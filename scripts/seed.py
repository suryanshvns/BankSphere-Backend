"""Idempotent seed: admin user, demo user, sample accounts (run after migrations)."""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt
from prisma import Json, Prisma
from prisma.enums import AccountType, KycStatus, Role


async def main() -> None:
    db = Prisma()
    await db.connect()
    try:
        if await db.user.find_unique(where={"email": "admin@example.com"}):
            print("Seed skipped: data already present")
            return

        admin_hash = bcrypt.hashpw(b"Admin123!@#", bcrypt.gensalt()).decode()
        admin = await db.user.create(
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

        await db.account.create(
            data={"user_id": user.id, "type": AccountType.SAVINGS, "currency": "USD"}
        )
        await db.account.create(
            data={"user_id": user.id, "type": AccountType.CURRENT, "currency": "USD"}
        )

        await db.auditlog.create(
            data={
                "user": {"connect": {"id": user.id}},
                "action": "NOTIFICATION",
                "resource": "seed",
                "details": Json({"message": "Welcome to BankSphere. Your accounts are ready."}),
            }
        )

        print(f"Seeded admin id={admin.id} (admin@example.com / Admin123!@#)")
        print(f"Seeded user id={user.id} (alice@example.com / User123456!)")
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
