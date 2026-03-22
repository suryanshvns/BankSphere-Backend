from __future__ import annotations

from typing import Any

from prisma import Prisma

from app.core.exceptions import NotFoundError
from app.core.security import hash_opaque_token, new_opaque_token
from app.repositories.extensions_repository import ApiKeyRepository, WebhookRepository
from app.services.audit_service import AuditService


class IntegrationsAdminService:
    def __init__(self, prisma: Prisma, audit: AuditService) -> None:
        self._webhooks = WebhookRepository(prisma)
        self._api_keys = ApiKeyRepository(prisma)
        self._audit = audit

    async def create_webhook(
        self,
        *,
        url: str,
        secret: str | None,
        events: list[Any] | dict[str, Any] | None,
        admin_id: str,
        ip: str | None,
    ):
        row = await self._webhooks.create(url=url, secret=secret, events=events)
        await self._audit.log(
            user_id=admin_id,
            action="ADMIN_WEBHOOK_CREATED",
            resource=f"webhook:{row.id}",
            details={"url": url},
            ip_address=ip,
        )
        return row

    async def list_webhooks(self):
        return await self._webhooks.list_all()

    async def delete_webhook(self, *, webhook_id: str, admin_id: str, ip: str | None) -> None:
        rows = await self._webhooks.list_all()
        if not any(w.id == webhook_id for w in rows):
            raise NotFoundError("Webhook not found")
        await self._webhooks.delete(webhook_id)
        await self._audit.log(
            user_id=admin_id,
            action="ADMIN_WEBHOOK_DELETED",
            resource=f"webhook:{webhook_id}",
            ip_address=ip,
        )

    async def create_api_key(self, *, name: str, admin_id: str, ip: str | None) -> tuple[object, str]:
        plain = new_opaque_token()
        row = await self._api_keys.create(name=name, key_hash=hash_opaque_token(plain))
        await self._audit.log(
            user_id=admin_id,
            action="ADMIN_API_KEY_CREATED",
            resource=f"api_key:{row.id}",
            details={"name": name},
            ip_address=ip,
        )
        return row, plain

    async def list_api_keys(self):
        return await self._api_keys.list_all()

    async def deactivate_api_key(self, *, key_id: str, admin_id: str, ip: str | None):
        keys = await self._api_keys.list_all()
        if not any(k.id == key_id for k in keys):
            raise NotFoundError("API key not found")
        row = await self._api_keys.deactivate(key_id)
        await self._audit.log(
            user_id=admin_id,
            action="ADMIN_API_KEY_DEACTIVATED",
            resource=f"api_key:{key_id}",
            ip_address=ip,
        )
        return row
