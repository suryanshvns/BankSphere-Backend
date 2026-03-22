from __future__ import annotations
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Request

from app.core.deps import (
    get_admin_service,
    get_loan_service,
    get_user_service,
    require_admin,
)
from app.schemas.account import AccountResponse
from app.schemas.admin import AdminAccountFreezeRequest, AdminUserBlockRequest, AuditLogEntry, PageMeta
from app.schemas.loan import AdminLoanStatusRequest, LoanResponse
from app.schemas.transaction import TransactionResponse
from app.schemas.user import AdminKycUpdateRequest, UserResponse
from app.services.admin_service import AdminService, total_pages
from app.services.loan_service import LoanService
from app.services.user_service import UserService
from app.utils.request_info import get_client_ip
from app.utils.response import success_response

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard/summary")
async def admin_dashboard_summary(
    _admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[AdminService, Depends(get_admin_service)],
) -> dict:
    data = await svc.dashboard_summary()
    return success_response(data)


@router.get("/dashboard/volume-series")
async def admin_volume_series(
    _admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[AdminService, Depends(get_admin_service)],
    days: int = Query(default=30, ge=1, le=90),
) -> dict:
    series = await svc.volume_by_day(days=days)
    return success_response(series)


@router.get("/users")
async def admin_list_users(
    _admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[AdminService, Depends(get_admin_service)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    kyc_status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None, max_length=200),
) -> dict:
    from prisma.enums import KycStatus as KycStatusEnum

    kyc_filter = None
    if kyc_status:
        try:
            kyc_filter = KycStatusEnum(kyc_status)
        except ValueError:
            kyc_filter = None
    rows, total = await svc.list_users(
        page=page,
        page_size=page_size,
        kyc_status=kyc_filter,
        search=search,
    )
    items = [UserResponse.model_validate(u).model_dump(mode="json") for u in rows]
    meta = PageMeta(
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=total_pages(total, page_size),
    )
    return success_response({"items": items, "meta": meta.model_dump()})


@router.patch("/users/{user_id}/kyc")
async def admin_update_kyc(
    user_id: str,
    request: Request,
    body: AdminKycUpdateRequest,
    admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[UserService, Depends(get_user_service)],
) -> dict:
    updated = await svc.admin_set_kyc(
        target_user_id=user_id,
        kyc_status=body.kyc_status,
        admin_id=getattr(admin, "id"),  # type: ignore[arg-type]
        ip=get_client_ip(request),
    )
    return success_response(UserResponse.model_validate(updated).model_dump(mode="json"))


@router.get("/users/{user_id}/detail")
async def admin_user_detail(
    user_id: str,
    _admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[AdminService, Depends(get_admin_service)],
) -> dict:
    u, accs = await svc.get_user_detail(user_id=user_id)
    return success_response(
        {
            "user": UserResponse.model_validate(u).model_dump(mode="json"),
            "accounts": [AccountResponse.model_validate(a).model_dump(mode="json") for a in accs],
        }
    )


@router.patch("/users/{user_id}/block")
async def admin_user_block(
    user_id: str,
    request: Request,
    body: AdminUserBlockRequest,
    admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[AdminService, Depends(get_admin_service)],
) -> dict:
    updated = await svc.set_user_blocked(
        target_user_id=user_id,
        blocked=body.blocked,
        admin_id=getattr(admin, "id"),  # type: ignore[arg-type]
        ip=get_client_ip(request),
    )
    return success_response(UserResponse.model_validate(updated).model_dump(mode="json"))


@router.post("/accounts/{account_id}/freeze")
async def admin_account_freeze(
    account_id: str,
    request: Request,
    body: AdminAccountFreezeRequest,
    admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[AdminService, Depends(get_admin_service)],
) -> dict:
    updated = await svc.freeze_account(
        account_id=account_id,
        frozen=body.frozen,
        admin_id=getattr(admin, "id"),  # type: ignore[arg-type]
        ip=get_client_ip(request),
    )
    return success_response(AccountResponse.model_validate(updated).model_dump(mode="json"))


@router.get("/transactions")
async def admin_list_transactions(
    _admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[AdminService, Depends(get_admin_service)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None),
) -> dict:
    from prisma.enums import TransactionStatus as TS

    st = None
    if status:
        try:
            st = TS(status)
        except ValueError:
            st = None
    rows, total = await svc.list_transactions(page=page, page_size=page_size, status=st)
    items = [TransactionResponse.model_validate(t).model_dump(mode="json") for t in rows]
    meta = PageMeta(
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=total_pages(total, page_size),
    )
    return success_response({"items": items, "meta": meta.model_dump()})


@router.get("/loans")
async def admin_list_loans(
    _admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[AdminService, Depends(get_admin_service)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None),
) -> dict:
    from prisma.enums import LoanStatus as LS

    st = None
    if status:
        try:
            st = LS(status)
        except ValueError:
            st = None
    rows, total = await svc.list_loans(page=page, page_size=page_size, status=st)
    items = [LoanResponse.model_validate(loan).model_dump(mode="json") for loan in rows]
    meta = PageMeta(
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=total_pages(total, page_size),
    )
    return success_response({"items": items, "meta": meta.model_dump()})


@router.patch("/loans/{loan_id}/status")
async def admin_loan_status(
    loan_id: str,
    request: Request,
    body: AdminLoanStatusRequest,
    admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[LoanService, Depends(get_loan_service)],
) -> dict:
    loan = await svc.admin_set_status(
        loan_id=loan_id,
        status=body.status,
        admin_id=getattr(admin, "id"),  # type: ignore[arg-type]
        ip=get_client_ip(request),
    )
    return success_response(LoanResponse.model_validate(loan).model_dump(mode="json"))


@router.get("/audit-logs")
async def admin_audit_logs(
    _admin: Annotated[object, Depends(require_admin)],
    svc: Annotated[AdminService, Depends(get_admin_service)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    action: Optional[str] = Query(default=None, max_length=120),
) -> dict:
    rows, total = await svc.list_audit_logs(page=page, page_size=page_size, action=action)
    items = [AuditLogEntry.model_validate(row).model_dump(mode="json") for row in rows]
    meta = PageMeta(
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=total_pages(total, page_size),
    )
    return success_response({"items": items, "meta": meta.model_dump()})
