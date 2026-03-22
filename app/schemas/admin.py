from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field


class AdminUserBlockRequest(BaseModel):
    blocked: bool


class PageMeta(BaseModel):
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    total_items: int
    total_pages: int


class AuditLogEntry(BaseModel):
    id: str
    user_id: Optional[str]
    action: str
    resource: Optional[str]
    details: Optional[dict[str, Any]]
    ip_address: Optional[str]
    read_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminAccountFreezeRequest(BaseModel):
    frozen: bool
