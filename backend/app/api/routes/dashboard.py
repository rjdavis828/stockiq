import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_redis
from app.config import settings
from app.db.models import Ticker, User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_ET = ZoneInfo("America/New_York")
_SEED_PATH = Path(__file__).parent.parent.parent.parent / "data" / "indices_seed.json"

# Symbol map: index name -> yfinance ticker symbol
_INDEX_SYMBOLS = {
    "S&P 500":    "^GSPC",
    "NASDAQ":     "^IXIC",
    "DOW":        "^DJI",
    "VIX":        "^VIX",
    "Russell 2K": "^RUT",
}


def _market_status(now_utc: datetime) -> str:
    et = now_utc.astimezone(_ET)
    t = et.time()
    # Market holidays not handled — weekday check only
    wd = et.weekday()  # 0=Mon, 6=Sun
    if wd >= 5:
        return "closed"
    from datetime import time
    pre_open   = time(4, 0)
    open_time  = time(9, 30)
    close_time = time(16, 0)
    post_close = time(20, 0)
    if t < pre_open or t >= post_close:
        return "closed"
    if t < open_time:
        return "pre"
    if t < close_time:
        return "open"
    return "post"


async def _load_indices(redis: aioredis.Redis) -> list[dict]:
    seed: list[dict] = json.loads(_SEED_PATH.read_text())
    stale_threshold = settings.ws_stale_threshold_s * 4
    now_ts = datetime.now(timezone.utc).timestamp()

    result = []
    for entry in seed:
        sym = _INDEX_SYMBOLS.get(entry["name"])
        bar = None
        if sym:
            raw = await redis.get(f"intraday:{sym}:latest")
            if raw:
                try:
                    bar = json.loads(raw)
                    # Check staleness
                    bar_ts_str = bar.get("ts") or bar.get("timestamp")
                    if bar_ts_str:
                        bar_ts = datetime.fromisoformat(bar_ts_str.replace("Z", "+00:00")).timestamp()
                        if now_ts - bar_ts > stale_threshold:
                            bar = None
                except Exception:
                    bar = None

        if bar and "close" in bar and "prev_close" in bar and bar["prev_close"]:
            close = float(bar["close"])
            prev = float(bar["prev_close"])
            change = (close - prev) / prev * 100
            result.append({"name": entry["name"], "value": round(close, 2), "change": round(change, 2)})
        else:
            result.append(entry)

    return result


@router.get("/summary")
async def dashboard_summary(
    redis: aioredis.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)

    indices = await _load_indices(redis)

    total_result = await db.execute(select(func.count()).select_from(select(Ticker).where(Ticker.active.is_(True)).subquery()))
    total_stocks = total_result.scalar_one()

    watchlist_count_raw = await redis.scard("watchlist:default")
    watchlist_count = watchlist_count_raw or 0

    return {
        "indices": indices,
        "market_status": _market_status(now),
        "last_updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "watchlist_count": watchlist_count,
        "total_stocks": total_stocks,
    }
