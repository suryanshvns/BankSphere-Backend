from __future__ import annotations
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from prisma import Prisma
from prisma.enums import LedgerSide, LoanInstallmentStatus, LoanStatus
from prisma.models import Loan, User

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationAppError
from app.repositories.account_repository import AccountRepository
from app.repositories.extensions_repository import LoanProductRepository
from app.repositories.loan_repository import LoanRepository
from app.services.audit_service import AuditService
from app.services.ledger_service import GL_CLEARING_ASSET, GL_CUSTOMER_LIABILITY_POOL, LedgerService
from app.utils.amortization import build_loan_schedule
from app.utils.emi import calculate_emi
from app.utils.enums import enum_or_str


class LoanService:
    def __init__(self, prisma: Prisma, audit: AuditService) -> None:
        self._prisma = prisma
        self._loans = LoanRepository(prisma)
        self._products = LoanProductRepository(prisma)
        self._audit = audit

    async def apply(
        self,
        *,
        user: User,
        principal: Decimal,
        annual_rate_pct: Decimal,
        tenure_months: int,
        purpose: str | None,
        ip: str | None,
    ) -> Loan:
        try:
            emi = calculate_emi(principal, annual_rate_pct, tenure_months)
        except ValueError as exc:
            raise ValidationAppError(str(exc)) from exc
        loan = await self._loans.create(
            user_id=user.id,
            principal=principal,
            annual_rate_pct=annual_rate_pct,
            tenure_months=tenure_months,
            emi=emi,
            purpose=purpose,
        )
        await self._audit.log(
            user_id=user.id,
            action="LOAN_APPLIED",
            resource=f"loan:{loan.id}",
            details={"principal": str(principal), "emi": str(emi)},
            ip_address=ip,
        )
        await self._audit.notify_user(
            user_id=user.id,
            message=f"Loan application {loan.id} submitted and is pending review.",
        )
        return loan

    async def get_loan(self, *, user: User, loan_id: str) -> Loan:
        loan = await self._loans.get_by_id(loan_id)
        if loan is None:
            raise NotFoundError("Loan not found")
        if loan.user_id != user.id:
            raise ForbiddenError("Not allowed to access this loan")
        return loan

    async def list_loans(self, *, user: User) -> list[Loan]:
        return await self._loans.list_by_user(user.id)

    async def admin_set_status(self, *, loan_id: str, status: LoanStatus, admin_id: str, ip: str | None) -> Loan:
        if status not in (LoanStatus.APPROVED, LoanStatus.REJECTED):
            raise ValidationAppError("Admin may only approve or reject loans")
        loan = await self._loans.get_by_id(loan_id)
        if loan is None:
            raise NotFoundError("Loan not found")
        if loan.status != LoanStatus.PENDING:
            raise ValidationAppError("Loan is no longer pending")
        schedule = build_loan_schedule(loan.principal, loan.annual_rate_pct, loan.tenure_months)
        base = loan.created_at
        if base.tzinfo is None:
            base = base.replace(tzinfo=timezone.utc)
        async with self._prisma.tx() as tx:
            await tx.loan.update(where={"id": loan_id}, data={"status": status})
            if status == LoanStatus.APPROVED and schedule:
                existing_n = await tx.loaninstallment.count(where={"loan_id": loan_id})
                if existing_n == 0:
                    for i, row in enumerate(schedule):
                        due = base + timedelta(days=30 * (i + 1))
                        await tx.loaninstallment.create(
                            data={
                                "loan_id": loan_id,
                                "sequence": i + 1,
                                "due_date": due,
                                "amount_due": Decimal(row["emi"]),
                                "principal_part": Decimal(row["principal_component"]),
                                "interest_part": Decimal(row["interest_component"]),
                            }
                        )
        updated = await self._loans.get_by_id(loan_id)
        assert updated is not None
        await self._audit.log(
            user_id=admin_id,
            action="LOAN_STATUS_UPDATED",
            resource=f"loan:{loan_id}",
            details={"status": enum_or_str(status)},
            ip_address=ip,
        )
        await self._audit.notify_user(
            user_id=loan.user_id,
            message=f"Your loan {loan_id} was {enum_or_str(status).lower()}.",
        )
        return updated

    async def list_products(self):
        return await self._products.list_all()

    async def repayment_schedule(self, *, user: User, loan_id: str) -> list[dict[str, str]]:
        loan = await self.get_loan(user=user, loan_id=loan_id)
        return build_loan_schedule(loan.principal, loan.annual_rate_pct, loan.tenure_months)

    async def list_installments(self, *, user: User, loan_id: str):
        await self.get_loan(user=user, loan_id=loan_id)
        return await self._prisma.loaninstallment.find_many(
            where={"loan_id": loan_id},
            order={"sequence": "asc"},
        )

    def _available_on_account(self, acc) -> Decimal:
        hb = getattr(acc, "hold_balance", None)
        if hb is None:
            hb = Decimal("0")
        return acc.balance - hb

    async def pay_installment(
        self,
        *,
        user: User,
        loan_id: str,
        sequence: int,
        from_account_id: str,
        ip: str | None,
    ):
        await self.get_loan(user=user, loan_id=loan_id)
        inst = await self._prisma.loaninstallment.find_first(
            where={"loan_id": loan_id, "sequence": sequence}
        )
        if inst is None:
            raise NotFoundError("Installment not found")
        if inst.status == LoanInstallmentStatus.PAID:
            raise ValidationAppError("Installment already paid")
        amount = inst.amount_due
        updated_inst = None
        async with self._prisma.tx() as tx:
            arepo = AccountRepository(tx)
            acc = await arepo.get_by_id(from_account_id)
            if acc is None or not acc.is_active:
                raise NotFoundError("Account not found")
            if acc.user_id != user.id:
                raise ForbiddenError("Invalid account")
            if getattr(acc, "is_frozen", False):
                raise ValidationAppError("Account is frozen")
            if self._available_on_account(acc) < amount:
                raise ValidationAppError("Insufficient available balance")
            await tx.account.update(
                where={"id": from_account_id},
                data={"balance": {"decrement": amount}},
            )
            updated_inst = await tx.loaninstallment.update(
                where={"id": inst.id},
                data={
                    "status": LoanInstallmentStatus.PAID,
                    "paid_at": datetime.now(timezone.utc),
                },
            )
            await LedgerService(tx).record_adhoc(
                memo=f"Loan installment {loan_id} #{sequence}",
                currency=acc.currency,
                lines=[
                    (GL_CUSTOMER_LIABILITY_POOL, LedgerSide.DEBIT, amount, from_account_id),
                    (GL_CLEARING_ASSET, LedgerSide.CREDIT, amount, None),
                ],
            )
        await self._audit.log(
            user_id=user.id,
            action="LOAN_INSTALLMENT_PAID",
            resource=f"loan:{loan_id}",
            details={"sequence": sequence, "amount": str(amount)},
            ip_address=ip,
        )
        assert updated_inst is not None
        return updated_inst

    async def prepay(
        self, *, user: User, loan_id: str, amount: Decimal, ip: str | None
    ) -> Loan:
        loan = await self.get_loan(user=user, loan_id=loan_id)
        if loan.status != LoanStatus.APPROVED:
            raise ValidationAppError("Only approved loans support prepayment")
        if amount <= 0:
            raise ValidationAppError("Amount must be positive")
        new_p = loan.principal - amount
        if new_p < 0:
            new_p = Decimal("0")
        if new_p == 0:
            new_emi = Decimal("0")
        else:
            new_emi = calculate_emi(new_p, loan.annual_rate_pct, loan.tenure_months)
        updated = await self._loans.update_principal_emi(loan_id, principal=new_p, emi=new_emi)
        await self._audit.log(
            user_id=user.id,
            action="LOAN_PREPAY",
            resource=f"loan:{loan_id}",
            details={"prepaid": str(amount), "new_principal": str(new_p)},
            ip_address=ip,
        )
        return updated
