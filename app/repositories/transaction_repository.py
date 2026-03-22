from __future__ import annotations
from datetime import datetime
from decimal import Decimal

from prisma import Prisma
from prisma.enums import TransactionKind, TransactionStatus
from prisma.models import Transaction


class TransactionRepository:
    def __init__(self, db: Prisma) -> None:
        self._db = db

    async def find_by_idempotency_key(self, key: str) -> Transaction | None:
        return await self._db.transaction.find_unique(where={"idempotency_key": key})

    async def get_by_id(self, tx_id: str) -> Transaction | None:
        return await self._db.transaction.find_unique(where={"id": tx_id})

    async def list_for_accounts(
        self,
        account_ids: list[str],
        *,
        skip: int = 0,
        take: int = 50,
        kind: TransactionKind | None = None,
        status: TransactionStatus | None = None,
        created_after=None,
        created_before=None,
    ) -> list[Transaction]:
        if not account_ids:
            return []
        base: dict = {
            "OR": [
                {"from_account_id": {"in": account_ids}},
                {"to_account_id": {"in": account_ids}},
            ]
        }
        parts: list[dict] = [base]
        if kind is not None:
            parts.append({"kind": kind})
        if status is not None:
            parts.append({"status": status})
        if created_after is not None:
            parts.append({"created_at": {"gte": created_after}})
        if created_before is not None:
            parts.append({"created_at": {"lte": created_before}})
        where: dict = parts[0] if len(parts) == 1 else {"AND": parts}
        return await self._db.transaction.find_many(
            where=where,
            order={"created_at": "desc"},
            skip=skip,
            take=take,
        )

    async def count_for_accounts(
        self,
        account_ids: list[str],
        *,
        kind: TransactionKind | None = None,
        status: TransactionStatus | None = None,
        created_after=None,
        created_before=None,
    ) -> int:
        if not account_ids:
            return 0
        base: dict = {
            "OR": [
                {"from_account_id": {"in": account_ids}},
                {"to_account_id": {"in": account_ids}},
            ]
        }
        parts: list[dict] = [base]
        if kind is not None:
            parts.append({"kind": kind})
        if status is not None:
            parts.append({"status": status})
        if created_after is not None:
            parts.append({"created_at": {"gte": created_after}})
        if created_before is not None:
            parts.append({"created_at": {"lte": created_before}})
        where: dict = parts[0] if len(parts) == 1 else {"AND": parts}
        return await self._db.transaction.count(where=where)

    async def count_all(self, *, status: TransactionStatus | None = None) -> int:
        where = {"status": status} if status is not None else {}
        return await self._db.transaction.count(where=where)

    async def list_all(
        self,
        *,
        skip: int = 0,
        take: int = 50,
        status: TransactionStatus | None = None,
    ) -> list[Transaction]:
        where = {"status": status} if status is not None else {}
        return await self._db.transaction.find_many(
            where=where,
            order={"created_at": "desc"},
            skip=skip,
            take=take,
        )

    async def sum_successful_amount(self) -> Decimal:
        rows = await self._db.query_raw(
            'SELECT COALESCE(SUM(amount), 0) AS s FROM "Transaction" WHERE status = \'SUCCESS\'',
        )
        if not rows:
            return Decimal("0")
        val = rows[0]["s"]
        return Decimal(str(val))

    async def list_success_for_chart(self, *, since: datetime) -> list[Transaction]:
        return await self._db.transaction.find_many(
            where={"status": TransactionStatus.SUCCESS, "created_at": {"gte": since}},
            order={"created_at": "asc"},
            take=10_000,
        )

    async def create_final(
        self,
        *,
        idempotency_key: str,
        kind: TransactionKind,
        status: TransactionStatus,
        amount: Decimal,
        from_account_id: str | None,
        to_account_id: str | None,
        description: str | None,
        failure_reason: str | None = None,
        client_reference: str | None = None,
    ) -> Transaction:
        return await self._db.transaction.create(
            data={
                "idempotency_key": idempotency_key,
                "kind": kind,
                "status": status,
                "amount": amount,
                "from_account_id": from_account_id,
                "to_account_id": to_account_id,
                "description": description,
                "failure_reason": failure_reason,
                "client_reference": client_reference,
            }
        )
