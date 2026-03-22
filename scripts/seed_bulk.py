"""Bulk seed: ensure base admin/demo user, then at least N realistic customers with accounts, money, loans.

Run after `prisma migrate deploy`. Uses DATABASE_URL from environment.

  pip install -r requirements.txt
  export DATABASE_URL=postgresql://banksphere:banksphere@127.0.0.1:5433/banksphere
  python scripts/seed_bulk.py
  python scripts/seed_bulk.py --target 250   # optional count (default 200)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys
import uuid
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt
from faker import Faker
from prisma import Json, Prisma
from prisma.enums import AccountType, KycStatus, LoanStatus, Role, TransactionKind, TransactionStatus

from app.utils.emi import calculate_emi

DEFAULT_TARGET_USERS = 200
USER_PASSWORD_PLAIN = b"SeedUser123!"
WELCOME_MESSAGE = "Welcome to BankSphere. Your accounts are ready."


async def ensure_base_users(db: Prisma) -> None:
    if await db.user.find_unique(where={"email": "admin@example.com"}):
        return
    admin_hash = bcrypt.hashpw(b"Admin123!@#", bcrypt.gensalt()).decode()
    await db.user.create(
        data={
            "email": "admin@example.com",
            "password_hash": admin_hash,
            "full_name": "Platform Admin",
            "role": Role.ADMIN,
            "kyc_status": KycStatus.VERIFIED,
        }
    )
    user_hash = bcrypt.hashpw(b"User123456!", bcrypt.gensalt()).decode()
    user = await db.user.create(
        data={
            "email": "alice@example.com",
            "password_hash": user_hash,
            "full_name": "Alice Demo",
            "role": Role.USER,
            "kyc_status": KycStatus.PENDING,
        }
    )
    await db.account.create(data={"user_id": user.id, "type": AccountType.SAVINGS, "currency": "USD"})
    await db.account.create(data={"user_id": user.id, "type": AccountType.CURRENT, "currency": "USD"})
    await db.auditlog.create(
        data={
            "user": {"connect": {"id": user.id}},
            "action": "NOTIFICATION",
            "resource": "seed",
            "details": Json({"message": WELCOME_MESSAGE}),
        }
    )
    print("Created base admin@example.com and alice@example.com")


def pick_kyc(fake: Faker) -> KycStatus:
    r = fake.random_int(1, 100)
    if r <= 55:
        return KycStatus.VERIFIED
    if r <= 85:
        return KycStatus.PENDING
    return KycStatus.REJECTED


async def seed_one_customer(
    db: Prisma,
    fake: Faker,
    password_hash: str,
    seq: int,
) -> None:
    full_name = fake.name()
    email = f"customer.{seq:05d}.{uuid.uuid4().hex[:8]}@example.com"
    kyc = pick_kyc(fake)

    user = await db.user.create(
        data={
            "email": email,
            "password_hash": password_hash,
            "full_name": full_name,
            "role": Role.USER,
            "kyc_status": kyc,
        }
    )

    savings = await db.account.create(
        data={"user_id": user.id, "type": AccountType.SAVINGS, "currency": "USD"}
    )
    current = await db.account.create(
        data={"user_id": user.id, "type": AccountType.CURRENT, "currency": "USD"}
    )

    savings_open = Decimal(str(fake.random_int(500, 75000))) + Decimal(
        str(round(fake.pyfloat(min_value=0, max_value=0.99), 2))
    )
    current_open = Decimal(str(fake.random_int(0, 12000))) + Decimal(
        str(round(fake.pyfloat(min_value=0, max_value=0.99), 2))
    )

    await db.account.update(where={"id": savings.id}, data={"balance": savings_open})
    await db.account.update(where={"id": current.id}, data={"balance": current_open})

    dep_key_s = f"seed-sav-{user.id}"
    await db.transaction.create(
        data={
            "idempotency_key": dep_key_s,
            "kind": TransactionKind.DEPOSIT,
            "status": TransactionStatus.SUCCESS,
            "amount": savings_open,
            "from_account_id": None,
            "to_account_id": savings.id,
            "description": "Initial seed deposit (savings)",
        }
    )
    dep_key_c = f"seed-cur-{user.id}"
    await db.transaction.create(
        data={
            "idempotency_key": dep_key_c,
            "kind": TransactionKind.DEPOSIT,
            "status": TransactionStatus.SUCCESS,
            "amount": current_open,
            "from_account_id": None,
            "to_account_id": current.id,
            "description": "Initial seed deposit (current)",
        }
    )

    if random.random() < 0.35 and savings_open > Decimal("50"):
        upper = min(Decimal("5000"), savings_open - Decimal("1"))
        lo = max(50, 1)
        hi = max(lo, int(upper))
        xfer_amt = Decimal(str(fake.random_int(lo, hi)))
        if xfer_amt > 0 and xfer_amt <= savings_open:
            await db.account.update(
                where={"id": savings.id},
                data={"balance": {"decrement": xfer_amt}},
            )
            await db.account.update(
                where={"id": current.id},
                data={"balance": {"increment": xfer_amt}},
            )
            await db.transaction.create(
                data={
                    "idempotency_key": f"seed-xfer-{user.id}",
                    "kind": TransactionKind.TRANSFER,
                    "status": TransactionStatus.SUCCESS,
                    "amount": xfer_amt,
                    "from_account_id": savings.id,
                    "to_account_id": current.id,
                    "description": "Seed transfer savings → current",
                }
            )

    if random.random() < 0.28:
        principal = Decimal(str(fake.random_int(5000, 150000)))
        rate = Decimal(str(round(fake.pyfloat(min_value=6.0, max_value=18.5), 2)))
        months = fake.random_int(12, 84)
        try:
            emi = calculate_emi(principal, rate, months)
            await db.loan.create(
                data={
                    "user_id": user.id,
                    "principal": principal,
                    "annual_rate_pct": rate,
                    "tenure_months": months,
                    "emi": emi,
                    "status": random.choice(
                        [LoanStatus.PENDING, LoanStatus.PENDING, LoanStatus.APPROVED, LoanStatus.REJECTED]
                    ),
                    "purpose": fake.sentence(nb_words=4).rstrip(".")[:500],
                }
            )
        except ValueError:
            pass

    await db.auditlog.create(
        data={
            "user": {"connect": {"id": user.id}},
            "action": "NOTIFICATION",
            "resource": "bulk_seed",
            "details": Json({"message": WELCOME_MESSAGE}),
        }
    )


async def seed_bulk_customers(db: Prisma, target: int) -> dict[str, int]:
    """Ensure at least `target` USER-role rows (including alice). Returns table counts."""
    random.seed(1729)
    Faker.seed(1729)
    fake = Faker()

    await ensure_base_users(db)

    user_count = await db.user.count(where={"role": Role.USER})
    need = max(0, target - user_count)
    if need == 0:
        print(f"Already have {user_count} users with role USER (target {target}). Skipping bulk insert.")
    else:
        print(f"Users with role USER: {user_count}. Creating {need} more to reach {target}…")
        password_hash = bcrypt.hashpw(USER_PASSWORD_PLAIN, bcrypt.gensalt()).decode()

        for i in range(need):
            seq = user_count + i + 1
            await seed_one_customer(db, fake, password_hash, seq)
            if (i + 1) % 25 == 0:
                print(f"  … {i + 1}/{need}")

    final = await db.user.count(where={"role": Role.USER})
    accounts = await db.account.count()
    txns = await db.transaction.count()
    loans = await db.loan.count()
    logs = await db.auditlog.count()
    print("Bulk pass done.")
    print(f"  USER count: {final}")
    print(f"  Account rows: {accounts}")
    print(f"  Transaction rows: {txns}")
    print(f"  Loan rows: {loans}")
    print(f"  AuditLog rows: {logs}")
    print(f"Bulk users share password: {USER_PASSWORD_PLAIN.decode()} (change in production).")
    return {
        "users": final,
        "accounts": accounts,
        "transactions": txns,
        "loans": loans,
        "audit_logs": logs,
    }


async def run(target: int) -> None:
    db = Prisma()
    await db.connect()
    try:
        await seed_bulk_customers(db, target)
    finally:
        await db.disconnect()


def main() -> None:
    p = argparse.ArgumentParser(description="Bulk-seed realistic BankSphere customers.")
    p.add_argument(
        "--target",
        type=int,
        default=DEFAULT_TARGET_USERS,
        help=f"Minimum number of USER-role accounts (default {DEFAULT_TARGET_USERS}).",
    )
    args = p.parse_args()
    if args.target < 2:
        p.error("--target must be at least 2")
    asyncio.run(run(args.target))


if __name__ == "__main__":
    main()
