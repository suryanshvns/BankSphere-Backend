from __future__ import annotations
import csv
import io
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Request, Response

from app.core.deps import get_account_service, get_current_user
from app.schemas.account import AccountCreateRequest, AccountPatchRequest, AccountResponse
from app.schemas.admin import PageMeta
from app.schemas.transaction import TransactionResponse
from app.services.account_service import AccountService
from app.services.admin_service import total_pages
from app.utils.request_info import get_client_ip
from app.utils.response import success_response

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("")
async def create_account(
    request: Request,
    body: AccountCreateRequest,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[AccountService, Depends(get_account_service)],
) -> dict:
    acc = await svc.create_account(
        user=user,  # type: ignore[arg-type]
        account_type=body.type,
        currency=body.currency.upper(),
        ip=get_client_ip(request),
    )
    return success_response(AccountResponse.model_validate(acc).model_dump(mode="json"))


@router.get("")
async def list_accounts(
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[AccountService, Depends(get_account_service)],
) -> dict:
    rows = await svc.list_accounts(user=user)  # type: ignore[arg-type]
    data = [AccountResponse.model_validate(a).model_dump(mode="json") for a in rows]
    return success_response(data)


@router.get("/{account_id}/balance")
async def account_balance(
    account_id: str,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[AccountService, Depends(get_account_service)],
) -> dict:
    snap = await svc.balance_snapshot(user=user, account_id=account_id)  # type: ignore[arg-type]
    return success_response(snap)


@router.get("/{account_id}/statement")
async def account_statement(
    account_id: str,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[AccountService, Depends(get_account_service)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
) -> dict:
    skip = (page - 1) * page_size
    rows, total, acc = await svc.statement_page(
        user=user,  # type: ignore[arg-type]
        account_id=account_id,
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
    return success_response(
        {
            "account": AccountResponse.model_validate(acc).model_dump(mode="json"),
            "items": items,
            "meta": meta.model_dump(),
        }
    )


@router.get("/{account_id}/statement.csv")
async def account_statement_csv(
    account_id: str,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[AccountService, Depends(get_account_service)],
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
) -> Response:
    rows, _acc = await svc.statement_csv_rows(
        user=user,  # type: ignore[arg-type]
        account_id=account_id,
        date_from=date_from,
        date_to=date_to,
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        ["id", "kind", "status", "amount", "from_account_id", "to_account_id", "description", "client_reference", "created_at"]
    )
    for t in rows:
        w.writerow(
            [
                t.id,
                t.kind.value if hasattr(t.kind, "value") else t.kind,
                t.status.value if hasattr(t.status, "value") else t.status,
                str(t.amount),
                t.from_account_id or "",
                t.to_account_id or "",
                t.description or "",
                getattr(t, "client_reference", None) or "",
                t.created_at.isoformat(),
            ]
        )
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="statement-{account_id}.csv"'},
    )


@router.patch("/{account_id}")
async def patch_account(
    account_id: str,
    body: AccountPatchRequest,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[AccountService, Depends(get_account_service)],
) -> dict:
    acc = await svc.update_own_nickname(
        user=user,  # type: ignore[arg-type]
        account_id=account_id,
        nickname=body.nickname,
    )
    return success_response(AccountResponse.model_validate(acc).model_dump(mode="json"))


@router.get("/{account_id}")
async def get_account(
    account_id: str,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[AccountService, Depends(get_account_service)],
) -> dict:
    acc = await svc.get_account(user=user, account_id=account_id)  # type: ignore[arg-type]
    return success_response(AccountResponse.model_validate(acc).model_dump(mode="json"))
