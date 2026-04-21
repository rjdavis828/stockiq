import json
from collections.abc import AsyncGenerator
from typing import Any

import redis.asyncio as aioredis
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_active_user, current_superuser
from app.config import settings
from app.db.models import User
from app.db.session import get_db

__all__ = [
    "get_db",
    "get_redis",
    "get_current_user",
    "get_superuser",
]


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


async def cache_get(redis: aioredis.Redis, key: str) -> Any | None:
    raw = await redis.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def cache_set(redis: aioredis.Redis, key: str, value: Any, ttl: int | None = None) -> None:
    ttl = ttl or settings.cache_ttl_seconds
    await redis.set(key, json.dumps(value, default=str), ex=ttl)


get_current_user = current_active_user
get_superuser = current_superuser
