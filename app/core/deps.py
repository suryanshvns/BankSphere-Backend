from __future__ import annotations
from collections.abc import AsyncGenerator
from typing import Annotated, Optional

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from prisma import Prisma
from prisma.enums import Role

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.repositories.user_repository import UserRepository
from app.services.account_service import AccountService
from app.services.audit_service import AuditService
from app.services.auth_extended_service import AuthExtendedService
from app.services.auth_service import AuthService
from app.services.admin_service import AdminService
from app.services.customer_extensions_service import CustomerExtensionsService
from app.services.integrations_admin_service import IntegrationsAdminService
from app.services.mfa_service import MfaService
from app.services.payment_instructions_service import PaymentInstructionsService
from app.services.card_auth_service import CardAuthService
from app.services.cx_portal_service import CxPortalService
from app.services.bank_operations_service import BankOperationsService
from app.services.loan_service import LoanService
from app.services.notification_service import NotificationService
from app.services.transaction_service import TransactionService
from app.services.user_service import UserService

security_scheme = HTTPBearer(auto_error=False)


async def get_prisma(request: Request) -> AsyncGenerator[Prisma, None]:
    prisma: Prisma = request.app.state.prisma
    yield prisma


async def get_current_user_id(
    request: Request,
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security_scheme)],
) -> str:
    if creds is None or not creds.credentials:
        raise UnauthorizedError("Missing bearer token")
    payload = decode_token(creds.credentials)
    sub = payload.get("sub")
    if not sub or not isinstance(sub, str):
        raise UnauthorizedError("Invalid token subject")
    return sub


async def get_current_user(
    user_id: Annotated[str, Depends(get_current_user_id)],
    prisma: Annotated[Prisma, Depends(get_prisma)],
):
    repo = UserRepository(prisma)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise UnauthorizedError("User no longer exists")
    if getattr(user, "is_active", True) is False:
        raise UnauthorizedError("Account suspended")
    return user


async def require_admin(
    user: Annotated[object, Depends(get_current_user)],
) -> object:
    role = getattr(user, "role", None)
    admin = Role.ADMIN
    is_admin = role == admin or role == getattr(admin, "value", None) or role == "ADMIN"
    if not is_admin:
        raise ForbiddenError("Administrator role required")
    return user


def get_audit_service(prisma: Annotated[Prisma, Depends(get_prisma)]) -> AuditService:
    return AuditService(prisma)


def get_user_service(
    prisma: Annotated[Prisma, Depends(get_prisma)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> UserService:
    return UserService(prisma, audit)


def get_auth_service(
    prisma: Annotated[Prisma, Depends(get_prisma)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> AuthService:
    return AuthService(prisma, audit)


def get_auth_extended_service(
    prisma: Annotated[Prisma, Depends(get_prisma)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> AuthExtendedService:
    return AuthExtendedService(prisma, audit)


def get_account_service(
    prisma: Annotated[Prisma, Depends(get_prisma)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> AccountService:
    return AccountService(prisma, audit)


def get_transaction_service(
    prisma: Annotated[Prisma, Depends(get_prisma)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> TransactionService:
    return TransactionService(prisma, audit)


def get_loan_service(
    prisma: Annotated[Prisma, Depends(get_prisma)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> LoanService:
    return LoanService(prisma, audit)


def get_admin_service(
    prisma: Annotated[Prisma, Depends(get_prisma)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> AdminService:
    return AdminService(prisma, audit)


def get_notification_service(prisma: Annotated[Prisma, Depends(get_prisma)]) -> NotificationService:
    return NotificationService(prisma)


def get_customer_extensions_service(
    prisma: Annotated[Prisma, Depends(get_prisma)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> CustomerExtensionsService:
    return CustomerExtensionsService(prisma, audit)


def get_integrations_admin_service(
    prisma: Annotated[Prisma, Depends(get_prisma)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> IntegrationsAdminService:
    return IntegrationsAdminService(prisma, audit)


def get_mfa_service(prisma: Annotated[Prisma, Depends(get_prisma)]) -> MfaService:
    return MfaService(prisma)


def get_payment_instructions_service(
    prisma: Annotated[Prisma, Depends(get_prisma)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
    transactions: Annotated[TransactionService, Depends(get_transaction_service)],
) -> PaymentInstructionsService:
    return PaymentInstructionsService(prisma, audit, transactions)


def get_card_auth_service(
    prisma: Annotated[Prisma, Depends(get_prisma)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> CardAuthService:
    return CardAuthService(prisma, audit)


def get_cx_portal_service(
    prisma: Annotated[Prisma, Depends(get_prisma)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> CxPortalService:
    return CxPortalService(prisma, audit)


def get_bank_operations_service(
    prisma: Annotated[Prisma, Depends(get_prisma)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
    transactions: Annotated[TransactionService, Depends(get_transaction_service)],
) -> BankOperationsService:
    return BankOperationsService(prisma, audit, transactions)
