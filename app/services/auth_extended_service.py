from __future__ import annotations

from datetime import datetime, timedelta, timezone

from prisma import Prisma
from prisma.models import User

from app.core.config import settings
from app.core.exceptions import UnauthorizedError, ValidationAppError
from app.core.security import (
    create_access_token,
    hash_opaque_token,
    hash_password,
    new_opaque_token,
    verify_password,
)
from app.repositories.session_token_repository import PasswordResetRepository, RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService


class AuthExtendedService:
    """Refresh sessions, password reset, logout."""

    def __init__(self, prisma: Prisma, audit: AuditService) -> None:
        self._users = UserRepository(prisma)
        self._refresh = RefreshTokenRepository(prisma)
        self._reset = PasswordResetRepository(prisma)
        self._audit = audit

    def _access_for_user(self, user: User) -> str:
        role_claim = user.role.value if hasattr(user.role, "value") else str(user.role)
        return create_access_token(user.id, {"role": role_claim})

    async def login_with_refresh(
        self,
        *,
        email: str,
        password: str,
        ip: str | None,
        user_agent: str | None,
    ) -> tuple[str, str, User]:
        user = await self._users.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid email or password")
        if getattr(user, "is_active", True) is False:
            raise UnauthorizedError("Account suspended")
        access = self._access_for_user(user)
        raw_refresh = new_opaque_token()
        await self._refresh.create(
            user_id=user.id,
            token_hash=hash_opaque_token(raw_refresh),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
            user_agent=user_agent,
            ip_address=ip,
        )
        await self._audit.log(
            user_id=user.id,
            action="USER_LOGIN",
            resource=f"user:{user.id}",
            ip_address=ip,
        )
        return access, raw_refresh, user

    async def refresh_access(self, *, refresh_token: str) -> tuple[str, User]:
        row = await self._refresh.find_valid(hash_opaque_token(refresh_token))
        if row is None:
            raise UnauthorizedError("Invalid or expired refresh token")
        user = await self._users.get_by_id(row.user_id)
        if user is None or getattr(user, "is_active", True) is False:
            raise UnauthorizedError("User no longer valid")
        return self._access_for_user(user), user

    async def logout(self, *, refresh_token: str) -> None:
        await self._refresh.delete_by_hash(hash_opaque_token(refresh_token))

    async def list_sessions(self, user_id: str) -> list[dict]:
        rows = await self._refresh.list_for_user(user_id)
        return [
            {
                "id": r.id,
                "created_at": r.created_at.isoformat(),
                "expires_at": r.expires_at.isoformat(),
                "ip_address": r.ip_address,
                "user_agent": r.user_agent,
            }
            for r in rows
        ]

    async def revoke_session(self, *, user_id: str, session_id: str) -> bool:
        n = await self._refresh.delete_by_id_for_user(token_id=session_id, user_id=user_id)
        return n > 0

    async def forgot_password(self, *, email: str) -> dict:
        user = await self._users.get_by_email(email)
        out: dict = {"message": "If the email exists, reset instructions were sent."}
        if user is None:
            return out
        raw = new_opaque_token()
        await self._reset.create(
            user_id=user.id,
            token_hash=hash_opaque_token(raw),
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.password_reset_expire_minutes),
        )
        if settings.environment.lower() == "development":
            out["reset_token"] = raw
            out["message"] = "Development mode: use reset_token with POST /auth/reset-password"
        return out

    async def reset_password(self, *, token: str, new_password: str) -> None:
        row = await self._reset.find_valid(hash_opaque_token(token))
        if row is None:
            raise ValidationAppError("Invalid or expired reset token")
        await self._users.update_password_hash(row.user_id, hash_password(new_password))
        await self._reset.mark_used(row.id)
