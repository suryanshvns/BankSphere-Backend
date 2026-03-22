from __future__ import annotations
from decimal import Decimal

from prisma import Prisma
from prisma.enums import LoanStatus
from prisma.models import Loan


class LoanRepository:
    def __init__(self, db: Prisma) -> None:
        self._db = db

    async def create(
        self,
        *,
        user_id: str,
        principal: Decimal,
        annual_rate_pct: Decimal,
        tenure_months: int,
        emi: Decimal,
        purpose: str | None,
    ) -> Loan:
        return await self._db.loan.create(
            data={
                "user_id": user_id,
                "principal": principal,
                "annual_rate_pct": annual_rate_pct,
                "tenure_months": tenure_months,
                "emi": emi,
                "purpose": purpose,
            }
        )

    async def get_by_id(self, loan_id: str) -> Loan | None:
        return await self._db.loan.find_unique(where={"id": loan_id})

    async def list_by_user(self, user_id: str) -> list[Loan]:
        return await self._db.loan.find_many(where={"user_id": user_id}, order={"created_at": "desc"})

    async def update_status(self, loan_id: str, status: LoanStatus) -> Loan:
        return await self._db.loan.update(where={"id": loan_id}, data={"status": status})

    async def update_principal_emi(self, loan_id: str, *, principal: Decimal, emi: Decimal) -> Loan:
        return await self._db.loan.update(
            where={"id": loan_id},
            data={"principal": principal, "emi": emi},
        )

    async def count_all(self, *, status: LoanStatus | None = None) -> int:
        where = {"status": status} if status is not None else {}
        return await self._db.loan.count(where=where)

    async def list_all(
        self,
        *,
        skip: int = 0,
        take: int = 50,
        status: LoanStatus | None = None,
    ) -> list[Loan]:
        where = {"status": status} if status is not None else {}
        return await self._db.loan.find_many(
            where=where,
            order={"created_at": "desc"},
            skip=skip,
            take=take,
        )
