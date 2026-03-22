from __future__ import annotations

from decimal import Decimal

from prisma import Prisma
from prisma.enums import CardAuthorizationStatus, CardStatus
from prisma.models import User

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationAppError
from app.services.audit_service import AuditService


class CardAuthService:
    def __init__(self, prisma: Prisma, audit: AuditService) -> None:
        self._prisma = prisma
        self._audit = audit

    async def authorize(
        self,
        *,
        user: User,
        card_id: str,
        amount: Decimal,
        merchant_name: str | None,
        idempotency_key: str,
        ip: str | None,
    ):
        card = await self._prisma.card.find_first(
            where={"id": card_id, "user_id": user.id, "status": CardStatus.ACTIVE}
        )
        if card is None:
            raise NotFoundError("Card not found")
        if getattr(card, "is_frozen", False):
            raise ValidationAppError("Card is frozen")
        if amount <= 0:
            raise ValidationAppError("Amount must be positive")
        row = await self._prisma.cardauthorization.create(
            data={
                "card_id": card_id,
                "amount": amount,
                "merchant_name": merchant_name,
                "idempotency_key": idempotency_key,
                "status": CardAuthorizationStatus.AUTHORIZED,
            }
        )
        await self._audit.log(
            user_id=user.id,
            action="CARD_AUTH_CREATED",
            resource=f"card_auth:{row.id}",
            details={"amount": str(amount)},
            ip_address=ip,
        )
        return row

    async def reverse(self, *, user: User, authorization_id: str, ip: str | None):
        auth = await self._prisma.cardauthorization.find_unique(where={"id": authorization_id})
        if auth is None:
            raise NotFoundError("Authorization not found")
        card = await self._prisma.card.find_first(where={"id": auth.card_id, "user_id": user.id})
        if card is None:
            raise ForbiddenError("Not allowed")
        if auth.status != CardAuthorizationStatus.AUTHORIZED:
            raise ValidationAppError("Only authorized holds can be reversed")
        await self._prisma.cardauthorization.update(
            where={"id": authorization_id},
            data={"status": CardAuthorizationStatus.REVERSED},
        )
        await self._audit.log(
            user_id=user.id,
            action="CARD_AUTH_REVERSED",
            resource=f"card_auth:{authorization_id}",
            ip_address=ip,
        )
        return await self._prisma.cardauthorization.find_unique(where={"id": authorization_id})
