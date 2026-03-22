"""One-shot demo dataset: rich customer accounts + admin queues (many users, pending KYC/loans).

Run from repo root (backend/) after migrations:

  export DATABASE_URL=postgresql://banksphere:banksphere@127.0.0.1:5433/banksphere
  pip install -r requirements.txt
  python scripts/seed_full_demo.py

See docs/SEED_DEMO.md for login cheatsheet.
"""

from __future__ import annotations

import asyncio
import os
import random
import sys
import uuid
from decimal import Decimal

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS = os.path.join(_ROOT, "scripts")
for _p in (_ROOT, _SCRIPTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bcrypt
import seed_bulk as sb
from prisma import Json, Prisma
from prisma.enums import AccountType, KycStatus, LoanStatus, Role, TransactionKind, TransactionStatus

from app.utils.emi import calculate_emi

DEMO_CUSTOMER_EMAIL = "customer.demo@example.com"
DEMO_CUSTOMER_PASSWORD = b"Demo123456!"


async def _add_txn(
    db: Prisma,
    *,
    idempotency_key: str,
    kind: TransactionKind,
    status: TransactionStatus,
    amount: Decimal,
    from_id: str | None,
    to_id: str | None,
    description: str,
) -> None:
    await db.transaction.create(
        data={
            "idempotency_key": idempotency_key,
            "kind": kind,
            "status": status,
            "amount": amount,
            "from_account_id": from_id,
            "to_account_id": to_id,
            "description": description,
        }
    )


async def enrich_alice(db: Prisma) -> None:
    u = await db.user.find_unique(where={"email": "alice@example.com"})
    if not u:
        return
    await db.user.update(where={"id": u.id}, data={"kyc_status": KycStatus.PENDING})

    accounts = await db.account.find_many(where={"user_id": u.id})
    by_type = {a.type: a for a in accounts}
    sav = by_type.get(AccountType.SAVINGS)
    cur = by_type.get(AccountType.CURRENT)
    if not sav or not cur:
        return

    extras: list[tuple[TransactionKind, Decimal, str | None, str | None, str, str]] = [
        (TransactionKind.DEPOSIT, Decimal("2500.00"), None, sav.id, "Payroll — Acme Corp"),
        (TransactionKind.DEPOSIT, Decimal("400.00"), None, sav.id, "Refund — electronics"),
        (TransactionKind.TRANSFER, Decimal("800.00"), sav.id, cur.id, "Transfer to checking"),
        (TransactionKind.WITHDRAW, Decimal("120.00"), cur.id, None, "ATM withdrawal"),
        (TransactionKind.DEPOSIT, Decimal("95.50"), None, cur.id, "Peer payment received"),
        (TransactionKind.TRANSFER, Decimal("300.00"), cur.id, sav.id, "Move to savings"),
        (TransactionKind.WITHDRAW, Decimal("45.00"), sav.id, None, "Debit purchase"),
        (TransactionKind.DEPOSIT, Decimal("2200.00"), None, sav.id, "Payroll — Acme Corp"),
        (TransactionKind.TRANSFER, Decimal("500.00"), sav.id, cur.id, "Rent share"),
        (TransactionKind.DEPOSIT, Decimal("60.00"), None, cur.id, "Cashback reward"),
    ]

    for i, (kind, amt, fid, tid, desc) in enumerate(extras):
        key = f"alice-rich-{u.id}-{i}-{uuid.uuid4().hex[:8]}"
        if kind == TransactionKind.DEPOSIT:
            await db.account.update(where={"id": tid}, data={"balance": {"increment": amt}})
        elif kind == TransactionKind.WITHDRAW:
            await db.account.update(where={"id": fid}, data={"balance": {"decrement": amt}})
        elif kind == TransactionKind.TRANSFER:
            await db.account.update(where={"id": fid}, data={"balance": {"decrement": amt}})
            await db.account.update(where={"id": tid}, data={"balance": {"increment": amt}})
        await _add_txn(db, idempotency_key=key, kind=kind, status=TransactionStatus.SUCCESS, amount=amt, from_id=fid, to_id=tid, description=desc)

    loan_specs = [
        (Decimal("48000"), Decimal("11.25"), 72, LoanStatus.PENDING, "Electric vehicle loan"),
        (Decimal("12000"), Decimal("9.99"), 36, LoanStatus.APPROVED, "Debt consolidation"),
        (Decimal("8500"), Decimal("12.50"), 24, LoanStatus.REJECTED, "Personal line"),
        (Decimal("320000"), Decimal("6.85"), 300, LoanStatus.PENDING, "Home mortgage pre-approval"),
        (Decimal("6500"), Decimal("10.00"), 18, LoanStatus.PENDING, "Medical payment plan"),
    ]
    for principal, rate, months, status, purpose in loan_specs:
        try:
            emi = calculate_emi(principal, rate, months)
            await db.loan.create(
                data={
                    "user_id": u.id,
                    "principal": principal,
                    "annual_rate_pct": rate,
                    "tenure_months": months,
                    "emi": emi,
                    "status": status,
                    "purpose": purpose,
                }
            )
        except ValueError:
            continue

    for msg in (
        "Your savings goal is 65% complete this quarter.",
        "Loan application received — we will notify you when it is reviewed.",
        "New device login from Chrome on macOS.",
    ):
        await db.auditlog.create(
            data={
                "user": {"connect": {"id": u.id}},
                "action": "NOTIFICATION",
                "resource": "demo_seed",
                "details": Json({"message": msg}),
            }
        )

    print("Enriched alice@example.com (transactions, loans, notifications).")


async def ensure_second_demo_customer(db: Prisma) -> None:
    if await db.user.find_unique(where={"email": DEMO_CUSTOMER_EMAIL}):
        print(f"Demo customer {DEMO_CUSTOMER_EMAIL} already exists; skipping create.")
        return

    h = bcrypt.hashpw(DEMO_CUSTOMER_PASSWORD, bcrypt.gensalt()).decode()
    user = await db.user.create(
        data={
            "email": DEMO_CUSTOMER_EMAIL,
            "password_hash": h,
            "full_name": "Morgan Rivers",
            "role": Role.USER,
            "kyc_status": KycStatus.VERIFIED,
        }
    )
    sav = await db.account.create(data={"user_id": user.id, "type": AccountType.SAVINGS, "currency": "USD"})
    cur = await db.account.create(data={"user_id": user.id, "type": AccountType.CURRENT, "currency": "USD"})

    open_s = Decimal("42000.00")
    open_c = Decimal("3100.00")
    await db.account.update(where={"id": sav.id}, data={"balance": open_s})
    await db.account.update(where={"id": cur.id}, data={"balance": open_c})
    await _add_txn(
        db,
        idempotency_key=f"demo-morgan-s-{user.id}",
        kind=TransactionKind.DEPOSIT,
        status=TransactionStatus.SUCCESS,
        amount=open_s,
        from_id=None,
        to_id=sav.id,
        description="Opening deposit (savings)",
    )
    await _add_txn(
        db,
        idempotency_key=f"demo-morgan-c-{user.id}",
        kind=TransactionKind.DEPOSIT,
        status=TransactionStatus.SUCCESS,
        amount=open_c,
        from_id=None,
        to_id=cur.id,
        description="Opening deposit (current)",
    )

    for i in range(14):
        amt = Decimal(str(random.randint(25, 1800))) + Decimal(str(round(random.random(), 2)))
        key = f"morgan-tx-{user.id}-{i}-{uuid.uuid4().hex[:6]}"
        if i % 4 == 0:
            await db.account.update(where={"id": sav.id}, data={"balance": {"increment": amt}})
            await _add_txn(
                db,
                idempotency_key=key,
                kind=TransactionKind.DEPOSIT,
                status=TransactionStatus.SUCCESS,
                amount=amt,
                from_id=None,
                to_id=sav.id,
                description=f"Income / transfer in #{i + 1}",
            )
        elif i % 4 == 1:
            await db.account.update(where={"id": cur.id}, data={"balance": {"increment": amt}})
            await _add_txn(
                db,
                idempotency_key=key,
                kind=TransactionKind.DEPOSIT,
                status=TransactionStatus.SUCCESS,
                amount=amt,
                from_id=None,
                to_id=cur.id,
                description=f"Reimbursement #{i + 1}",
            )
        else:
            x = min(amt, Decimal("900"))
            await db.account.update(where={"id": sav.id}, data={"balance": {"decrement": x}})
            await db.account.update(where={"id": cur.id}, data={"balance": {"increment": x}})
            await _add_txn(
                db,
                idempotency_key=key,
                kind=TransactionKind.TRANSFER,
                status=TransactionStatus.SUCCESS,
                amount=x,
                from_id=sav.id,
                to_id=cur.id,
                description=f"Savings to checking #{i + 1}",
            )

    for principal, rate, months, st, purpose in [
        (Decimal("18000"), Decimal("8.49"), 48, LoanStatus.APPROVED, "Career certification bootcamp"),
        (Decimal("9500"), Decimal("11.00"), 30, LoanStatus.PENDING, "Home appliance bundle"),
    ]:
        emi = calculate_emi(principal, rate, months)
        await db.loan.create(
            data={
                "user_id": user.id,
                "principal": principal,
                "annual_rate_pct": rate,
                "tenure_months": months,
                "emi": emi,
                "status": st,
                "purpose": purpose,
            }
        )

    await db.auditlog.create(
        data={
            "user": {"connect": {"id": user.id}},
            "action": "NOTIFICATION",
            "resource": "demo_seed",
            "details": Json({"message": "Welcome Morgan — your premium trial features are active."}),
        }
    )
    print(f"Created {DEMO_CUSTOMER_EMAIL} (Morgan Rivers) with activity.")


async def boost_admin_queues(db: Prisma) -> None:
    """Extra PENDING loans + KYC backlog for admin UI tables."""
    users = await db.user.find_many(where={"role": Role.USER})
    if len(users) < 5:
        return
    ids = [u.id for u in users]
    random.seed(4242)

    created_loans = 0
    for _ in range(55):
        uid = random.choice(ids)
        principal = Decimal(str(random.randint(3000, 125000)))
        rate = Decimal(str(round(random.uniform(7.0, 17.5), 2)))
        months = random.choice([12, 18, 24, 36, 48, 60, 72])
        try:
            emi = calculate_emi(principal, rate, months)
            await db.loan.create(
                data={
                    "user_id": uid,
                    "principal": principal,
                    "annual_rate_pct": rate,
                    "tenure_months": months,
                    "emi": emi,
                    "status": LoanStatus.PENDING,
                    "purpose": random.choice(
                        [
                            "Working capital",
                            "Wedding expenses",
                            "Education fees",
                            "Travel",
                            "Medical",
                            "Vehicle repair",
                            "Small business",
                        ]
                    ),
                }
            )
            created_loans += 1
        except ValueError:
            continue

    kyc_flips = 0
    skip_kyc = {DEMO_CUSTOMER_EMAIL, "admin@example.com"}
    ver_users = [u for u in users if u.kyc_status == KycStatus.VERIFIED and u.email not in skip_kyc]
    random.shuffle(ver_users)
    for u in ver_users[: min(48, len(ver_users))]:
        await db.user.update(where={"id": u.id}, data={"kyc_status": KycStatus.PENDING})
        kyc_flips += 1

    print(f"Admin queues: +{created_loans} PENDING loans, set {kyc_flips} users to KYC PENDING for review.")


async def main_async() -> None:
    db = Prisma()
    await db.connect()
    try:
        print("=== Full demo seed (customer + admin data) ===\n")
        await sb.seed_bulk_customers(db, target=180)
        print()
        await enrich_alice(db)
        await ensure_second_demo_customer(db)
        await boost_admin_queues(db)
        print()
        print("=== Summary ===")
        print("  Admin UI:  admin@example.com  /  Admin123!@#")
        print("  Customer:  alice@example.com /  User123456!  (busy dashboard)")
        print(f"  Customer:  {DEMO_CUSTOMER_EMAIL} / {DEMO_CUSTOMER_PASSWORD.decode()}  (second profile)")
        print(f"  Bulk:      customer.*****@example.com / {sb.USER_PASSWORD_PLAIN.decode()}")
        print("  Docs:      docs/SEED_DEMO.md")
    finally:
        await db.disconnect()


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
