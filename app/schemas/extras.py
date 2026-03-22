from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field

from prisma.enums import CardStatus, RecurringFrequency


class RecurringCreateRequest(BaseModel):
    from_account_id: str
    to_account_id: str
    amount: Decimal = Field(..., gt=0)
    frequency: RecurringFrequency
    next_run_at: datetime
    description: Optional[str] = Field(default=None, max_length=500)


class RecurringPaymentResponse(BaseModel):
    id: str
    user_id: str
    from_account_id: str
    to_account_id: str
    amount: Decimal
    frequency: RecurringFrequency
    next_run_at: datetime
    active: bool
    description: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class RecurringActiveRequest(BaseModel):
    active: bool


class BeneficiaryCreateRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=200)
    beneficiary_account_id: str


class BeneficiaryResponse(BaseModel):
    id: str
    user_id: str
    display_name: str
    beneficiary_account_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CardCreateRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=120)
    last4: str = Field(..., min_length=4, max_length=4, pattern=r"^\d{4}$")


class CardResponse(BaseModel):
    id: str
    user_id: str
    label: str
    last4: str
    status: CardStatus
    is_frozen: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CardFreezeRequest(BaseModel):
    is_frozen: bool


class WebhookCreateRequest(BaseModel):
    url: str = Field(..., min_length=8, max_length=2000)
    secret: Optional[str] = Field(default=None, max_length=500)
    events: Optional[list[Any]] = None


class WebhookResponse(BaseModel):
    id: str
    url: str
    secret: Optional[str]
    events: Optional[Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ApiKeyCreatedResponse(BaseModel):
    id: str
    name: str
    key: str
    created_at: datetime
