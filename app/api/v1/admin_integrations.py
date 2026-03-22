from __future__ import annotations
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.deps import get_integrations_admin_service, require_admin
from app.schemas.extras import (
    ApiKeyCreateRequest,
    ApiKeyCreatedResponse,
    ApiKeyResponse,
    WebhookCreateRequest,
    WebhookResponse,
)
from app.services.integrations_admin_service import IntegrationsAdminService
from app.utils.request_info import get_client_ip
from app.utils.response import success_response

router = APIRouter(prefix="/admin", tags=["admin-integrations"])


@router.post("/webhooks")
async def admin_create_webhook(
    request: Request,
    body: WebhookCreateRequest,
    admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[IntegrationsAdminService, Depends(get_integrations_admin_service)],
) -> dict:
    row = await svc.create_webhook(
        url=body.url,
        secret=body.secret,
        events=body.events,
        admin_id=getattr(admin, "id"),  # type: ignore[arg-type]
        ip=get_client_ip(request),
    )
    return success_response(WebhookResponse.model_validate(row).model_dump(mode="json"))


@router.get("/webhooks")
async def admin_list_webhooks(
    _admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[IntegrationsAdminService, Depends(get_integrations_admin_service)],
) -> dict:
    rows = await svc.list_webhooks()
    data = [WebhookResponse.model_validate(w).model_dump(mode="json") for w in rows]
    return success_response(data)


@router.delete("/webhooks/{webhook_id}")
async def admin_delete_webhook(
    webhook_id: str,
    request: Request,
    admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[IntegrationsAdminService, Depends(get_integrations_admin_service)],
) -> dict:
    await svc.delete_webhook(
        webhook_id=webhook_id,
        admin_id=getattr(admin, "id"),  # type: ignore[arg-type]
        ip=get_client_ip(request),
    )
    return success_response({"ok": True})


@router.post("/api-keys")
async def admin_create_api_key(
    request: Request,
    body: ApiKeyCreateRequest,
    admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[IntegrationsAdminService, Depends(get_integrations_admin_service)],
) -> dict:
    row, plain = await svc.create_api_key(
        name=body.name,
        admin_id=getattr(admin, "id"),  # type: ignore[arg-type]
        ip=get_client_ip(request),
    )
    payload = ApiKeyCreatedResponse(
        id=row.id,
        name=row.name,
        key=plain,
        created_at=row.created_at,
    )
    return success_response(payload.model_dump(mode="json"))


@router.get("/api-keys")
async def admin_list_api_keys(
    _admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[IntegrationsAdminService, Depends(get_integrations_admin_service)],
) -> dict:
    rows = await svc.list_api_keys()
    data = [ApiKeyResponse.model_validate(k).model_dump(mode="json") for k in rows]
    return success_response(data)


@router.post("/api-keys/{key_id}/deactivate")
async def admin_deactivate_api_key(
    key_id: str,
    request: Request,
    admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[IntegrationsAdminService, Depends(get_integrations_admin_service)],
) -> dict:
    row = await svc.deactivate_api_key(
        key_id=key_id,
        admin_id=getattr(admin, "id"),  # type: ignore[arg-type]
        ip=get_client_ip(request),
    )
    return success_response(ApiKeyResponse.model_validate(row).model_dump(mode="json"))
