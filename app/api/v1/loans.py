from __future__ import annotations
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.deps import get_current_user, get_loan_service
from app.schemas.enterprise import LoanInstallmentPayRequest, LoanInstallmentResponse
from app.schemas.loan import LoanApplyRequest, LoanPrepayRequest, LoanProductResponse, LoanResponse
from app.services.loan_service import LoanService
from app.utils.request_info import get_client_ip
from app.utils.response import success_response

router = APIRouter(prefix="/loans", tags=["loans"])


@router.get("/products")
async def loan_products(
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[LoanService, Depends(get_loan_service)],
) -> dict:
    rows = await svc.list_products()
    data = [LoanProductResponse.model_validate(p).model_dump(mode="json") for p in rows]
    return success_response(data)


@router.post("/apply")
async def apply_loan(
    request: Request,
    body: LoanApplyRequest,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[LoanService, Depends(get_loan_service)],
) -> dict:
    loan = await svc.apply(
        user=user,  # type: ignore[arg-type]
        principal=body.principal,
        annual_rate_pct=body.annual_rate_pct,
        tenure_months=body.tenure_months,
        purpose=body.purpose,
        ip=get_client_ip(request),
    )
    return success_response(LoanResponse.model_validate(loan).model_dump(mode="json"))


@router.get("")
async def list_loans(
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[LoanService, Depends(get_loan_service)],
) -> dict:
    rows = await svc.list_loans(user=user)  # type: ignore[arg-type]
    data = [LoanResponse.model_validate(x).model_dump(mode="json") for x in rows]
    return success_response(data)


@router.get("/{loan_id}/schedule")
async def loan_schedule(
    loan_id: str,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[LoanService, Depends(get_loan_service)],
) -> dict:
    sched = await svc.repayment_schedule(user=user, loan_id=loan_id)  # type: ignore[arg-type]
    return success_response(sched)


@router.get("/{loan_id}/installments")
async def loan_installments(
    loan_id: str,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[LoanService, Depends(get_loan_service)],
) -> dict:
    rows = await svc.list_installments(user=user, loan_id=loan_id)  # type: ignore[arg-type]
    data = [LoanInstallmentResponse.model_validate(x).model_dump(mode="json") for x in rows]
    return success_response(data)


@router.post("/{loan_id}/installments/{sequence}/pay")
async def loan_installment_pay(
    loan_id: str,
    sequence: int,
    request: Request,
    body: LoanInstallmentPayRequest,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[LoanService, Depends(get_loan_service)],
) -> dict:
    row = await svc.pay_installment(
        user=user,  # type: ignore[arg-type]
        loan_id=loan_id,
        sequence=sequence,
        from_account_id=body.from_account_id,
        ip=get_client_ip(request),
    )
    return success_response(LoanInstallmentResponse.model_validate(row).model_dump(mode="json"))


@router.post("/{loan_id}/prepay")
async def loan_prepay(
    loan_id: str,
    request: Request,
    body: LoanPrepayRequest,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[LoanService, Depends(get_loan_service)],
) -> dict:
    loan = await svc.prepay(
        user=user,  # type: ignore[arg-type]
        loan_id=loan_id,
        amount=body.amount,
        ip=get_client_ip(request),
    )
    return success_response(LoanResponse.model_validate(loan).model_dump(mode="json"))


@router.get("/{loan_id}")
async def get_loan(
    loan_id: str,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[LoanService, Depends(get_loan_service)],
) -> dict:
    loan = await svc.get_loan(user=user, loan_id=loan_id)  # type: ignore[arg-type]
    return success_response(LoanResponse.model_validate(loan).model_dump(mode="json"))
