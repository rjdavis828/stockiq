#!/usr/bin/env python3
"""Create or reset the superuser account."""
import asyncio
import sys
import uuid
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select, update
from fastapi_users.password import PasswordHelper

from app.db.session import AsyncSessionLocal
from app.db.models import User

EMAIL = "super@localhost.local"
PASSWORD = "superpassword"


async def main() -> None:
    helper = PasswordHelper()
    hashed = helper.hash(PASSWORD)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == EMAIL))
        existing = result.scalar_one_or_none()

        if existing:
            await session.execute(
                update(User)
                .where(User.email == EMAIL)
                .values(hashed_password=hashed, is_superuser=True, is_active=True, is_verified=True)
            )
            print(f"Updated existing user → {EMAIL}")
        else:
            session.add(
                User(
                    id=uuid.uuid4(),
                    email=EMAIL,
                    hashed_password=hashed,
                    is_active=True,
                    is_superuser=True,
                    is_verified=True,
                )
            )
            print(f"Created superuser → {EMAIL}")

        await session.commit()

    print(f"  Email:    {EMAIL}")
    print(f"  Password: {PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
