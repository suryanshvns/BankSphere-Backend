from __future__ import annotations
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.deps import get_current_user, get_customer_extensions_service
from app.schemas.extras import RecurringActiveRequest, RecurringCreateRequest, RecurringPaymentResponse
from app.services.customer_extensions_service import CustomerExtensionsService
from app.utils.request_info import get_client_ip
from app.utils.response import success_response

router = APIRouter(prefix="/recurring-payments", tags=["recurring-payments"])


@router.post("")
async def create_recurring(
    request: Request,
    body: RecurringCreateRequest,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[CustomerExtensionsService, Depends(get_customer_extensions_service)],
) -> dict:
    row = await svc.create_recurring(
        user=user,  # type: ignore[arg-type]
        from_account_id=body.from_account_id,
        to_account_id=body.to_account_id,
        amount=body.amount,
        frequency=body.frequency,
        next_run_at=body.next_run_at,
        description=body.description,
        ip=get_client_ip(request),
    )
    return success_response(RecurringPaymentResponse.model_validate(row).model_dump(mode="json"))


@router.get("")
async def list_recurring(
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[CustomerExtensionsService, Depends(get_customer_extensions_service)],
) -> dict:
    rows = await svc.list_recurring(user=user)  # type: ignore[arg-type]
    data = [RecurringPaymentResponse.model_validate(r).model_dump(mode="json") for r in rows]
    return success_response(data)


@router.patch("/{recurring_id}/active")
async def set_recurring_active(
    recurring_id: str,
    request: Request,
    body: RecurringActiveRequest,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[CustomerExtensionsService, Depends(get_customer_extensions_service)],
) -> dict:
    row = await svc.set_recurring_active(
        user=user,  # type: ignore[arg-type]
        recurring_id=recurring_id,
        active=body.active,
        ip=get_client_ip(request),
    )
    return success_response(RecurringPaymentResponse.model_validate(row).model_dump(mode="json"))
