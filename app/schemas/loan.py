from __future__ import annotations
from datetime import datetime
from decimal import Decimal

from typing import Optional

from pydantic import BaseModel, Field

from prisma.enums import LoanStatus


class LoanApplyRequest(BaseModel):
    principal: Decimal = Field(..., gt=0)
    annual_rate_pct: Decimal = Field(..., ge=0, le=100)
    tenure_months: int = Field(..., ge=1, le=600)
    purpose: Optional[str] = Field(default=None, max_length=500)


class LoanResponse(BaseModel):
    id: str
    user_id: str
    principal: Decimal
    annual_rate_pct: Decimal
    tenure_months: int
    emi: Decimal
    status: LoanStatus
    purpose: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminLoanStatusRequest(BaseModel):
    status: LoanStatus


class LoanProductResponse(BaseModel):
    id: str
    name: str
    min_principal: Decimal
    max_principal: Decimal
    min_tenure_months: int
    max_tenure_months: int
    annual_rate_pct: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


class LoanPrepayRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
