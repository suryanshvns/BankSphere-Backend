from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field

from prisma.enums import PaymentRail


class MfaDisableRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=128)


class MfaConfirmRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=8)


class OutboundPaymentCreateRequest(BaseModel):
    from_account_id: str
    amount: Decimal = Field(..., gt=0)
    rail: PaymentRail
    counterparty: Optional[dict[str, Any]] = None
    idempotency_key: str = Field(..., min_length=8, max_length=200)
    reference: Optional[str] = Field(default=None, max_length=200)


class CardAuthorizeRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    merchant_name: Optional[str] = Field(default=None, max_length=200)
    idempotency_key: str = Field(..., min_length=8, max_length=200)


class CardCaptureRequest(BaseModel):
    authorization_id: str
    from_account_id: str
    idempotency_key: str = Field(..., min_length=8, max_length=200)


class SupportCaseCreateRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=200)
    body: Optional[str] = Field(default=None, max_length=5000)
    priority: int = Field(default=0, ge=0, le=10)


class KybUpsertRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=200)
    registration_number: Optional[str] = Field(default=None, max_length=120)
    country: str = Field(default="US", min_length=2, max_length=2)


class ManualCreditPayload(BaseModel):
    account_id: str
    amount: Decimal = Field(..., gt=0)


class PendingActionCreateRequest(BaseModel):
    action_type: str = Field(..., min_length=1, max_length=80)
    payload: dict[str, Any]


class PendingActionResolveRequest(BaseModel):
    note: Optional[str] = Field(default=None, max_length=500)


class AccountHoldCreateRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    reason: str = Field(..., min_length=1, max_length=500)


class WebhookEnqueueRequest(BaseModel):
    webhook_endpoint_id: str
    event_type: str = Field(..., min_length=1, max_length=120)
    body: dict[str, Any]


class LoanInstallmentPayRequest(BaseModel):
    from_account_id: str


class LoanInstallmentResponse(BaseModel):
    id: str
    loan_id: str
    sequence: int
    due_date: datetime
    amount_due: Decimal
    principal_part: Decimal
    interest_part: Decimal
    status: Any
    paid_at: Optional[datetime]

    model_config = {"from_attributes": True}
