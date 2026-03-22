from __future__ import annotations
from datetime import datetime
from decimal import Decimal

from prisma import Prisma
from prisma.enums import CardAuthorizationStatus, CardStatus, TransactionKind, TransactionStatus
from prisma.errors import UniqueViolationError
from prisma.models import Account, Transaction, User

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationAppError
from app.repositories.account_repository import AccountRepository
from app.repositories.transaction_repository import TransactionRepository
from app.services.audit_service import AuditService
from app.services.ledger_service import LedgerService
from app.utils.enums import enum_or_str


def _frozen_check(acc: Account | None) -> None:
    if acc is not None and getattr(acc, "is_frozen", False):
        raise ValidationAppError("Account is frozen")


def _available_balance(acc: Account) -> Decimal:
    hb = getattr(acc, "hold_balance", None)
    if hb is None:
        hb = Decimal("0")
    return acc.balance - hb


class TransactionService:
    def __init__(self, prisma: Prisma, audit: AuditService) -> None:
        self._prisma = prisma
        self._audit = audit

    async def _existing_idempotent(self, key: str) -> Transaction | None:
        return await TransactionRepository(self._prisma).find_by_idempotency_key(key)

    async def deposit(
        self,
        *,
        user: User,
        account_id: str,
        amount: Decimal,
        idempotency_key: str,
        description: str | None,
        client_reference: str | None,
        ip: str | None,
    ) -> Transaction:
        existing = await self._existing_idempotent(idempotency_key)
        if existing:
            return existing
        try:
            async with self._prisma.tx() as tx:
                arepo = AccountRepository(tx)
                trepo = TransactionRepository(tx)
                acc = await arepo.get_by_id(account_id)
                if acc is None or not acc.is_active:
                    raise NotFoundError("Account not found")
                _frozen_check(acc)
                if acc.user_id != user.id:
                    raise ForbiddenError("Cannot deposit to this account")
                await tx.account.update(
                    where={"id": account_id},
                    data={"balance": {"increment": amount}},
                )
                txn = await trepo.create_final(
                    idempotency_key=idempotency_key,
                    kind=TransactionKind.DEPOSIT,
                    status=TransactionStatus.SUCCESS,
                    amount=amount,
                    from_account_id=None,
                    to_account_id=account_id,
                    description=description,
                    client_reference=client_reference,
                )
                await LedgerService(tx).record_for_transaction(txn)
        except UniqueViolationError:
            replay = await self._existing_idempotent(idempotency_key)
            if replay:
                return replay
            raise
        await self._audit.log(
            user_id=user.id,
            action="TX_DEPOSIT",
            resource=f"transaction:{txn.id}",
            details={"amount": str(amount), "account_id": account_id},
            ip_address=ip,
        )
        await self._audit.notify_user(
            user_id=user.id,
            message=f"Deposit of {amount} to account {account_id} completed.",
        )
        return txn

    async def withdraw(
        self,
        *,
        user: User,
        account_id: str,
        amount: Decimal,
        idempotency_key: str,
        description: str | None,
        client_reference: str | None,
        ip: str | None,
    ) -> Transaction:
        existing = await self._existing_idempotent(idempotency_key)
        if existing:
            return existing
        try:
            async with self._prisma.tx() as tx:
                arepo = AccountRepository(tx)
                trepo = TransactionRepository(tx)
                acc = await arepo.get_by_id(account_id)
                if acc is None or not acc.is_active:
                    raise NotFoundError("Account not found")
                _frozen_check(acc)
                if acc.user_id != user.id:
                    raise ForbiddenError("Cannot withdraw from this account")
                if _available_balance(acc) < amount:
                    failed = await trepo.create_final(
                        idempotency_key=idempotency_key,
                        kind=TransactionKind.WITHDRAW,
                        status=TransactionStatus.FAILED,
                        amount=amount,
                        from_account_id=account_id,
                        to_account_id=None,
                        description=description,
                        failure_reason="Insufficient balance",
                        client_reference=client_reference,
                    )
                    await self._audit.log(
                        user_id=user.id,
                        action="TX_WITHDRAW_FAILED",
                        resource=f"transaction:{failed.id}",
                        details={"reason": "insufficient_balance", "account_id": account_id},
                        ip_address=ip,
                    )
                    return failed
                await tx.account.update(
                    where={"id": account_id},
                    data={"balance": {"decrement": amount}},
                )
                txn = await trepo.create_final(
                    idempotency_key=idempotency_key,
                    kind=TransactionKind.WITHDRAW,
                    status=TransactionStatus.SUCCESS,
                    amount=amount,
                    from_account_id=account_id,
                    to_account_id=None,
                    description=description,
                    client_reference=client_reference,
                )
                await LedgerService(tx).record_for_transaction(txn)
        except UniqueViolationError:
            replay = await self._existing_idempotent(idempotency_key)
            if replay:
                return replay
            raise
        await self._audit.log(
            user_id=user.id,
            action="TX_WITHDRAW",
            resource=f"transaction:{txn.id}",
            details={"amount": str(amount), "account_id": account_id, "status": enum_or_str(txn.status)},
            ip_address=ip,
        )
        await self._audit.notify_user(
            user_id=user.id,
            message=f"Withdrawal of {amount} from account {account_id} completed.",
        )
        return txn

    async def transfer(
        self,
        *,
        user: User,
        from_account_id: str,
        to_account_id: str,
        amount: Decimal,
        idempotency_key: str,
        description: str | None,
        client_reference: str | None,
        ip: str | None,
    ) -> Transaction:
        if from_account_id == to_account_id:
            raise ValidationAppError("Cannot transfer to the same account")
        existing = await self._existing_idempotent(idempotency_key)
        if existing:
            return existing
        try:
            async with self._prisma.tx() as tx:
                arepo = AccountRepository(tx)
                trepo = TransactionRepository(tx)
                from_acc = await arepo.get_by_id(from_account_id)
                to_acc = await arepo.get_by_id(to_account_id)
                if from_acc is None or not from_acc.is_active:
                    raise NotFoundError("Source account not found")
                if to_acc is None or not to_acc.is_active:
                    raise NotFoundError("Destination account not found")
                _frozen_check(from_acc)
                _frozen_check(to_acc)
                if from_acc.user_id != user.id:
                    raise ForbiddenError("Cannot transfer from this account")
                if _available_balance(from_acc) < amount:
                    failed = await trepo.create_final(
                        idempotency_key=idempotency_key,
                        kind=TransactionKind.TRANSFER,
                        status=TransactionStatus.FAILED,
                        amount=amount,
                        from_account_id=from_account_id,
                        to_account_id=to_account_id,
                        description=description,
                        failure_reason="Insufficient balance",
                        client_reference=client_reference,
                    )
                    await self._audit.log(
                        user_id=user.id,
                        action="TX_TRANSFER_FAILED",
                        resource=f"transaction:{failed.id}",
                        details={"reason": "insufficient_balance"},
                        ip_address=ip,
                    )
                    return failed
                await tx.account.update(
                    where={"id": from_account_id},
                    data={"balance": {"decrement": amount}},
                )
                await tx.account.update(
                    where={"id": to_account_id},
                    data={"balance": {"increment": amount}},
                )
                txn = await trepo.create_final(
                    idempotency_key=idempotency_key,
                    kind=TransactionKind.TRANSFER,
                    status=TransactionStatus.SUCCESS,
                    amount=amount,
                    from_account_id=from_account_id,
                    to_account_id=to_account_id,
                    description=description,
                    client_reference=client_reference,
                )
                await LedgerService(tx).record_for_transaction(txn)
        except UniqueViolationError:
            replay = await self._existing_idempotent(idempotency_key)
            if replay:
                return replay
            raise
        await self._audit.log(
            user_id=user.id,
            action="TX_TRANSFER",
            resource=f"transaction:{txn.id}",
            details={
                "amount": str(amount),
                "from": from_account_id,
                "to": to_account_id,
                "status": enum_or_str(txn.status),
            },
            ip_address=ip,
        )
        await self._audit.notify_user(
            user_id=user.id,
            message=f"Transfer of {amount} to account {to_account_id} completed.",
        )
        return txn

    async def get_transaction(self, *, user: User, transaction_id: str) -> Transaction:
        trepo = TransactionRepository(self._prisma)
        txn = await trepo.get_by_id(transaction_id)
        if txn is None:
            raise NotFoundError("Transaction not found")
        ids = await self._user_account_ids(user.id)
        if txn.from_account_id not in ids and txn.to_account_id not in ids:
            raise ForbiddenError("Not allowed to view this transaction")
        return txn

    async def list_transactions(
        self,
        *,
        user: User,
        account_id: str | None = None,
        kind: TransactionKind | None = None,
        status: TransactionStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int = 0,
        take: int = 50,
    ) -> tuple[list[Transaction], int]:
        ids = await self._user_account_ids(user.id)
        if account_id is not None:
            if account_id not in ids:
                raise ForbiddenError("Invalid account filter")
            ids = [account_id]
        repo = TransactionRepository(self._prisma)
        n = await repo.count_for_accounts(
            ids,
            kind=kind,
            status=status,
            created_after=date_from,
            created_before=date_to,
        )
        rows = await repo.list_for_accounts(
            ids,
            skip=skip,
            take=take,
            kind=kind,
            status=status,
            created_after=date_from,
            created_before=date_to,
        )
        return rows, n

    async def retry_failed(
        self,
        *,
        user: User,
        failed_transaction_id: str,
        new_idempotency_key: str,
        ip: str | None,
    ) -> Transaction:
        trepo = TransactionRepository(self._prisma)
        prev = await trepo.get_by_id(failed_transaction_id)
        if prev is None:
            raise NotFoundError("Transaction not found")
        ids = await self._user_account_ids(user.id)
        if prev.from_account_id not in ids and prev.to_account_id not in ids:
            raise ForbiddenError("Not allowed")
        if prev.status != TransactionStatus.FAILED:
            raise ValidationAppError("Only failed transactions can be retried")
        if prev.kind == TransactionKind.WITHDRAW:
            assert prev.from_account_id is not None
            return await self.withdraw(
                user=user,
                account_id=prev.from_account_id,
                amount=prev.amount,
                idempotency_key=new_idempotency_key,
                description=prev.description,
                client_reference=prev.client_reference,
                ip=ip,
            )
        if prev.kind == TransactionKind.TRANSFER:
            assert prev.from_account_id and prev.to_account_id
            return await self.transfer(
                user=user,
                from_account_id=prev.from_account_id,
                to_account_id=prev.to_account_id,
                amount=prev.amount,
                idempotency_key=new_idempotency_key,
                description=prev.description,
                client_reference=prev.client_reference,
                ip=ip,
            )
        raise ValidationAppError("Retry not supported for this transaction type")

    async def card_capture(
        self,
        *,
        user: User,
        card_id: str,
        authorization_id: str,
        from_account_id: str,
        idempotency_key: str,
        ip: str | None,
    ) -> Transaction:
        card = await self._prisma.card.find_first(
            where={"id": card_id, "user_id": user.id, "status": CardStatus.ACTIVE}
        )
        if card is None:
            raise ForbiddenError("Card not found or not active")
        auth = await self._prisma.cardauthorization.find_first(
            where={
                "id": authorization_id,
                "card_id": card_id,
                "status": CardAuthorizationStatus.AUTHORIZED,
            }
        )
        if auth is None:
            raise NotFoundError("Authorization not found or already settled")
        amount = auth.amount
        existing = await self._existing_idempotent(idempotency_key)
        if existing:
            return existing
        try:
            async with self._prisma.tx() as tx:
                arepo = AccountRepository(tx)
                trepo = TransactionRepository(tx)
                acc = await arepo.get_by_id(from_account_id)
                if acc is None or not acc.is_active:
                    raise NotFoundError("Account not found")
                _frozen_check(acc)
                if acc.user_id != user.id:
                    raise ForbiddenError("Cannot charge this account")
                if _available_balance(acc) < amount:
                    raise ValidationAppError("Insufficient available balance for capture")
                await tx.account.update(
                    where={"id": from_account_id},
                    data={"balance": {"decrement": amount}},
                )
                txn = await trepo.create_final(
                    idempotency_key=idempotency_key,
                    kind=TransactionKind.CARD_CAPTURE,
                    status=TransactionStatus.SUCCESS,
                    amount=amount,
                    from_account_id=from_account_id,
                    to_account_id=None,
                    description=f"Card capture {card_id}",
                    client_reference=None,
                )
                await tx.cardauthorization.update(
                    where={"id": authorization_id},
                    data={"status": CardAuthorizationStatus.CAPTURED, "capture_txn_id": txn.id},
                )
                await LedgerService(tx).record_for_transaction(txn)
        except UniqueViolationError:
            replay = await self._existing_idempotent(idempotency_key)
            if replay:
                return replay
            raise
        await self._audit.log(
            user_id=user.id,
            action="TX_CARD_CAPTURE",
            resource=f"transaction:{txn.id}",
            details={"amount": str(amount), "card_id": card_id},
            ip_address=ip,
        )
        return txn

    async def _user_account_ids(self, user_id: str) -> list[str]:
        accs = await AccountRepository(self._prisma).list_by_user(user_id)
        return [a.id for a in accs]
