from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from prisma import Json, Prisma
from prisma.enums import DataExportStatus, PendingAdminActionStatus, ScreeningResultStatus
from prisma.models import User

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationAppError
from app.repositories.account_repository import AccountRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.services.transaction_service import TransactionService


class BankOperationsService:
    def __init__(self, prisma: Prisma, audit: AuditService, transactions: TransactionService) -> None:
        self._prisma = prisma
        self._audit = audit
        self._tx = transactions
        self._accounts = AccountRepository(prisma)
        self._users = UserRepository(prisma)

    async def list_ledger_accounts(self):
        return await self._prisma.ledgeraccount.find_many(order={"code": "asc"})

    async def list_journal_entries(self, *, take: int = 50):
        entries = await self._prisma.journalentry.find_many(
            order={"posted_at": "desc"},
            take=take,
        )
        out: list = []
        for e in entries:
            lines = await self._prisma.journalline.find_many(
                where={"journal_entry_id": e.id},
                include={"ledger_account": True},
            )
            setattr(e, "_lines_loaded", lines)
            out.append(e)
        return out

    async def create_account_hold(
        self, *, account_id: str, amount: Decimal, reason: str, admin_id: str, ip: str | None
    ):
        if amount <= 0:
            raise ValidationAppError("Amount must be positive")
        acc = await self._accounts.get_by_id(account_id)
        if acc is None:
            raise NotFoundError("Account not found")
        async with self._prisma.tx() as tx:
            hold = await tx.accounthold.create(
                data={"account_id": account_id, "amount": amount, "reason": reason},
            )
            await tx.account.update(
                where={"id": account_id},
                data={"hold_balance": {"increment": amount}},
            )
        await self._audit.log(
            user_id=admin_id,
            action="ACCOUNT_HOLD_PLACED",
            resource=f"account:{account_id}",
            details={"amount": str(amount)},
            ip_address=ip,
        )
        return hold

    async def release_hold(self, *, hold_id: str, admin_id: str, ip: str | None):
        hold = await self._prisma.accounthold.find_unique(where={"id": hold_id})
        if hold is None:
            raise NotFoundError("Hold not found")
        if hold.released_at is not None:
            raise ValidationAppError("Hold already released")
        async with self._prisma.tx() as tx:
            await tx.accounthold.update(
                where={"id": hold_id},
                data={"released_at": datetime.now(timezone.utc)},
            )
            await tx.account.update(
                where={"id": hold.account_id},
                data={"hold_balance": {"decrement": hold.amount}},
            )
        await self._audit.log(
            user_id=admin_id,
            action="ACCOUNT_HOLD_RELEASED",
            resource=f"account_hold:{hold_id}",
            ip_address=ip,
        )
        return await self._prisma.accounthold.find_unique(where={"id": hold_id})

    async def create_pending_action(
        self, *, maker_id: str, action_type: str, payload: dict, ip: str | None
    ):
        row = await self._prisma.pendingadminaction.create(
            data={
                "maker_id": maker_id,
                "action_type": action_type,
                "payload": Json(payload),
                "status": PendingAdminActionStatus.PENDING,
            }
        )
        await self._audit.log(
            user_id=maker_id,
            action="PENDING_ADMIN_ACTION_CREATED",
            resource=f"pending_action:{row.id}",
            details={"type": action_type},
            ip_address=ip,
        )
        return row

    async def list_pending_actions(self):
        return await self._prisma.pendingadminaction.find_many(
            where={"status": PendingAdminActionStatus.PENDING},
            order={"created_at": "desc"},
        )

    async def approve_pending_action(
        self, *, action_id: str, checker_id: str, note: str | None, ip: str | None
    ):
        act = await self._prisma.pendingadminaction.find_unique(where={"id": action_id})
        if act is None:
            raise NotFoundError("Action not found")
        if act.status != PendingAdminActionStatus.PENDING:
            raise ValidationAppError("Action is not pending")
        if act.maker_id == checker_id:
            raise ValidationAppError("Checker must be a different administrator than the maker")
        payload = act.payload if isinstance(act.payload, dict) else {}
        if act.action_type == "MANUAL_CREDIT":
            account_id = payload.get("account_id")
            amount = Decimal(str(payload.get("amount", "0")))
            if not account_id or amount <= 0:
                raise ValidationAppError("Invalid MANUAL_CREDIT payload")
            acc = await self._accounts.get_by_id(account_id)
            if acc is None:
                raise NotFoundError("Account not found")
            owner = await self._users.get_by_id(acc.user_id)
            if owner is None:
                raise NotFoundError("User not found")
            await self._tx.deposit(
                user=owner,
                account_id=account_id,
                amount=amount,
                idempotency_key=f"manual-credit:{action_id}",
                description="Admin manual credit (maker-checker)",
                client_reference=f"pending_action:{action_id}",
                ip=ip,
            )
        await self._prisma.pendingadminaction.update(
            where={"id": action_id},
            data={
                "status": PendingAdminActionStatus.APPROVED,
                "checker_id": checker_id,
                "resolution_note": note,
                "resolved_at": datetime.now(timezone.utc),
            },
        )
        await self._audit.log(
            user_id=checker_id,
            action="PENDING_ADMIN_ACTION_APPROVED",
            resource=f"pending_action:{action_id}",
            ip_address=ip,
        )
        return await self._prisma.pendingadminaction.find_unique(where={"id": action_id})

    async def reject_pending_action(
        self, *, action_id: str, checker_id: str, note: str | None, ip: str | None
    ):
        act = await self._prisma.pendingadminaction.find_unique(where={"id": action_id})
        if act is None:
            raise NotFoundError("Action not found")
        if act.maker_id == checker_id:
            raise ForbiddenError("Checker must differ from maker")
        await self._prisma.pendingadminaction.update(
            where={"id": action_id},
            data={
                "status": PendingAdminActionStatus.REJECTED,
                "checker_id": checker_id,
                "resolution_note": note,
                "resolved_at": datetime.now(timezone.utc),
            },
        )
        await self._audit.log(
            user_id=checker_id,
            action="PENDING_ADMIN_ACTION_REJECTED",
            resource=f"pending_action:{action_id}",
            ip_address=ip,
        )
        return await self._prisma.pendingadminaction.find_unique(where={"id": action_id})

    async def run_screening(self, *, target_user_id: str, admin_id: str, ip: str | None):
        u = await self._users.get_by_id(target_user_id)
        if u is None:
            raise NotFoundError("User not found")
        name = (u.full_name or "").lower()
        email = (u.email or "").lower()
        pep_hit = "pep" in name or "politician" in name
        sanctions_hit = "sanction" in email or "blocked" in email
        if sanctions_hit:
            status = ScreeningResultStatus.BLOCKED
        elif pep_hit:
            status = ScreeningResultStatus.REVIEW
        else:
            status = ScreeningResultStatus.CLEAR
        row = await self._prisma.screeningcheck.create(
            data={
                "user_id": target_user_id,
                "pep_hit": pep_hit,
                "sanctions_hit": sanctions_hit,
                "status": status,
                "notes": "Automated stub screening",
            }
        )
        await self._audit.log(
            user_id=admin_id,
            action="SCREENING_RUN",
            resource=f"user:{target_user_id}",
            details={"status": status.value if hasattr(status, "value") else str(status)},
            ip_address=ip,
        )
        return row

    async def list_data_exports(self):
        return await self._prisma.dataexportrequest.find_many(
            order={"created_at": "desc"},
            take=100,
        )

    async def process_data_export(self, *, export_id: str, admin_id: str, ip: str | None):
        req = await self._prisma.dataexportrequest.find_unique(where={"id": export_id})
        if req is None:
            raise NotFoundError("Export request not found")
        u = await self._users.get_by_id(req.user_id)
        if u is None:
            raise NotFoundError("User missing")
        accounts = await self._prisma.account.find_many(where={"user_id": u.id})
        loans = await self._prisma.loan.find_many(where={"user_id": u.id})
        acc_ids = [a.id for a in accounts]
        if acc_ids:
            txs = await self._prisma.transaction.find_many(
                where={
                    "OR": [
                        {"from_account_id": {"in": acc_ids}},
                        {"to_account_id": {"in": acc_ids}},
                    ]
                },
                take=500,
                order={"created_at": "desc"},
            )
        else:
            txs = []
        payload = {
            "user": {"id": u.id, "email": u.email, "full_name": u.full_name, "kyc_status": str(u.kyc_status)},
            "accounts": [{"id": a.id, "balance": str(a.balance), "currency": a.currency} for a in accounts],
            "loans": [{"id": l.id, "principal": str(l.principal), "status": str(l.status)} for l in loans],
            "transactions_sample": [
                {"id": t.id, "kind": str(t.kind), "amount": str(t.amount), "status": str(t.status)} for t in txs
            ],
        }
        await self._prisma.dataexportrequest.update(
            where={"id": export_id},
            data={
                "status": DataExportStatus.READY,
                "result_json": Json(payload),
                "completed_at": datetime.now(timezone.utc),
            },
        )
        await self._audit.log(
            user_id=admin_id,
            action="DATA_EXPORT_PROCESSED",
            resource=f"data_export:{export_id}",
            ip_address=ip,
        )
        return await self._prisma.dataexportrequest.find_unique(where={"id": export_id})

    async def list_webhook_deliveries(self):
        return await self._prisma.webhookdelivery.find_many(
            order={"created_at": "desc"},
            take=100,
        )

    async def enqueue_webhook_sample(self, *, webhook_endpoint_id: str, event_type: str, body: dict):
        return await self._prisma.webhookdelivery.create(
            data={
                "webhook_endpoint_id": webhook_endpoint_id,
                "event_type": event_type,
                "body": Json(body),
                "status": "PENDING",
            }
        )

    async def retry_webhook_delivery(self, *, delivery_id: str, admin_id: str, ip: str | None):
        d = await self._prisma.webhookdelivery.find_unique(where={"id": delivery_id})
        if d is None:
            raise NotFoundError("Delivery not found")
        nxt = d.attempt_count + 1
        await self._prisma.webhookdelivery.update(
            where={"id": delivery_id},
            data={
                "status": "SUCCESS",
                "attempt_count": nxt,
                "last_error": None,
            },
        )
        await self._audit.log(
            user_id=admin_id,
            action="WEBHOOK_DELIVERY_RETRIED",
            resource=f"webhook_delivery:{delivery_id}",
            ip_address=ip,
        )
        return await self._prisma.webhookdelivery.find_unique(where={"id": delivery_id})
