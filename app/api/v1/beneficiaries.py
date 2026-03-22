from __future__ import annotations
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.deps import get_current_user, get_customer_extensions_service
from app.schemas.extras import BeneficiaryCreateRequest, BeneficiaryResponse
from app.services.customer_extensions_service import CustomerExtensionsService
from app.utils.request_info import get_client_ip
from app.utils.response import success_response

router = APIRouter(prefix="/beneficiaries", tags=["beneficiaries"])


@router.post("")
async def create_beneficiary(
    request: Request,
    body: BeneficiaryCreateRequest,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[CustomerExtensionsService, Depends(get_customer_extensions_service)],
) -> dict:
    row = await svc.create_beneficiary(
        user=user,  # type: ignore[arg-type]
        display_name=body.display_name,
        beneficiary_account_id=body.beneficiary_account_id,
        ip=get_client_ip(request),
    )
    return success_response(BeneficiaryResponse.model_validate(row).model_dump(mode="json"))


@router.get("")
async def list_beneficiaries(
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[CustomerExtensionsService, Depends(get_customer_extensions_service)],
) -> dict:
    rows = await svc.list_beneficiaries(user=user)  # type: ignore[arg-type]
    data = [BeneficiaryResponse.model_validate(b).model_dump(mode="json") for b in rows]
    return success_response(data)


@router.delete("/{beneficiary_id}")
async def delete_beneficiary(
    beneficiary_id: str,
    request: Request,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[CustomerExtensionsService, Depends(get_customer_extensions_service)],
) -> dict:
    await svc.delete_beneficiary(
        user=user,  # type: ignore[arg-type]
        beneficiary_id=beneficiary_id,
        ip=get_client_ip(request),
    )
    return success_response({"ok": True})
