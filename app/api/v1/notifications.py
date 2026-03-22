from __future__ import annotations
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user, get_notification_service
from app.core.exceptions import NotFoundError
from app.services.notification_service import NotificationService
from app.utils.response import success_response

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[NotificationService, Depends(get_notification_service)],
) -> dict:
    items = await svc.list_for_user(user=user)  # type: ignore[arg-type]
    return success_response([n.model_dump(mode="json") for n in items])


@router.patch("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[NotificationService, Depends(get_notification_service)],
) -> dict:
    ok = await svc.mark_read(user=user, notification_id=notification_id)  # type: ignore[arg-type]
    if not ok:
        raise NotFoundError("Notification not found")
    return success_response({"ok": True})


@router.post("/read-all")
async def mark_all_notifications_read(
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[NotificationService, Depends(get_notification_service)],
) -> dict:
    await svc.mark_all_read(user=user)  # type: ignore[arg-type]
    return success_response({"ok": True})
