from __future__ import annotations
from decimal import Decimal

from prisma import Prisma
from prisma.enums import KycStatus
from prisma.models import User

from app.core.exceptions import NotFoundError, UnauthorizedError, ValidationAppError
from app.core.security import hash_password, verify_password
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.utils.enums import enum_or_str


class UserService:
    def __init__(self, prisma: Prisma, audit: AuditService) -> None:
        self._users = UserRepository(prisma)
        self._audit = audit

    async def submit_kyc(self, *, user: User, reference_id: str, ip: str | None) -> User:
        if user.kyc_status == KycStatus.VERIFIED:
            raise ValidationAppError("KYC already verified")
        await self._audit.log(
            user_id=user.id,
            action="KYC_SUBMITTED",
            resource=f"user:{user.id}",
            details={"reference_id": reference_id},
            ip_address=ip,
        )
        await self._audit.notify_user(
            user_id=user.id,
            message="KYC documents received. Our team will review shortly.",
        )
        return user

    async def admin_set_kyc(self, *, target_user_id: str, kyc_status: KycStatus, admin_id: str, ip: str | None) -> User:
        target = await self._users.get_by_id(target_user_id)
        if target is None:
            raise NotFoundError("User not found")
        updated = await self._users.update_kyc(target_user_id, kyc_status)
        await self._audit.log(
            user_id=admin_id,
            action="ADMIN_KYC_UPDATE",
            resource=f"user:{target_user_id}",
            details={"kyc_status": enum_or_str(kyc_status)},
            ip_address=ip,
        )
        await self._audit.notify_user(
            user_id=target_user_id,
            message=f"Your KYC status is now {enum_or_str(kyc_status)}.",
        )
        return updated

    async def update_me(
        self,
        *,
        user: User,
        full_name: str | None,
        phone: str | None,
        notify_email: bool | None,
        notify_push: bool | None,
    ) -> User:
        return await self._users.update_profile(
            user.id,
            full_name=full_name,
            phone=phone,
            notify_email=notify_email,
            notify_push=notify_push,
        )

    async def change_password(
        self, *, user: User, current_password: str, new_password: str, ip: str | None
    ) -> None:
        if not verify_password(current_password, user.password_hash):
            raise UnauthorizedError("Current password is incorrect")
        await self._users.update_password_hash(user.id, hash_password(new_password))
        await self._audit.log(
            user_id=user.id,
            action="USER_PASSWORD_CHANGED",
            resource=f"user:{user.id}",
            ip_address=ip,
        )

    async def update_limits(
        self,
        *,
        user: User,
        daily_transfer_max: Decimal | None,
        daily_atm_max: Decimal | None,
    ) -> User:
        return await self._users.update_limits(
            user.id,
            daily_transfer_max=daily_transfer_max,
            daily_atm_max=daily_atm_max,
        )
