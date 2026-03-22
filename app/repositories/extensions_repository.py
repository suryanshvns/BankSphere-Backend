from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from prisma import Json, Prisma
from prisma.enums import CardStatus, RecurringFrequency
from prisma.models import ApiKey, Beneficiary, Card, LoanProduct, RecurringPayment, WebhookEndpoint


class LoanProductRepository:
    def __init__(self, db: Prisma) -> None:
        self._db = db

    async def list_all(self) -> list[LoanProduct]:
        return await self._db.loanproduct.find_many(order={"name": "asc"})


class RecurringPaymentRepository:
    def __init__(self, db: Prisma) -> None:
        self._db = db

    async def create(
        self,
        *,
        user_id: str,
        from_account_id: str,
        to_account_id: str,
        amount: Decimal,
        frequency: RecurringFrequency,
        next_run_at: datetime,
        description: str | None,
    ) -> RecurringPayment:
        return await self._db.recurringpayment.create(
            data={
                "user_id": user_id,
                "from_account_id": from_account_id,
                "to_account_id": to_account_id,
                "amount": amount,
                "frequency": frequency,
                "next_run_at": next_run_at,
                "description": description,
            }
        )

    async def list_for_user(self, user_id: str) -> list[RecurringPayment]:
        return await self._db.recurringpayment.find_many(
            where={"user_id": user_id},
            order={"next_run_at": "asc"},
        )

    async def get_owned(self, recurring_id: str, user_id: str) -> RecurringPayment | None:
        return await self._db.recurringpayment.find_first(
            where={"id": recurring_id, "user_id": user_id}
        )

    async def update_active(self, recurring_id: str, *, active: bool) -> RecurringPayment:
        return await self._db.recurringpayment.update(
            where={"id": recurring_id},
            data={"active": active},
        )


class BeneficiaryRepository:
    def __init__(self, db: Prisma) -> None:
        self._db = db

    async def create(
        self, *, user_id: str, display_name: str, beneficiary_account_id: str
    ) -> Beneficiary:
        return await self._db.beneficiary.create(
            data={
                "user_id": user_id,
                "display_name": display_name,
                "beneficiary_account_id": beneficiary_account_id,
            }
        )

    async def list_for_user(self, user_id: str) -> list[Beneficiary]:
        return await self._db.beneficiary.find_many(where={"user_id": user_id})

    async def get_owned(self, beneficiary_id: str, user_id: str) -> Beneficiary | None:
        return await self._db.beneficiary.find_first(
            where={"id": beneficiary_id, "user_id": user_id}
        )

    async def delete_owned(self, beneficiary_id: str, user_id: str) -> None:
        await self._db.beneficiary.delete_many(where={"id": beneficiary_id, "user_id": user_id})


class CardRepository:
    def __init__(self, db: Prisma) -> None:
        self._db = db

    async def create(self, *, user_id: str, label: str, last4: str) -> Card:
        return await self._db.card.create(
            data={"user_id": user_id, "label": label, "last4": last4, "status": CardStatus.ACTIVE}
        )

    async def list_for_user(self, user_id: str) -> list[Card]:
        return await self._db.card.find_many(where={"user_id": user_id})

    async def get_owned(self, card_id: str, user_id: str) -> Card | None:
        return await self._db.card.find_first(where={"id": card_id, "user_id": user_id})

    async def update_frozen(self, card_id: str, *, is_frozen: bool) -> Card:
        return await self._db.card.update(where={"id": card_id}, data={"is_frozen": is_frozen})

    async def update_status(self, card_id: str, *, status: CardStatus) -> Card:
        return await self._db.card.update(where={"id": card_id}, data={"status": status})


class WebhookRepository:
    def __init__(self, db: Prisma) -> None:
        self._db = db

    async def create(self, *, url: str, secret: str | None, events: list | dict | None) -> WebhookEndpoint:
        ev = events if events is not None else []
        return await self._db.webhookendpoint.create(
            data={"url": url, "secret": secret, "events": Json(ev)}
        )

    async def list_all(self) -> list[WebhookEndpoint]:
        return await self._db.webhookendpoint.find_many(order={"created_at": "desc"})

    async def delete(self, webhook_id: str) -> None:
        await self._db.webhookendpoint.delete(where={"id": webhook_id})


class ApiKeyRepository:
    def __init__(self, db: Prisma) -> None:
        self._db = db

    async def create(self, *, name: str, key_hash: str) -> ApiKey:
        return await self._db.apikey.create(data={"name": name, "key_hash": key_hash})

    async def list_all(self) -> list[ApiKey]:
        return await self._db.apikey.find_many(order={"created_at": "desc"})

    async def deactivate(self, key_id: str) -> ApiKey:
        return await self._db.apikey.update(where={"id": key_id}, data={"is_active": False})
