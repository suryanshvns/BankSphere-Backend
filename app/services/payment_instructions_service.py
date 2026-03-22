from __future__ import annotations

from decimal import Decimal

from prisma import Prisma
from prisma.enums import PaymentInstructionStatus, PaymentRail, TransactionStatus
from prisma.models import User

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationAppError
from app.repositories.account_repository import AccountRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.services.transaction_service import TransactionService


class PaymentInstructionsService:
    def __init__(self, prisma: Prisma, audit: AuditService, transactions: TransactionService) -> None:
        self._prisma = prisma
        self._audit = audit
        self._tx = transactions
        self._accounts = AccountRepository(prisma)
        self._users = UserRepository(prisma)

    async def create(
        self,
        *,
        user: User,
        from_account_id: str,
        amount: Decimal,
        rail: PaymentRail,
        counterparty: dict | None,
        idempotency_key: str,
        reference: str | None,
        ip: str | None,
    ):
        acc = await self._accounts.get_by_id(from_account_id)
        if acc is None or acc.user_id != user.id:
            raise ForbiddenError("Invalid account")
        if amount <= 0:
            raise ValidationAppError("Amount must be positive")
        row = await self._prisma.paymentinstruction.create(
            data={
                "user_id": user.id,
                "from_account_id": from_account_id,
                "amount": amount,
                "rail": rail,
                "counterparty": counterparty,
                "idempotency_key": idempotency_key,
                "reference": reference,
                "status": PaymentInstructionStatus.PENDING,
            }
        )
        await self._audit.log(
            user_id=user.id,
            action="PAYMENT_INSTRUCTION_CREATED",
            resource=f"payment_instruction:{row.id}",
            details={"rail": str(rail), "amount": str(amount)},
            ip_address=ip,
        )
        return row

    async def list_for_user(self, *, user: User):
        return await self._prisma.paymentinstruction.find_many(
            where={"user_id": user.id},
            order={"created_at": "desc"},
            take=100,
        )

    async def admin_settle(self, *, instruction_id: str, admin_id: str, ip: str | None):
        pi = await self._prisma.paymentinstruction.find_unique(where={"id": instruction_id})
        if pi is None:
            raise NotFoundError("Payment instruction not found")
        if pi.status not in (PaymentInstructionStatus.PENDING, PaymentInstructionStatus.SUBMITTED):
            raise ValidationAppError("Instruction cannot be settled in current status")
        owner = await self._users.get_by_id(pi.user_id)
        if owner is None:
            raise NotFoundError("User not found")
        wt = await self._tx.withdraw(
            user=owner,
            account_id=pi.from_account_id,
            amount=pi.amount,
            idempotency_key=f"pi-settle:{pi.id}",
            description=f"Outbound {pi.rail} settlement",
            client_reference=pi.reference,
            ip=ip,
        )
        if wt.status != TransactionStatus.SUCCESS:
            await self._prisma.paymentinstruction.update(
                where={"id": instruction_id},
                data={
                    "status": PaymentInstructionStatus.FAILED,
                    "failure_reason": (wt.failure_reason or "Withdraw failed")[:500],
                },
            )
            raise ValidationAppError("Could not debit account for settlement")
        await self._prisma.paymentinstruction.update(
            where={"id": instruction_id},
            data={"status": PaymentInstructionStatus.SETTLED},
        )
        await self._audit.log(
            user_id=admin_id,
            action="PAYMENT_INSTRUCTION_SETTLED",
            resource=f"payment_instruction:{instruction_id}",
            ip_address=ip,
        )
        return await self._prisma.paymentinstruction.find_unique(where={"id": instruction_id})

    async def admin_return(self, *, instruction_id: str, admin_id: str, ip: str | None):
        pi = await self._prisma.paymentinstruction.find_unique(where={"id": instruction_id})
        if pi is None:
            raise NotFoundError("Payment instruction not found")
        await self._prisma.paymentinstruction.update(
            where={"id": instruction_id},
            data={"status": PaymentInstructionStatus.RETURNED},
        )
        await self._audit.log(
            user_id=admin_id,
            action="PAYMENT_INSTRUCTION_RETURNED",
            resource=f"payment_instruction:{instruction_id}",
            ip_address=ip,
        )
        return await self._prisma.paymentinstruction.find_unique(where={"id": instruction_id})
