from __future__ import annotations

from datetime import datetime, timezone

from prisma import Prisma
from prisma.models import PasswordResetToken, RefreshToken


class RefreshTokenRepository:
    def __init__(self, db: Prisma) -> None:
        self._db = db

    async def create(
        self,
        *,
        user_id: str,
        token_hash: str,
        expires_at: datetime,
        user_agent: str | None,
        ip_address: str | None,
    ) -> RefreshToken:
        return await self._db.refreshtoken.create(
            data={
                "user_id": user_id,
                "token_hash": token_hash,
                "expires_at": expires_at,
                "user_agent": user_agent,
                "ip_address": ip_address,
            }
        )

    async def find_valid(self, token_hash: str) -> RefreshToken | None:
        row = await self._db.refreshtoken.find_unique(where={"token_hash": token_hash})
        if row is None:
            return None
        exp = row.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            return None
        return row

    async def delete_by_hash(self, token_hash: str) -> None:
        await self._db.refreshtoken.delete_many(where={"token_hash": token_hash})

    async def delete_by_id_for_user(self, *, token_id: str, user_id: str) -> int:
        return await self._db.refreshtoken.delete_many(where={"id": token_id, "user_id": user_id})

    async def list_for_user(self, user_id: str) -> list[RefreshToken]:
        return await self._db.refreshtoken.find_many(
            where={"user_id": user_id},
            order={"created_at": "desc"},
            take=50,
        )


class PasswordResetRepository:
    def __init__(self, db: Prisma) -> None:
        self._db = db

    async def create(
        self, *, user_id: str, token_hash: str, expires_at: datetime
    ) -> PasswordResetToken:
        return await self._db.passwordresettoken.create(
            data={"user_id": user_id, "token_hash": token_hash, "expires_at": expires_at}
        )

    async def find_valid(self, token_hash: str) -> PasswordResetToken | None:
        row = await self._db.passwordresettoken.find_unique(where={"token_hash": token_hash})
        if row is None or row.used_at is not None:
            return None
        exp = row.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            return None
        return row

    async def mark_used(self, token_id: str) -> None:
        await self._db.passwordresettoken.update(
            where={"id": token_id},
            data={"used_at": datetime.now(timezone.utc)},
        )
