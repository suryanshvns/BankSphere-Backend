from __future__ import annotations
from decimal import Decimal

from prisma import Prisma
from prisma.enums import AccountType
from prisma.models import Account


class AccountRepository:
    def __init__(self, db: Prisma) -> None:
        self._db = db

    async def create(
        self,
        *,
        user_id: str,
        account_type: AccountType,
        currency: str,
    ) -> Account:
        return await self._db.account.create(
            data={"user_id": user_id, "type": account_type, "currency": currency}
        )

    async def get_by_id(self, account_id: str) -> Account | None:
        return await self._db.account.find_unique(where={"id": account_id})

    async def list_by_user(self, user_id: str) -> list[Account]:
        return await self._db.account.find_many(where={"user_id": user_id, "is_active": True})

    async def list_all_for_user(self, user_id: str) -> list[Account]:
        return await self._db.account.find_many(where={"user_id": user_id})

    async def update_meta(
        self,
        account_id: str,
        *,
        nickname: str | None = None,
        is_frozen: bool | None = None,
    ) -> Account:
        data: dict = {}
        if nickname is not None:
            data["nickname"] = nickname
        if is_frozen is not None:
            data["is_frozen"] = is_frozen
        return await self._db.account.update(where={"id": account_id}, data=data)
