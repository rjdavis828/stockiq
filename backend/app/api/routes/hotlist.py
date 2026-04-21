from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_redis
from app.config import settings
from app.db.models import Alert, Ticker, User

router = APIRouter(prefix="/hotlist", tags=["hotlist"])

_MANUAL_KEY = "hotlist:manual"
_HB_KEY = "ws:finnhub:last_heartbeat"


@router.get("")
async def get_hotlist(
    redis: aioredis.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    manual = sorted(await redis.smembers(_MANUAL_KEY))
    manual_set = set(manual)

    rows = await db.execute(
        select(Ticker.symbol)
        .join(Alert, Alert.ticker_id == Ticker.id)
        .where(Alert.status == "active")
        .distinct()
    )
    suggested = sorted({r.symbol for r in rows} - manual_set)

    ws_connected = False
    hb = await redis.get(_HB_KEY)
    if hb:
        age = datetime.now(timezone.utc).timestamp() - float(hb)
        ws_connected = age <= settings.ws_stale_threshold_s

    return {
        "suggested": suggested,
        "manual": manual,
        "ws_connected": ws_connected,
        "slots_used": len(manual),
    }


@router.post("/{symbol}", status_code=200)
async def pin_symbol(
    symbol: str,
    redis: aioredis.Redis = Depends(get_redis),
    _user: User = Depends(get_current_user),
):
    symbol = symbol.upper()
    manual = await redis.smembers(_MANUAL_KEY)

    if symbol in manual:
        raise HTTPException(status_code=409, detail="Symbol already in hotlist")

    if len(manual) >= settings.finnhub_hotlist_max:
        raise HTTPException(status_code=400, detail="Hotlist at capacity")

    await redis.sadd(_MANUAL_KEY, symbol)
    return {"symbol": symbol}


@router.delete("/{symbol}", status_code=200)
async def unpin_symbol(
    symbol: str,
    redis: aioredis.Redis = Depends(get_redis),
    _user: User = Depends(get_current_user),
):
    symbol = symbol.upper()
    await redis.srem(_MANUAL_KEY, symbol)
    return {"symbol": symbol}
