from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from math import ceil

from prisma import Prisma
from prisma.enums import KycStatus, LoanStatus, TransactionStatus
from prisma.models import User

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationAppError
from app.repositories.account_repository import AccountRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.loan_repository import LoanRepository
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.utils.enums import enum_or_str


class AdminService:
    def __init__(self, prisma: Prisma, audit: AuditService) -> None:
        self._users = UserRepository(prisma)
        self._accounts = AccountRepository(prisma)
        self._txns = TransactionRepository(prisma)
        self._loans = LoanRepository(prisma)
        self._audit_logs = AuditRepository(prisma)
        self._audit = audit

    async def dashboard_summary(self) -> dict:
        total_users = await self._users.count_all()
        total_tx = await self._txns.count_all()
        total_volume = await self._txns.sum_successful_amount()
        success_c = await self._txns.count_all(status=TransactionStatus.SUCCESS)
        failed_c = await self._txns.count_all(status=TransactionStatus.FAILED)
        pending_c = await self._txns.count_all(status=TransactionStatus.PENDING)
        pending_loans = await self._loans.count_all(status=LoanStatus.PENDING)
        return {
            "total_users": total_users,
            "total_transactions": total_tx,
            "total_volume": str(total_volume),
            "transactions_by_status": {
                "SUCCESS": success_c,
                "FAILED": failed_c,
                "PENDING": pending_c,
            },
            "pending_loan_requests": pending_loans,
        }

    async def volume_by_day(self, *, days: int) -> list[dict[str, str]]:
        days = max(1, min(days, 90))
        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = await self._txns.list_success_for_chart(since=since)
        buckets: dict[str, Decimal] = {}
        for t in rows:
            dt = t.created_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            key = dt.date().isoformat()
            buckets[key] = buckets.get(key, Decimal("0")) + t.amount
        ordered = sorted(buckets.items(), key=lambda x: x[0])
        return [{"date": d, "volume": str(v)} for d, v in ordered]

    async def list_users(
        self,
        *,
        page: int,
        page_size: int,
        kyc_status: KycStatus | None,
        search: str | None,
    ) -> tuple[list[User], int]:
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        skip = (page - 1) * page_size
        rows, total = await self._users.list_for_admin(
            skip=skip,
            take=page_size,
            kyc_status=kyc_status,
            search=search or None,
        )
        return rows, total

    async def set_user_blocked(
        self,
        *,
        target_user_id: str,
        blocked: bool,
        admin_id: str,
        ip: str | None,
    ) -> User:
        if target_user_id == admin_id:
            raise ValidationAppError("Cannot change your own account status")
        target = await self._users.get_by_id(target_user_id)
        if target is None:
            raise NotFoundError("User not found")
        role_val = enum_or_str(getattr(target, "role", ""))
        if role_val == "ADMIN":
            raise ForbiddenError("Cannot block or unblock administrator accounts")
        is_active = not blocked
        updated = await self._users.update_is_active(target_user_id, is_active=is_active)
        await self._audit.log(
            user_id=admin_id,
            action="ADMIN_USER_BLOCK" if blocked else "ADMIN_USER_UNBLOCK",
            resource=f"user:{target_user_id}",
            details={"blocked": blocked},
            ip_address=ip,
        )
        return updated

    async def list_transactions(
        self,
        *,
        page: int,
        page_size: int,
        status: TransactionStatus | None,
    ) -> tuple[list, int]:
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        skip = (page - 1) * page_size
        total = await self._txns.count_all(status=status)
        rows = await self._txns.list_all(skip=skip, take=page_size, status=status)
        return rows, total

    async def list_loans(
        self,
        *,
        page: int,
        page_size: int,
        status: LoanStatus | None,
    ) -> tuple[list, int]:
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        skip = (page - 1) * page_size
        total = await self._loans.count_all(status=status)
        rows = await self._loans.list_all(skip=skip, take=page_size, status=status)
        return rows, total

    async def get_user_detail(self, *, user_id: str) -> tuple[User, list]:
        u = await self._users.get_by_id(user_id)
        if u is None:
            raise NotFoundError("User not found")
        accs = await self._accounts.list_all_for_user(user_id)
        return u, accs

    async def freeze_account(
        self,
        *,
        account_id: str,
        frozen: bool,
        admin_id: str,
        ip: str | None,
    ):
        acc = await self._accounts.get_by_id(account_id)
        if acc is None:
            raise NotFoundError("Account not found")
        updated = await self._accounts.update_meta(account_id, is_frozen=frozen)
        await self._audit.log(
            user_id=admin_id,
            action="ADMIN_ACCOUNT_FREEZE" if frozen else "ADMIN_ACCOUNT_UNFREEZE",
            resource=f"account:{account_id}",
            details={"frozen": frozen, "owner_user_id": acc.user_id},
            ip_address=ip,
        )
        return updated

    async def list_audit_logs(
        self,
        *,
        page: int,
        page_size: int,
        action: str | None,
    ) -> tuple[list, int]:
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        skip = (page - 1) * page_size
        total = await self._audit_logs.count_admin_logs(
            exclude_notifications=True,
            action=action,
        )
        rows = await self._audit_logs.list_admin_logs(
            skip=skip,
            take=page_size,
            exclude_notifications=True,
            action=action,
        )
        return rows, total


def total_pages(total_items: int, page_size: int) -> int:
    if total_items == 0:
        return 0
    return int(ceil(total_items / page_size))
