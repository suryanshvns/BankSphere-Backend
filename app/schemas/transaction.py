from __future__ import annotations
from datetime import datetime
from decimal import Decimal

from typing import Optional

from pydantic import BaseModel, Field

from prisma.enums import TransactionKind, TransactionStatus


class DepositRequest(BaseModel):
    account_id: str
    amount: Decimal = Field(..., gt=0)
    idempotency_key: str = Field(..., min_length=8, max_length=200)
    description: Optional[str] = Field(default=None, max_length=500)
    client_reference: Optional[str] = Field(default=None, max_length=200)


class WithdrawRequest(BaseModel):
    account_id: str
    amount: Decimal = Field(..., gt=0)
    idempotency_key: str = Field(..., min_length=8, max_length=200)
    description: Optional[str] = Field(default=None, max_length=500)
    client_reference: Optional[str] = Field(default=None, max_length=200)


class TransferRequest(BaseModel):
    from_account_id: str
    to_account_id: str
    amount: Decimal = Field(..., gt=0)
    idempotency_key: str = Field(..., min_length=8, max_length=200)
    description: Optional[str] = Field(default=None, max_length=500)
    client_reference: Optional[str] = Field(default=None, max_length=200)


class TransactionResponse(BaseModel):
    id: str
    idempotency_key: str
    kind: TransactionKind
    status: TransactionStatus
    amount: Decimal
    from_account_id: Optional[str]
    to_account_id: Optional[str]
    description: Optional[str]
    client_reference: Optional[str] = None
    failure_reason: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class TransactionRetryRequest(BaseModel):
    idempotency_key: str = Field(..., min_length=8, max_length=200)
