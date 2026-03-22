from __future__ import annotations
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.deps import (
    get_card_auth_service,
    get_current_user,
    get_cx_portal_service,
    get_mfa_service,
    get_payment_instructions_service,
    get_transaction_service,
)
from app.schemas.enterprise import (
    CardAuthorizeRequest,
    CardCaptureRequest,
    KybUpsertRequest,
    MfaConfirmRequest,
    MfaDisableRequest,
    OutboundPaymentCreateRequest,
    SupportCaseCreateRequest,
)
from app.services.card_auth_service import CardAuthService
from app.services.cx_portal_service import CxPortalService
from app.services.mfa_service import MfaService
from app.services.payment_instructions_service import PaymentInstructionsService
from app.services.transaction_service import TransactionService
from app.utils.request_info import get_client_ip
from app.utils.response import success_response

router = APIRouter(prefix="/platform", tags=["platform"])


@router.post("/mfa/enroll/start")
async def mfa_enroll_start(
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[MfaService, Depends(get_mfa_service)],
) -> dict:
    out = await svc.enroll_start(user=user)  # type: ignore[arg-type]
    return success_response(out)


@router.post("/mfa/enroll/confirm")
async def mfa_enroll_confirm(
    body: MfaConfirmRequest,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[MfaService, Depends(get_mfa_service)],
) -> dict:
    u = await svc.enroll_confirm(user=user, code=body.code)  # type: ignore[arg-type]
    from app.schemas.user import UserResponse

    return success_response(UserResponse.model_validate(u).model_dump(mode="json"))


@router.post("/mfa/disable")
async def mfa_disable(
    body: MfaDisableRequest,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[MfaService, Depends(get_mfa_service)],
) -> dict:
    u = await svc.disable(user=user, password=body.password)  # type: ignore[arg-type]
    from app.schemas.user import UserResponse

    return success_response(UserResponse.model_validate(u).model_dump(mode="json"))


@router.post("/payments/outbound")
async def create_outbound_payment(
    request: Request,
    body: OutboundPaymentCreateRequest,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[PaymentInstructionsService, Depends(get_payment_instructions_service)],
) -> dict:
    row = await svc.create(
        user=user,  # type: ignore[arg-type]
        from_account_id=body.from_account_id,
        amount=body.amount,
        rail=body.rail,
        counterparty=body.counterparty,
        idempotency_key=body.idempotency_key,
        reference=body.reference,
        ip=get_client_ip(request),
    )
    return success_response(
        {
            "id": row.id,
            "status": row.status.value if hasattr(row.status, "value") else str(row.status),
            "amount": str(row.amount),
            "rail": row.rail.value if hasattr(row.rail, "value") else str(row.rail),
        }
    )


@router.get("/payments/outbound")
async def list_outbound_payments(
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[PaymentInstructionsService, Depends(get_payment_instructions_service)],
) -> dict:
    rows = await svc.list_for_user(user=user)  # type: ignore[arg-type]
    data = [
        {
            "id": r.id,
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            "amount": str(r.amount),
            "rail": r.rail.value if hasattr(r.rail, "value") else str(r.rail),
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
    return success_response(data)


@router.post("/cards/{card_id}/authorize")
async def platform_card_authorize(
    card_id: str,
    request: Request,
    body: CardAuthorizeRequest,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[CardAuthService, Depends(get_card_auth_service)],
) -> dict:
    row = await svc.authorize(
        user=user,  # type: ignore[arg-type]
        card_id=card_id,
        amount=body.amount,
        merchant_name=body.merchant_name,
        idempotency_key=body.idempotency_key,
        ip=get_client_ip(request),
    )
    return success_response(
        {"id": row.id, "status": str(row.status), "amount": str(row.amount)}
    )


@router.post("/cards/authorizations/{authorization_id}/reverse")
async def platform_card_reverse(
    authorization_id: str,
    request: Request,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[CardAuthService, Depends(get_card_auth_service)],
) -> dict:
    row = await svc.reverse(
        user=user,  # type: ignore[arg-type]
        authorization_id=authorization_id,
        ip=get_client_ip(request),
    )
    return success_response({"id": row.id, "status": str(row.status)})


@router.post("/cards/{card_id}/capture")
async def platform_card_capture(
    card_id: str,
    request: Request,
    body: CardCaptureRequest,
    user: Annotated[object, Depends(get_current_user)],
    txn: Annotated[TransactionService, Depends(get_transaction_service)],
) -> dict:
    from app.schemas.transaction import TransactionResponse

    t = await txn.card_capture(
        user=user,  # type: ignore[arg-type]
        card_id=card_id,
        authorization_id=body.authorization_id,
        from_account_id=body.from_account_id,
        idempotency_key=body.idempotency_key,
        ip=get_client_ip(request),
    )
    return success_response(TransactionResponse.model_validate(t).model_dump(mode="json"))


@router.post("/support/cases")
async def create_support_case(
    request: Request,
    body: SupportCaseCreateRequest,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[CxPortalService, Depends(get_cx_portal_service)],
) -> dict:
    row = await svc.create_support_case(
        user=user,  # type: ignore[arg-type]
        subject=body.subject,
        body=body.body,
        priority=body.priority,
        ip=get_client_ip(request),
    )
    return success_response(
        {
            "id": row.id,
            "subject": row.subject,
            "status": row.status.value if hasattr(row.status, "value") else str(row.status),
        }
    )


@router.get("/support/cases")
async def list_support_cases(
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[CxPortalService, Depends(get_cx_portal_service)],
) -> dict:
    rows = await svc.list_support_cases(user=user)  # type: ignore[arg-type]
    return success_response(
        [
            {
                "id": r.id,
                "subject": r.subject,
                "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    )


@router.post("/business/profile")
async def upsert_business_profile(
    request: Request,
    body: KybUpsertRequest,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[CxPortalService, Depends(get_cx_portal_service)],
) -> dict:
    row = await svc.upsert_business_profile(
        user=user,  # type: ignore[arg-type]
        company_name=body.company_name,
        registration_number=body.registration_number,
        country=body.country,
        ip=get_client_ip(request),
    )
    return success_response(
        {
            "id": row.id,
            "company_name": row.company_name,
            "status": row.status.value if hasattr(row.status, "value") else str(row.status),
        }
    )


@router.post("/privacy/data-export")
async def request_data_export(
    request: Request,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[CxPortalService, Depends(get_cx_portal_service)],
) -> dict:
    row = await svc.request_data_export(user=user, ip=get_client_ip(request))  # type: ignore[arg-type]
    return success_response({"id": row.id, "status": str(row.status)})


@router.get("/privacy/data-export/{export_id}")
async def get_data_export(
    export_id: str,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[CxPortalService, Depends(get_cx_portal_service)],
) -> dict:
    row = await svc.get_data_export(user=user, export_id=export_id)  # type: ignore[arg-type]
    return success_response(
        {
            "id": row.id,
            "status": row.status.value if hasattr(row.status, "value") else str(row.status),
            "result_json": row.result_json,
            "created_at": row.created_at.isoformat(),
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        }
    )
