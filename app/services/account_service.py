from __future__ import annotations
from datetime import datetime
from decimal import Decimal

from prisma import Prisma
from prisma.enums import TransactionKind, TransactionStatus
from prisma.models import Account, User

from app.core.exceptions import ForbiddenError, NotFoundError
from app.repositories.account_repository import AccountRepository
from app.repositories.transaction_repository import TransactionRepository
from app.services.audit_service import AuditService
from app.utils.enums import enum_or_str


class AccountService:
    def __init__(self, prisma: Prisma, audit: AuditService) -> None:
        self._prisma = prisma
        self._accounts = AccountRepository(prisma)
        self._audit = audit

    async def create_account(self, *, user: User, account_type, currency: str, ip: str | None) -> Account:
        acc = await self._accounts.create(user_id=user.id, account_type=account_type, currency=currency)
        await self._audit.log(
            user_id=user.id,
            action="ACCOUNT_CREATED",
            resource=f"account:{acc.id}",
            details={"type": enum_or_str(account_type)},
            ip_address=ip,
        )
        return acc

    async def get_account(self, *, user: User, account_id: str) -> Account:
        acc = await self._accounts.get_by_id(account_id)
        if acc is None:
            raise NotFoundError("Account not found")
        if acc.user_id != user.id:
            raise ForbiddenError("Not allowed to access this account")
        return acc

    async def list_accounts(self, *, user: User) -> list[Account]:
        return await self._accounts.list_by_user(user.id)

    async def update_own_nickname(self, *, user: User, account_id: str, nickname: str | None) -> Account:
        await self.get_account(user=user, account_id=account_id)
        return await self._accounts.update_meta(account_id, nickname=nickname)

    async def balance_snapshot(self, *, user: User, account_id: str) -> dict:
        acc = await self.get_account(user=user, account_id=account_id)
        hb = getattr(acc, "hold_balance", None)
        if hb is None:
            hb = Decimal("0")
        avail = acc.balance - hb
        return {
            "account_id": acc.id,
            "balance": str(acc.balance),
            "available_balance": str(avail),
            "hold_balance": str(hb),
            "currency": acc.currency,
            "as_of": acc.updated_at.isoformat(),
            "is_frozen": getattr(acc, "is_frozen", False),
        }

    async def statement_page(
        self,
        *,
        user: User,
        account_id: str,
        date_from: datetime | None,
        date_to: datetime | None,
        skip: int,
        take: int,
    ) -> tuple[list, int, Account]:
        acc = await self.get_account(user=user, account_id=account_id)
        repo = TransactionRepository(self._prisma)
        ids = [account_id]
        total = await repo.count_for_accounts(
            ids,
            created_after=date_from,
            created_before=date_to,
        )
        rows = await repo.list_for_accounts(
            ids,
            skip=skip,
            take=take,
            created_after=date_from,
            created_before=date_to,
        )
        return rows, total, acc

    async def statement_csv_rows(
        self,
        *,
        user: User,
        account_id: str,
        date_from: datetime | None,
        date_to: datetime | None,
        max_rows: int = 5000,
    ) -> tuple[list, Account]:
        acc = await self.get_account(user=user, account_id=account_id)
        repo = TransactionRepository(self._prisma)
        rows = await repo.list_for_accounts(
            [account_id],
            skip=0,
            take=max_rows,
            created_after=date_from,
            created_before=date_to,
        )
        return rows, acc
