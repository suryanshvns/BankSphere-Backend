from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from prisma.enums import KycStatus, Role


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: Role
    kyc_status: KycStatus
    is_active: bool = True
    phone: Optional[str] = None
    notify_email: bool = True
    notify_push: bool = True
    daily_transfer_max: Optional[Decimal] = None
    daily_atm_max: Optional[Decimal] = None
    mfa_enabled: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=40)
    notify_email: Optional[bool] = None
    notify_push: Optional[bool] = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class UserLimitsUpdateRequest(BaseModel):
    daily_transfer_max: Optional[Decimal] = Field(default=None, ge=0)
    daily_atm_max: Optional[Decimal] = Field(default=None, ge=0)


class UserLimitsResponse(BaseModel):
    daily_transfer_max: Optional[Decimal] = None
    daily_atm_max: Optional[Decimal] = None

    model_config = {"from_attributes": True}


class KycSubmitRequest(BaseModel):
    reference_id: str = Field(..., min_length=1, max_length=120)


class AdminKycUpdateRequest(BaseModel):
    kyc_status: KycStatus
