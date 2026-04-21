from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis
from app.api.deps import cache_get, cache_set, get_current_user, get_db, get_redis, get_superuser
from app.db.models import Ticker, User
from app.ingestion.tasks import refresh_tickers
from app.schemas.ticker import TickerRead

router = APIRouter(prefix="/tickers", tags=["tickers"])


@router.get("")
async def list_tickers(
    exchange: str | None = Query(None),
    sector: str | None = Query(None),
    min_market_cap: int | None = Query(None),
    active_only: bool = Query(True),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    cache_key = f"tickers:{exchange}:{sector}:{min_market_cap}:{active_only}:{limit}:{offset}"
    cached = await cache_get(redis, cache_key)
    if cached is not None:
        return cached

    base_stmt = select(Ticker)
    if active_only:
        base_stmt = base_stmt.where(Ticker.active.is_(True))
    if exchange:
        base_stmt = base_stmt.where(Ticker.exchange == exchange)
    if sector:
        base_stmt = base_stmt.where(Ticker.sector == sector)
    if min_market_cap is not None:
        base_stmt = base_stmt.where(Ticker.market_cap >= min_market_cap)

    total_result = await db.execute(select(func.count()).select_from(base_stmt.subquery()))
    total = total_result.scalar_one()

    stmt = base_stmt.order_by(Ticker.symbol).limit(limit).offset(offset)
    result = await db.execute(stmt)
    tickers = result.scalars().all()
    items = [TickerRead.model_validate(t).model_dump(mode="json") for t in tickers]
    data = {"items": items, "total": total}
    await cache_set(redis, cache_key, data)
    return data


@router.get("/{symbol}", response_model=TickerRead)
async def get_ticker(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    cache_key = f"ticker:{symbol.upper()}"
    cached = await cache_get(redis, cache_key)
    if cached is not None:
        return cached

    result = await db.execute(select(Ticker).where(Ticker.symbol == symbol.upper()))
    ticker = result.scalar_one_or_none()
    if ticker is None:
        raise HTTPException(status_code=404, detail=f"Ticker {symbol} not found")

    data = TickerRead.model_validate(ticker).model_dump(mode="json")
    await cache_set(redis, cache_key, data)
    return data


@router.post("/refresh", status_code=202)
async def trigger_ticker_refresh(
    _: User = Depends(get_superuser),
):
    refresh_tickers.delay()
    return {"status": "queued"}
