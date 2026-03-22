from __future__ import annotations
from fastapi import APIRouter

from app.utils.response import success_response

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    return success_response({"status": "ok"})
