from __future__ import annotations
from prisma import Prisma
from prisma.enums import KycStatus, Role
from prisma.models import User


class UserRepository:
    def __init__(self, db: Prisma) -> None:
        self._db = db

    async def create(
        self,
        *,
        email: str,
        password_hash: str,
        full_name: str,
        role: Role,
    ) -> User:
        return await self._db.user.create(
            data={
                "email": email,
                "password_hash": password_hash,
                "full_name": full_name,
                "role": role,
            }
        )

    async def get_by_email(self, email: str) -> User | None:
        return await self._db.user.find_unique(where={"email": email})

    async def get_by_id(self, user_id: str) -> User | None:
        return await self._db.user.find_unique(where={"id": user_id})

    async def update_kyc(self, user_id: str, kyc_status: KycStatus) -> User:
        return await self._db.user.update(where={"id": user_id}, data={"kyc_status": kyc_status})

    async def update_is_active(self, user_id: str, *, is_active: bool) -> User:
        return await self._db.user.update(where={"id": user_id}, data={"is_active": is_active})

    async def count_all(self) -> int:
        return await self._db.user.count()

    async def list_for_admin(
        self,
        *,
        skip: int,
        take: int,
        kyc_status: KycStatus | None = None,
        search: str | None = None,
    ) -> tuple[list[User], int]:
        where: dict = {}
        if kyc_status is not None:
            where["kyc_status"] = kyc_status
        if search:
            where["email"] = {"contains": search, "mode": "insensitive"}
        total = await self._db.user.count(where=where)
        rows = await self._db.user.find_many(
            where=where,
            skip=skip,
            take=take,
            order={"created_at": "desc"},
        )
        return rows, total

    async def update_profile(
        self,
        user_id: str,
        *,
        full_name: str | None = None,
        phone: str | None = None,
        notify_email: bool | None = None,
        notify_push: bool | None = None,
    ) -> User:
        data: dict = {}
        if full_name is not None:
            data["full_name"] = full_name
        if phone is not None:
            data["phone"] = phone
        if notify_email is not None:
            data["notify_email"] = notify_email
        if notify_push is not None:
            data["notify_push"] = notify_push
        return await self._db.user.update(where={"id": user_id}, data=data)

    async def update_password_hash(self, user_id: str, password_hash: str) -> User:
        return await self._db.user.update(where={"id": user_id}, data={"password_hash": password_hash})

    async def set_mfa_secret(self, user_id: str, secret: str) -> User:
        return await self._db.user.update(
            where={"id": user_id},
            data={"mfa_totp_secret": secret, "mfa_enabled": False},
        )

    async def set_mfa_enabled(self, user_id: str, enabled: bool) -> User:
        return await self._db.user.update(where={"id": user_id}, data={"mfa_enabled": enabled})

    async def clear_mfa(self, user_id: str) -> User:
        return await self._db.user.update(
            where={"id": user_id},
            data={"mfa_totp_secret": None, "mfa_enabled": False},
        )

    async def update_limits(
        self,
        user_id: str,
        *,
        daily_transfer_max=None,
        daily_atm_max=None,
    ) -> User:
        data: dict = {}
        if daily_transfer_max is not None:
            data["daily_transfer_max"] = daily_transfer_max
        if daily_atm_max is not None:
            data["daily_atm_max"] = daily_atm_max
        if not data:
            u = await self.get_by_id(user_id)
            assert u is not None
            return u
        return await self._db.user.update(where={"id": user_id}, data=data)
