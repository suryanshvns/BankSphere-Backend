from __future__ import annotations

from decimal import Decimal

from prisma import Prisma
from prisma.enums import LedgerSide, TransactionKind, TransactionStatus
from prisma.models import Transaction


GL_CLEARING_ASSET = "11111111-1111-1111-1111-111111111101"
GL_CUSTOMER_LIABILITY_POOL = "11111111-1111-1111-1111-111111111102"


class LedgerService:
    """Double-entry postings mirrored to customer balance changes (simplified GL)."""

    def __init__(self, db: Prisma) -> None:
        self._db = db

    async def record_for_transaction(self, txn: Transaction) -> None:
        if txn.status != TransactionStatus.SUCCESS:
            return
        kind = txn.kind
        amount = txn.amount
        currency = "USD"
        memo = f"{kind} {txn.id}"

        if kind == TransactionKind.DEPOSIT:
            assert txn.to_account_id is not None
            await self._post(
                transaction_id=txn.id,
                memo=memo,
                currency=currency,
                lines=[
                    (GL_CLEARING_ASSET, LedgerSide.DEBIT, amount, None),
                    (GL_CUSTOMER_LIABILITY_POOL, LedgerSide.CREDIT, amount, txn.to_account_id),
                ],
            )
        elif kind == TransactionKind.WITHDRAW:
            assert txn.from_account_id is not None
            await self._post(
                transaction_id=txn.id,
                memo=memo,
                currency=currency,
                lines=[
                    (GL_CUSTOMER_LIABILITY_POOL, LedgerSide.DEBIT, amount, txn.from_account_id),
                    (GL_CLEARING_ASSET, LedgerSide.CREDIT, amount, None),
                ],
            )
        elif kind == TransactionKind.TRANSFER:
            assert txn.from_account_id and txn.to_account_id
            await self._post(
                transaction_id=txn.id,
                memo=memo,
                currency=currency,
                lines=[
                    (GL_CUSTOMER_LIABILITY_POOL, LedgerSide.DEBIT, amount, txn.from_account_id),
                    (GL_CUSTOMER_LIABILITY_POOL, LedgerSide.CREDIT, amount, txn.to_account_id),
                ],
            )
        elif kind == TransactionKind.CARD_CAPTURE:
            assert txn.from_account_id is not None
            await self._post(
                transaction_id=txn.id,
                memo=memo,
                currency=currency,
                lines=[
                    (GL_CUSTOMER_LIABILITY_POOL, LedgerSide.DEBIT, amount, txn.from_account_id),
                    (GL_CLEARING_ASSET, LedgerSide.CREDIT, amount, None),
                ],
            )

    async def record_adhoc(
        self,
        *,
        memo: str,
        currency: str,
        lines: list[tuple[str, LedgerSide, Decimal, str | None]],
    ) -> None:
        await self._post(transaction_id=None, memo=memo, currency=currency, lines=lines)

    async def _post(
        self,
        *,
        transaction_id: str | None,
        memo: str | None,
        currency: str,
        lines: list[tuple[str, LedgerSide, Decimal, str | None]],
    ) -> None:
        deb = sum((l[2] for l in lines if l[1] == LedgerSide.DEBIT), Decimal("0"))
        cred = sum((l[2] for l in lines if l[1] == LedgerSide.CREDIT), Decimal("0"))
        if deb != cred:
            raise ValueError("Unbalanced journal")
        entry = await self._db.journalentry.create(
            data={
                "transaction_id": transaction_id,
                "memo": memo,
                "currency": currency,
            }
        )
        for lid, side, amt, iid in lines:
            await self._db.journalline.create(
                data={
                    "journal_entry_id": entry.id,
                    "ledger_account_id": lid,
                    "side": side,
                    "amount": amt,
                    "internal_account_id": iid,
                }
            )
