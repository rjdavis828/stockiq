from datetime import date, datetime, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import cache_get, cache_set, get_db, get_redis, get_superuser
from app.db.models import OHLCVDaily, OHLCVIntraday, Ticker, User
from app.ingestion.tasks import ingest_daily_ohlcv
from app.schemas.ohlcv import BackfillRequest, OHLCVDailyRead, OHLCVIntradayRead

router = APIRouter(prefix="/ohlcv", tags=["ohlcv"])


async def _resolve_ticker(symbol: str, db: AsyncSession) -> Ticker:
    result = await db.execute(select(Ticker).where(Ticker.symbol == symbol.upper()))
    ticker = result.scalar_one_or_none()
    if ticker is None:
        raise HTTPException(status_code=404, detail=f"Ticker {symbol} not found")
    return ticker


@router.get("/{symbol}/daily", response_model=list[OHLCVDailyRead])
async def get_daily_bars(
    symbol: str,
    start: date | None = Query(None),
    end: date | None = Query(None),
    limit: int = Query(252, le=2000),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    cache_key = f"ohlcv:daily:{symbol.upper()}:{start}:{end}:{limit}"
    cached = await cache_get(redis, cache_key)
    if cached is not None:
        return cached

    ticker = await _resolve_ticker(symbol, db)
    stmt = select(OHLCVDaily).where(OHLCVDaily.ticker_id == ticker.id)
    if start:
        stmt = stmt.where(OHLCVDaily.date >= start)
    if end:
        stmt = stmt.where(OHLCVDaily.date <= end)
    stmt = stmt.order_by(OHLCVDaily.date.desc()).limit(limit)

    result = await db.execute(stmt)
    bars = result.scalars().all()
    data = [OHLCVDailyRead.model_validate(b).model_dump(mode="json") for b in bars]
    await cache_set(redis, cache_key, data)
    return data


@router.get("/{symbol}/intraday", response_model=list[OHLCVIntradayRead])
async def get_intraday_bars(
    symbol: str,
    timeframe: str = Query("5m"),
    date: date | None = Query(None),
    limit: int = Query(390, le=2000),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    cache_key = f"ohlcv:intraday:{symbol.upper()}:{timeframe}:{date}:{limit}"
    cached = await cache_get(redis, cache_key)
    if cached is not None:
        return cached

    ticker = await _resolve_ticker(symbol, db)
    stmt = (
        select(OHLCVIntraday)
        .where(OHLCVIntraday.ticker_id == ticker.id)
        .where(OHLCVIntraday.timeframe == timeframe)
    )
    if date:
        day_start = datetime(date.year, date.month, date.day, tzinfo=timezone.utc)
        day_end = datetime(date.year, date.month, date.day, 23, 59, 59, tzinfo=timezone.utc)
        stmt = stmt.where(OHLCVIntraday.ts >= day_start).where(OHLCVIntraday.ts <= day_end)
    stmt = stmt.order_by(OHLCVIntraday.ts.desc()).limit(limit)

    result = await db.execute(stmt)
    bars = result.scalars().all()
    data = [OHLCVIntradayRead.model_validate(b).model_dump(mode="json") for b in bars]
    await cache_set(redis, cache_key, data)
    return data


@router.get("/{symbol}/latest", response_model=OHLCVDailyRead)
async def get_latest_bar(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    cache_key = f"ohlcv:latest:{symbol.upper()}"
    cached = await cache_get(redis, cache_key)
    if cached is not None:
        return cached

    ticker = await _resolve_ticker(symbol, db)
    result = await db.execute(
        select(OHLCVDaily)
        .where(OHLCVDaily.ticker_id == ticker.id)
        .order_by(OHLCVDaily.date.desc())
        .limit(1)
    )
    bar = result.scalar_one_or_none()
    if bar is None:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")

    data = OHLCVDailyRead.model_validate(bar).model_dump(mode="json")
    await cache_set(redis, cache_key, data, ttl=60)
    return data


@router.post("/backfill", status_code=202)
async def trigger_backfill(
    _: User = Depends(get_superuser),
):
    ingest_daily_ohlcv.delay()
    return {"status": "queued"}
