#!/usr/bin/env python3
"""Seed default users on first startup. Does not overwrite existing accounts."""
import asyncio
import sys
import uuid
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from fastapi_users.password import PasswordHelper

from app.db.session import AsyncSessionLocal
from app.db.models import User

USERS = [
    {
        "email": "admin@localhost.local",
        "password": "adminpassword",
        "is_superuser": True,
    },
    {
        "email": "stock_user@localhost.local",
        "password": "stockpassword",
        "is_superuser": False,
    },
]


async def main() -> None:
    helper = PasswordHelper()

    async with AsyncSessionLocal() as session:
        for spec in USERS:
            result = await session.execute(select(User).where(User.email == spec["email"]))
            if result.scalar_one_or_none():
                print(f"  exists → {spec['email']}")
                continue

            session.add(
                User(
                    id=uuid.uuid4(),
                    email=spec["email"],
                    hashed_password=helper.hash(spec["password"]),
                    is_active=True,
                    is_superuser=spec["is_superuser"],
                    is_verified=True,
                )
            )
            print(f"  created → {spec['email']} (superuser={spec['is_superuser']})")

        await session.commit()

    print("\nDefault credentials (change after first login):")
    for spec in USERS:
        print(f"  {spec['email']} / {spec['password']}")


if __name__ == "__main__":
    asyncio.run(main())
