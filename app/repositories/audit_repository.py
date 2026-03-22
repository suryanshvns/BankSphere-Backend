from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

from prisma import Json, Prisma
from prisma.models import AuditLog


class AuditRepository:
    def __init__(self, db: Prisma) -> None:
        self._db = db

    async def create(
        self,
        *,
        user_id: str | None,
        action: str,
        resource: str | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        payload: dict = {
            "action": action,
            "resource": resource,
            "ip_address": ip_address,
        }
        if user_id is not None:
            payload["user"] = {"connect": {"id": user_id}}
        if details is not None:
            payload["details"] = Json(details)
        return await self._db.auditlog.create(data=payload)

    async def list_notifications_for_user(self, user_id: str, *, take: int = 50) -> list[AuditLog]:
        return await self._db.auditlog.find_many(
            where={"user_id": user_id, "action": "NOTIFICATION"},
            order={"created_at": "desc"},
            take=take,
        )

    async def mark_notification_read(self, *, audit_id: str, user_id: str) -> bool:
        row = await self._db.auditlog.find_first(
            where={"id": audit_id, "user_id": user_id, "action": "NOTIFICATION"}
        )
        if row is None:
            return False
        await self._db.auditlog.update(
            where={"id": audit_id},
            data={"read_at": datetime.now(timezone.utc)},
        )
        return True

    async def mark_all_notifications_read(self, user_id: str) -> None:
        await self._db.auditlog.update_many(
            where={
                "user_id": user_id,
                "action": "NOTIFICATION",
                "read_at": None,
            },
            data={"read_at": datetime.now(timezone.utc)},
        )

    @staticmethod
    def _admin_log_where(*, exclude_notifications: bool, action: str | None) -> dict:
        parts: list[dict] = []
        if exclude_notifications:
            parts.append({"NOT": {"action": "NOTIFICATION"}})
        if action:
            parts.append({"action": action})
        if not parts:
            return {}
        if len(parts) == 1:
            return parts[0]
        return {"AND": parts}

    async def count_admin_logs(
        self, *, exclude_notifications: bool = True, action: str | None = None
    ) -> int:
        where = self._admin_log_where(exclude_notifications=exclude_notifications, action=action)
        return await self._db.auditlog.count(where=where)

    async def list_admin_logs(
        self,
        *,
        skip: int = 0,
        take: int = 50,
        exclude_notifications: bool = True,
        action: str | None = None,
    ) -> list[AuditLog]:
        where = self._admin_log_where(exclude_notifications=exclude_notifications, action=action)
        return await self._db.auditlog.find_many(
            where=where,
            order={"created_at": "desc"},
            skip=skip,
            take=take,
        )
