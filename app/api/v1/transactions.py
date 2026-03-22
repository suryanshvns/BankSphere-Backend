from __future__ import annotations
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Request

from app.core.deps import get_current_user, get_transaction_service
from app.schemas.admin import PageMeta
from app.schemas.transaction import (
    DepositRequest,
    TransactionResponse,
    TransactionRetryRequest,
    TransferRequest,
    WithdrawRequest,
)
from app.services.admin_service import total_pages
from app.services.transaction_service import TransactionService
from app.utils.request_info import get_client_ip
from app.utils.response import success_response

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("/deposit")
async def deposit(
    request: Request,
    body: DepositRequest,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[TransactionService, Depends(get_transaction_service)],
) -> dict:
    txn = await svc.deposit(
        user=user,  # type: ignore[arg-type]
        account_id=body.account_id,
        amount=body.amount,
        idempotency_key=body.idempotency_key,
        description=body.description,
        client_reference=body.client_reference,
        ip=get_client_ip(request),
    )
    return success_response(TransactionResponse.model_validate(txn).model_dump(mode="json"))


@router.post("/withdraw")
async def withdraw(
    request: Request,
    body: WithdrawRequest,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[TransactionService, Depends(get_transaction_service)],
) -> dict:
    txn = await svc.withdraw(
        user=user,  # type: ignore[arg-type]
        account_id=body.account_id,
        amount=body.amount,
        idempotency_key=body.idempotency_key,
        description=body.description,
        client_reference=body.client_reference,
        ip=get_client_ip(request),
    )
    return success_response(TransactionResponse.model_validate(txn).model_dump(mode="json"))


@router.post("/transfer")
async def transfer(
    request: Request,
    body: TransferRequest,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[TransactionService, Depends(get_transaction_service)],
) -> dict:
    txn = await svc.transfer(
        user=user,  # type: ignore[arg-type]
        from_account_id=body.from_account_id,
        to_account_id=body.to_account_id,
        amount=body.amount,
        idempotency_key=body.idempotency_key,
        description=body.description,
        client_reference=body.client_reference,
        ip=get_client_ip(request),
    )
    return success_response(TransactionResponse.model_validate(txn).model_dump(mode="json"))


@router.get("")
async def list_transactions(
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[TransactionService, Depends(get_transaction_service)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    account_id: Optional[str] = Query(default=None),
    kind: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
) -> dict:
    from prisma.enums import TransactionKind as TK
    from prisma.enums import TransactionStatus as TS

    k = None
    if kind:
        try:
            k = TK(kind)
        except ValueError:
            k = None
    st = None
    if status:
        try:
            st = TS(status)
        except ValueError:
            st = None
    skip = (page - 1) * page_size
    rows, total = await svc.list_transactions(
        user=user,  # type: ignore[arg-type]
        account_id=account_id,
        kind=k,
        status=st,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        take=page_size,
    )
    items = [TransactionResponse.model_validate(t).model_dump(mode="json") for t in rows]
    meta = PageMeta(
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=total_pages(total, page_size),
    )
    return success_response({"items": items, "meta": meta.model_dump()})


@router.post("/{transaction_id}/retry")
async def retry_transaction(
    transaction_id: str,
    request: Request,
    body: TransactionRetryRequest,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[TransactionService, Depends(get_transaction_service)],
) -> dict:
    txn = await svc.retry_failed(
        user=user,  # type: ignore[arg-type]
        failed_transaction_id=transaction_id,
        new_idempotency_key=body.idempotency_key,
        ip=get_client_ip(request),
    )
    return success_response(TransactionResponse.model_validate(txn).model_dump(mode="json"))


@router.get("/{transaction_id}")
async def get_transaction(
    transaction_id: str,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[TransactionService, Depends(get_transaction_service)],
) -> dict:
    txn = await svc.get_transaction(user=user, transaction_id=transaction_id)  # type: ignore[arg-type]
    return success_response(TransactionResponse.model_validate(txn).model_dump(mode="json"))
