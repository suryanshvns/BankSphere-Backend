from __future__ import annotations

import pyotp

from prisma import Prisma
from prisma.models import User

from app.core.exceptions import UnauthorizedError, ValidationAppError
from app.core.security import verify_password
from app.repositories.user_repository import UserRepository


class MfaService:
    def __init__(self, prisma: Prisma) -> None:
        self._users = UserRepository(prisma)

    async def enroll_start(self, *, user: User) -> dict[str, str]:
        if getattr(user, "mfa_enabled", False):
            raise ValidationAppError("MFA already enabled; disable first to re-enroll")
        secret = pyotp.random_base32()
        await self._users.set_mfa_secret(user.id, secret)
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(name=user.email, issuer_name="BankSphere")
        return {"secret": secret, "otpauth_url": uri}

    async def enroll_confirm(self, *, user: User, code: str) -> User:
        fresh = await self._users.get_by_id(user.id)
        if fresh is None:
            raise ValidationAppError("User not found")
        secret = getattr(fresh, "mfa_totp_secret", None)
        if not secret:
            raise ValidationAppError("Start enrollment first")
        if not pyotp.TOTP(secret).verify(code, valid_window=1):
            raise ValidationAppError("Invalid code")
        return await self._users.set_mfa_enabled(fresh.id, True)

    async def disable(self, *, user: User, password: str) -> User:
        if not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid password")
        return await self._users.clear_mfa(user.id)
