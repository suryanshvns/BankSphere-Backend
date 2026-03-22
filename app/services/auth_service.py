from __future__ import annotations
from prisma import Prisma
from prisma.enums import Role
from prisma.models import User

from app.core.exceptions import UnauthorizedError, ValidationAppError
from app.core.security import create_access_token, hash_password, verify_password
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService


class AuthService:
    def __init__(self, prisma: Prisma, audit: AuditService) -> None:
        self._users = UserRepository(prisma)
        self._audit = audit

    async def signup(self, *, email: str, password: str, full_name: str, ip: str | None) -> User:
        existing = await self._users.get_by_email(email)
        if existing:
            raise ValidationAppError("Email already registered")
        user = await self._users.create(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role=Role.USER,
        )
        await self._audit.log(
            user_id=user.id,
            action="USER_SIGNUP",
            resource=f"user:{user.id}",
            details={"email": email},
            ip_address=ip,
        )
        return user

    async def login(self, *, email: str, password: str, ip: str | None) -> tuple[str, User]:
        user = await self._users.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid email or password")
        if getattr(user, "is_active", True) is False:
            raise UnauthorizedError("Account suspended")
        role_claim = user.role.value if hasattr(user.role, "value") else str(user.role)
        token = create_access_token(user.id, {"role": role_claim})
        await self._audit.log(
            user_id=user.id,
            action="USER_LOGIN",
            resource=f"user:{user.id}",
            ip_address=ip,
        )
        return token, user
