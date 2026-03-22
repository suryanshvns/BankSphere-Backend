from __future__ import annotations
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.deps import get_current_user, get_customer_extensions_service
from app.schemas.extras import CardCreateRequest, CardFreezeRequest, CardResponse
from app.services.customer_extensions_service import CustomerExtensionsService
from app.utils.request_info import get_client_ip
from app.utils.response import success_response

router = APIRouter(prefix="/cards", tags=["cards"])


@router.post("")
async def create_card(
    request: Request,
    body: CardCreateRequest,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[CustomerExtensionsService, Depends(get_customer_extensions_service)],
) -> dict:
    row = await svc.create_card(
        user=user,  # type: ignore[arg-type]
        label=body.label,
        last4=body.last4,
        ip=get_client_ip(request),
    )
    return success_response(CardResponse.model_validate(row).model_dump(mode="json"))


@router.get("")
async def list_cards(
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[CustomerExtensionsService, Depends(get_customer_extensions_service)],
) -> dict:
    rows = await svc.list_cards(user=user)  # type: ignore[arg-type]
    data = [CardResponse.model_validate(c).model_dump(mode="json") for c in rows]
    return success_response(data)


@router.patch("/{card_id}/freeze")
async def freeze_card(
    card_id: str,
    request: Request,
    body: CardFreezeRequest,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[CustomerExtensionsService, Depends(get_customer_extensions_service)],
) -> dict:
    row = await svc.set_card_frozen(
        user=user,  # type: ignore[arg-type]
        card_id=card_id,
        is_frozen=body.is_frozen,
        ip=get_client_ip(request),
    )
    return success_response(CardResponse.model_validate(row).model_dump(mode="json"))


@router.post("/{card_id}/cancel")
async def cancel_card(
    card_id: str,
    request: Request,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[CustomerExtensionsService, Depends(get_customer_extensions_service)],
) -> dict:
    row = await svc.cancel_card(
        user=user,  # type: ignore[arg-type]
        card_id=card_id,
        ip=get_client_ip(request),
    )
    return success_response(CardResponse.model_validate(row).model_dump(mode="json"))
