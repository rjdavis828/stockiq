import json
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.api.deps import cache_get, cache_set, get_current_user, get_db, get_redis
from app.db.models import Fundamental, Ticker, User
from app.schemas.fundamentals import FundamentalsResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fundamentals", tags=["fundamentals"])

_CACHE_TTL = 3600 * 6  # 6 hours — fundamentals change weekly


@router.get("/{symbol}", response_model=List[FundamentalsResponse])
async def get_fundamentals(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    _user: User = Depends(get_current_user),
):
    cache_key = f"fundamentals:{symbol.upper()}"
    cached = await cache_get(redis, cache_key)
    if cached is not None:
        return cached

    ticker_result = await db.execute(
        select(Ticker).where(Ticker.symbol == symbol.upper())
    )
    ticker = ticker_result.scalar_one_or_none()
    if ticker is None:
        raise HTTPException(status_code=404, detail="Ticker not found")

    result = await db.execute(
        select(Fundamental)
        .where(Fundamental.ticker_id == ticker.id)
        .order_by(Fundamental.period.desc())
        .limit(8)
    )
    rows = result.scalars().all()

    data = [FundamentalsResponse.model_validate(r).model_dump(mode="json") for r in rows]
    await cache_set(redis, cache_key, data, ttl=_CACHE_TTL)
    return data
