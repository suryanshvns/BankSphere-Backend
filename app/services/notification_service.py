from __future__ import annotations
from prisma import Prisma
from prisma.models import User

from app.repositories.audit_repository import AuditRepository
from app.schemas.notification import NotificationResponse


class NotificationService:
    def __init__(self, prisma: Prisma) -> None:
        self._audit = AuditRepository(prisma)

    async def list_for_user(self, *, user: User) -> list[NotificationResponse]:
        rows = await self._audit.list_notifications_for_user(user.id)
        out: list[NotificationResponse] = []
        for row in rows:
            details = row.details or {}
            msg = details.get("message")
            if not isinstance(msg, str):
                msg = "Notification"
            out.append(
                NotificationResponse(
                    id=row.id,
                    message=msg,
                    created_at=row.created_at,
                    read_at=getattr(row, "read_at", None),
                )
            )
        return out

    async def mark_read(self, *, user: User, notification_id: str) -> bool:
        return await self._audit.mark_notification_read(audit_id=notification_id, user_id=user.id)

    async def mark_all_read(self, *, user: User) -> None:
        await self._audit.mark_all_notifications_read(user.id)
