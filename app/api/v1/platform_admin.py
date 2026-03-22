from __future__ import annotations
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from app.core.deps import (
    get_bank_operations_service,
    get_payment_instructions_service,
    require_admin,
)
from app.schemas.enterprise import (
    AccountHoldCreateRequest,
    PendingActionCreateRequest,
    PendingActionResolveRequest,
    WebhookEnqueueRequest,
)
from app.services.bank_operations_service import BankOperationsService
from app.services.payment_instructions_service import PaymentInstructionsService
from app.utils.request_info import get_client_ip
from app.utils.response import success_response

router = APIRouter(prefix="/admin/ops", tags=["platform-admin"])


@router.get("/ledger/accounts")
async def ops_ledger_accounts(
    _admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[BankOperationsService, Depends(get_bank_operations_service)],
) -> dict:
    rows = await svc.list_ledger_accounts()
    return success_response(
        [
            {
                "id": r.id,
                "code": r.code,
                "name": r.name,
                "type": r.type.value if hasattr(r.type, "value") else str(r.type),
            }
            for r in rows
        ]
    )


@router.get("/ledger/journal-entries")
async def ops_journal_entries(
    _admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[BankOperationsService, Depends(get_bank_operations_service)],
    take: int = 50,
) -> dict:
    rows = await svc.list_journal_entries(take=min(take, 200))
    out: list[dict[str, Any]] = []
    for e in rows:
        lines = []
        for ln in getattr(e, "_lines_loaded", []) or []:
            la = getattr(ln, "ledger_account", None)
            lines.append(
                {
                    "ledger_code": la.code if la else None,
                    "side": ln.side.value if hasattr(ln.side, "value") else str(ln.side),
                    "amount": str(ln.amount),
                    "internal_account_id": ln.internal_account_id,
                }
            )
        out.append(
            {
                "id": e.id,
                "transaction_id": e.transaction_id,
                "memo": e.memo,
                "posted_at": e.posted_at.isoformat(),
                "lines": lines,
            }
        )
    return success_response(out)


@router.post("/payment-instructions/{instruction_id}/settle")
async def ops_pi_settle(
    instruction_id: str,
    request: Request,
    admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[PaymentInstructionsService, Depends(get_payment_instructions_service)],
) -> dict:
    row = await svc.admin_settle(
        instruction_id=instruction_id,
        admin_id=getattr(admin, "id"),  # type: ignore[arg-type]
        ip=get_client_ip(request),
    )
    return success_response({"id": row.id, "status": str(row.status)})


@router.post("/payment-instructions/{instruction_id}/return")
async def ops_pi_return(
    instruction_id: str,
    request: Request,
    admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[PaymentInstructionsService, Depends(get_payment_instructions_service)],
) -> dict:
    row = await svc.admin_return(
        instruction_id=instruction_id,
        admin_id=getattr(admin, "id"),  # type: ignore[arg-type]
        ip=get_client_ip(request),
    )
    return success_response({"id": row.id, "status": str(row.status)})


@router.post("/accounts/{account_id}/holds")
async def ops_create_hold(
    account_id: str,
    request: Request,
    body: AccountHoldCreateRequest,
    admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[BankOperationsService, Depends(get_bank_operations_service)],
) -> dict:
    row = await svc.create_account_hold(
        account_id=account_id,
        amount=body.amount,
        reason=body.reason,
        admin_id=getattr(admin, "id"),  # type: ignore[arg-type]
        ip=get_client_ip(request),
    )
    return success_response({"id": row.id if row else None, "account_id": account_id})


@router.delete("/holds/{hold_id}")
async def ops_release_hold(
    hold_id: str,
    request: Request,
    admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[BankOperationsService, Depends(get_bank_operations_service)],
) -> dict:
    row = await svc.release_hold(
        hold_id=hold_id,
        admin_id=getattr(admin, "id"),  # type: ignore[arg-type]
        ip=get_client_ip(request),
    )
    return success_response({"id": row.id if row else hold_id, "released": True})


@router.post("/pending-actions")
async def ops_create_pending(
    request: Request,
    body: PendingActionCreateRequest,
    admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[BankOperationsService, Depends(get_bank_operations_service)],
) -> dict:
    row = await svc.create_pending_action(
        maker_id=getattr(admin, "id"),  # type: ignore[arg-type]
        action_type=body.action_type,
        payload=body.payload,
        ip=get_client_ip(request),
    )
    return success_response({"id": row.id, "status": str(row.status)})


@router.get("/pending-actions")
async def ops_list_pending(
    _admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[BankOperationsService, Depends(get_bank_operations_service)],
) -> dict:
    rows = await svc.list_pending_actions()
    return success_response([{"id": r.id, "action_type": r.action_type, "maker_id": r.maker_id} for r in rows])


@router.post("/pending-actions/{action_id}/approve")
async def ops_approve_pending(
    action_id: str,
    request: Request,
    body: PendingActionResolveRequest,
    admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[BankOperationsService, Depends(get_bank_operations_service)],
) -> dict:
    row = await svc.approve_pending_action(
        action_id=action_id,
        checker_id=getattr(admin, "id"),  # type: ignore[arg-type]
        note=body.note,
        ip=get_client_ip(request),
    )
    return success_response({"id": row.id, "status": str(row.status)})


@router.post("/pending-actions/{action_id}/reject")
async def ops_reject_pending(
    action_id: str,
    request: Request,
    body: PendingActionResolveRequest,
    admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[BankOperationsService, Depends(get_bank_operations_service)],
) -> dict:
    row = await svc.reject_pending_action(
        action_id=action_id,
        checker_id=getattr(admin, "id"),  # type: ignore[arg-type]
        note=body.note,
        ip=get_client_ip(request),
    )
    return success_response({"id": row.id, "status": str(row.status)})


@router.post("/users/{user_id}/screening")
async def ops_screening(
    user_id: str,
    request: Request,
    admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[BankOperationsService, Depends(get_bank_operations_service)],
) -> dict:
    row = await svc.run_screening(
        target_user_id=user_id,
        admin_id=getattr(admin, "id"),  # type: ignore[arg-type]
        ip=get_client_ip(request),
    )
    return success_response(
        {
            "id": row.id,
            "pep_hit": row.pep_hit,
            "sanctions_hit": row.sanctions_hit,
            "status": row.status.value if hasattr(row.status, "value") else str(row.status),
        }
    )


@router.get("/data-exports")
async def ops_list_exports(
    _admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[BankOperationsService, Depends(get_bank_operations_service)],
) -> dict:
    rows = await svc.list_data_exports()
    return success_response(
        [
            {
                "id": r.id,
                "user_id": r.user_id,
                "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            }
            for r in rows
        ]
    )


@router.post("/data-exports/{export_id}/process")
async def ops_process_export(
    export_id: str,
    request: Request,
    admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[BankOperationsService, Depends(get_bank_operations_service)],
) -> dict:
    row = await svc.process_data_export(
        export_id=export_id,
        admin_id=getattr(admin, "id"),  # type: ignore[arg-type]
        ip=get_client_ip(request),
    )
    return success_response({"id": row.id, "status": str(row.status)})


@router.post("/webhooks/enqueue")
async def ops_webhook_enqueue(
    body: WebhookEnqueueRequest,
    _admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[BankOperationsService, Depends(get_bank_operations_service)],
) -> dict:
    row = await svc.enqueue_webhook_sample(
        webhook_endpoint_id=body.webhook_endpoint_id,
        event_type=body.event_type,
        body=body.body,
    )
    return success_response({"id": row.id, "status": row.status})


@router.get("/webhook-deliveries")
async def ops_list_webhook_deliveries(
    _admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[BankOperationsService, Depends(get_bank_operations_service)],
) -> dict:
    rows = await svc.list_webhook_deliveries()
    return success_response(
        [
            {"id": r.id, "status": r.status, "event_type": r.event_type, "attempt_count": r.attempt_count}
            for r in rows
        ]
    )


@router.post("/webhook-deliveries/{delivery_id}/retry")
async def ops_retry_webhook(
    delivery_id: str,
    request: Request,
    admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[BankOperationsService, Depends(get_bank_operations_service)],
) -> dict:
    row = await svc.retry_webhook_delivery(
        delivery_id=delivery_id,
        admin_id=getattr(admin, "id"),  # type: ignore[arg-type]
        ip=get_client_ip(request),
    )
    return success_response({"id": row.id, "status": row.status})
