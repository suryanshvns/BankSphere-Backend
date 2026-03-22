from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from prisma.enums import AccountType


class AccountCreateRequest(BaseModel):
    type: AccountType
    currency: str = Field(default="USD", min_length=3, max_length=3)


class AccountResponse(BaseModel):
    id: str
    user_id: str
    type: AccountType
    balance: Decimal
    currency: str
    is_active: bool
    nickname: Optional[str] = None
    is_frozen: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class AccountPatchRequest(BaseModel):
    nickname: Optional[str] = Field(default=None, max_length=120)
