from __future__ import annotations
from typing import Any

from prisma import Prisma

from app.repositories.audit_repository import AuditRepository


class AuditService:
    def __init__(self, prisma: Prisma) -> None:
        self._repo = AuditRepository(prisma)

    async def log(
        self,
        *,
        user_id: str | None,
        action: str,
        resource: str | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> None:
        await self._repo.create(
            user_id=user_id,
            action=action,
            resource=resource,
            details=details,
            ip_address=ip_address,
        )

    async def notify_user(self, *, user_id: str, message: str) -> None:
        await self._repo.create(
            user_id=user_id,
            action="NOTIFICATION",
            resource="in_app",
            details={"message": message},
        )
