from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from prisma import Prisma
from prisma.enums import CardStatus, RecurringFrequency
from prisma.models import User

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationAppError
from app.repositories.account_repository import AccountRepository
from app.repositories.extensions_repository import BeneficiaryRepository, CardRepository, RecurringPaymentRepository
from app.services.audit_service import AuditService


class CustomerExtensionsService:
    def __init__(self, prisma: Prisma, audit: AuditService) -> None:
        self._accounts = AccountRepository(prisma)
        self._recurring = RecurringPaymentRepository(prisma)
        self._beneficiary = BeneficiaryRepository(prisma)
        self._card = CardRepository(prisma)
        self._audit = audit

    async def _require_own_account(self, user_id: str, account_id: str):
        acc = await self._accounts.get_by_id(account_id)
        if acc is None or not acc.is_active:
            raise NotFoundError("Account not found")
        if acc.user_id != user_id:
            raise ForbiddenError("Not allowed to use this account")
        return acc

    async def create_recurring(
        self,
        *,
        user: User,
        from_account_id: str,
        to_account_id: str,
        amount: Decimal,
        frequency: RecurringFrequency,
        next_run_at: datetime,
        description: str | None,
        ip: str | None,
    ):
        await self._require_own_account(user.id, from_account_id)
        to_acc = await self._accounts.get_by_id(to_account_id)
        if to_acc is None or not to_acc.is_active:
            raise NotFoundError("Destination account not found")
        if amount <= 0:
            raise ValidationAppError("Amount must be positive")
        row = await self._recurring.create(
            user_id=user.id,
            from_account_id=from_account_id,
            to_account_id=to_account_id,
            amount=amount,
            frequency=frequency,
            next_run_at=next_run_at,
            description=description,
        )
        await self._audit.log(
            user_id=user.id,
            action="RECURRING_CREATED",
            resource=f"recurring:{row.id}",
            details={"amount": str(amount), "frequency": frequency.value if hasattr(frequency, "value") else str(frequency)},
            ip_address=ip,
        )
        return row

    async def list_recurring(self, *, user: User):
        return await self._recurring.list_for_user(user.id)

    async def set_recurring_active(self, *, user: User, recurring_id: str, active: bool, ip: str | None):
        row = await self._recurring.get_owned(recurring_id, user.id)
        if row is None:
            raise NotFoundError("Recurring payment not found")
        updated = await self._recurring.update_active(recurring_id, active=active)
        await self._audit.log(
            user_id=user.id,
            action="RECURRING_ACTIVE_SET",
            resource=f"recurring:{recurring_id}",
            details={"active": active},
            ip_address=ip,
        )
        return updated

    async def create_beneficiary(
        self, *, user: User, display_name: str, beneficiary_account_id: str, ip: str | None
    ):
        target = await self._accounts.get_by_id(beneficiary_account_id)
        if target is None or not target.is_active:
            raise NotFoundError("Beneficiary account not found")
        if target.user_id == user.id:
            raise ValidationAppError("Use another user's account as beneficiary")
        row = await self._beneficiary.create(
            user_id=user.id,
            display_name=display_name,
            beneficiary_account_id=beneficiary_account_id,
        )
        await self._audit.log(
            user_id=user.id,
            action="BENEFICIARY_CREATED",
            resource=f"beneficiary:{row.id}",
            details={"display_name": display_name},
            ip_address=ip,
        )
        return row

    async def list_beneficiaries(self, *, user: User):
        return await self._beneficiary.list_for_user(user.id)

    async def delete_beneficiary(self, *, user: User, beneficiary_id: str, ip: str | None):
        row = await self._beneficiary.get_owned(beneficiary_id, user.id)
        if row is None:
            raise NotFoundError("Beneficiary not found")
        await self._beneficiary.delete_owned(beneficiary_id, user.id)
        await self._audit.log(
            user_id=user.id,
            action="BENEFICIARY_DELETED",
            resource=f"beneficiary:{beneficiary_id}",
            ip_address=ip,
        )

    async def create_card(self, *, user: User, label: str, last4: str, ip: str | None):
        if len(last4) != 4 or not last4.isdigit():
            raise ValidationAppError("last4 must be exactly 4 digits")
        row = await self._card.create(user_id=user.id, label=label, last4=last4)
        await self._audit.log(
            user_id=user.id,
            action="CARD_CREATED",
            resource=f"card:{row.id}",
            details={"label": label},
            ip_address=ip,
        )
        return row

    async def list_cards(self, *, user: User):
        return await self._card.list_for_user(user.id)

    async def set_card_frozen(self, *, user: User, card_id: str, is_frozen: bool, ip: str | None):
        row = await self._card.get_owned(card_id, user.id)
        if row is None:
            raise NotFoundError("Card not found")
        if row.status != CardStatus.ACTIVE and not is_frozen:
            raise ValidationAppError("Cannot unfreeze a non-active card")
        updated = await self._card.update_frozen(card_id, is_frozen=is_frozen)
        await self._audit.log(
            user_id=user.id,
            action="CARD_FROZEN_SET",
            resource=f"card:{card_id}",
            details={"is_frozen": is_frozen},
            ip_address=ip,
        )
        return updated

    async def cancel_card(self, *, user: User, card_id: str, ip: str | None):
        row = await self._card.get_owned(card_id, user.id)
        if row is None:
            raise NotFoundError("Card not found")
        updated = await self._card.update_status(card_id, status=CardStatus.CANCELLED)
        await self._audit.log(
            user_id=user.id,
            action="CARD_CANCELLED",
            resource=f"card:{card_id}",
            ip_address=ip,
        )
        return updated
