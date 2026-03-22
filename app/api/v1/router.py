from __future__ import annotations
from fastapi import APIRouter

from app.api.v1 import (
    accounts,
    admin,
    admin_integrations,
    auth,
    beneficiaries,
    cards,
    health,
    loans,
    notifications,
    platform_admin,
    platform_customer,
    recurring,
    transactions,
    users,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(accounts.router)
api_router.include_router(transactions.router)
api_router.include_router(loans.router)
api_router.include_router(notifications.router)
api_router.include_router(recurring.router)
api_router.include_router(beneficiaries.router)
api_router.include_router(cards.router)
api_router.include_router(admin.router)
api_router.include_router(admin_integrations.router)
api_router.include_router(platform_customer.router)
api_router.include_router(platform_admin.router)
