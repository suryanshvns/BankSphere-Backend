from __future__ import annotations
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: str
    message: str
    created_at: datetime
    read_at: Optional[datetime] = None
