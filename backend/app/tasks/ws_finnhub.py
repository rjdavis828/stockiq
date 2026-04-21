import asyncio
import json
import logging
from datetime import datetime, timezone

from celery_worker import celery_app

logger = logging.getLogger(__name__)

WS_URL = "wss://ws.finnhub.io?token={token}"
WS_HB_KEY = "ws:finnhub:last_heartbeat"
WS_STREAM = "ws:bars:1m"
_HOTLIST_MANUAL_KEY = "hotlist:manual"
_RECONNECT_DELAY_S = 5
_HB_INTERVAL_S = 30


class OHLCVAccumulator:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.current_bucket: datetime | None = None
        self.open = self.high = self.low = self.close = self.volume = 0.0

    def _bucket(self, ts_ms: int) -> datetime:
        ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        return ts.replace(second=0, microsecond=0)

    def add_trade(self, price: float, volume: float, ts_ms: int) -> datetime | None:
        bucket = self._bucket(ts_ms)
        completed_bucket = None
        if self.current_bucket is not None and bucket > self.current_bucket:
            completed_bucket = self.current_bucket
        if self.current_bucket != bucket:
            self.open = price
            self.high = price
            self.low = price
            self.current_bucket = bucket
        else:
            self.high = max(self.high, price)
            self.low = min(self.low, price)
        self.close = price
        self.volume += volume
        return completed_bucket

    def to_bar(self, bucket: datetime) -> dict:
        return {
            "symbol": self.symbol,
            "ts": bucket.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "vwap": None,
            "trade_count": None,
        }

    def reset_to(self, price: float, volume: float, bucket: datetime):
        self.open = price
        self.high = price
        self.low = price
        self.close = price
        self.volume = volume
        self.current_bucket = bucket


async def _get_hotlist(redis) -> set[str]:
    return set(await redis.smembers(_HOTLIST_MANUAL_KEY))


def _emit(redis_sync, bar: dict):
    redis_sync.xadd(WS_STREAM, {"bar": json.dumps(bar)}, maxlen=100_000)


async def _ws_loop():
    import websockets
    import redis.asyncio as aioredis

    from app.config import settings

    if not settings.finnhub_api_key:
        logger.error("FINNHUB_API_KEY not configured; ws_finnhub worker exiting.")
        return

    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    accumulators: dict[str, OHLCVAccumulator] = {}
    subscribed: set[str] = set()

    async def _sync_subscriptions(ws, hotlist: set[str]):
        to_add = hotlist - subscribed
        to_remove = subscribed - hotlist
        for sym in to_add:
            await ws.send(json.dumps({"type": "subscribe", "symbol": sym}))
            subscribed.add(sym)
            if sym not in accumulators:
                accumulators[sym] = OHLCVAccumulator(sym)
        for sym in to_remove:
            await ws.send(json.dumps({"type": "unsubscribe", "symbol": sym}))
            subscribed.discard(sym)

    url = WS_URL.format(token=settings.finnhub_api_key)

    while True:
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=30) as ws:
                logger.info("Finnhub WS connected")
                hotlist = await _get_hotlist(redis)
                await _sync_subscriptions(ws, hotlist)
                last_hb = asyncio.get_event_loop().time()

                async for raw in ws:
                    now = asyncio.get_event_loop().time()
                    await redis.set(WS_HB_KEY, str(int(datetime.now(timezone.utc).timestamp())))

                    if now - last_hb >= _HB_INTERVAL_S:
                        last_hb = now
                        new_hotlist = await _get_hotlist(redis)
                        await _sync_subscriptions(ws, new_hotlist)

                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    if msg.get("type") != "trade":
                        continue

                    for trade in msg.get("data", []):
                        sym = trade.get("s")
                        price = trade.get("p")
                        volume = trade.get("v", 0)
                        ts_ms = trade.get("t")
                        if not sym or price is None or ts_ms is None:
                            continue
                        if sym not in accumulators:
                            accumulators[sym] = OHLCVAccumulator(sym)
                        acc = accumulators[sym]
                        completed_bucket = acc.add_trade(float(price), float(volume), int(ts_ms))
                        if completed_bucket is not None:
                            bar = acc.to_bar(completed_bucket)
                            payload = json.dumps({"type": "bar", **bar})
                            await redis.xadd(WS_STREAM, {"bar": json.dumps(bar)}, maxlen=100_000)
                            channel = f"{settings.ws_bar_channel_prefix}:{sym}"
                            await redis.publish(channel, payload)
                            logger.debug("Emitted bar %s @ %s", sym, completed_bucket)

        except Exception:
            logger.exception("Finnhub WS error; reconnecting in %ds", _RECONNECT_DELAY_S)
            await asyncio.sleep(_RECONNECT_DELAY_S)


async def _flush():
    import redis.asyncio as aioredis

    from app.config import settings
    from app.ingestion.normalizer import bulk_insert_intraday_bars
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        entries = await redis.xrange(WS_STREAM, count=10_000)
        if not entries:
            return {"bars_inserted": 0, "entries_read": 0}

        bars = []
        last_id = None
        for entry_id, fields in entries:
            last_id = entry_id
            try:
                bar = json.loads(fields["bar"])
                bar["ts"] = datetime.fromisoformat(bar["ts"])
                bars.append(bar)
            except Exception:
                logger.exception("Failed to parse WS stream entry %s", entry_id)

        inserted = 0
        if bars:
            async with factory() as session:
                inserted = await bulk_insert_intraday_bars(session, bars, timeframe="1m")

        if last_id:
            await redis.xdel(WS_STREAM, *[e[0] for e in entries])

        try:
            from app.tasks.alert_eval import evaluate_alerts_for_bar
            hotlist = await _get_hotlist(redis)
            latest_by_symbol: dict[str, dict] = {}
            for bar in bars:
                sym = bar["symbol"]
                if sym not in latest_by_symbol or bar["ts"] > latest_by_symbol[sym]["ts"]:
                    latest_by_symbol[sym] = bar
            for sym, bar in latest_by_symbol.items():
                if sym not in hotlist:
                    continue
                evaluate_alerts_for_bar.delay(sym, {
                    "type": "bar", "symbol": sym,
                    "ts": bar["ts"].isoformat(),
                    "open": bar["open"], "high": bar["high"],
                    "low": bar["low"], "close": bar["close"],
                    "volume": bar["volume"],
                    "vwap": bar.get("vwap"),
                    "trade_count": bar.get("trade_count"),
                })
        except Exception:
            logger.exception("Failed to queue alert evaluations from WS flush")

        logger.info("WS flush: %d entries read, %d bars inserted", len(entries), inserted)
        return {"entries_read": len(entries), "bars_inserted": inserted}
    finally:
        await engine.dispose()
        await redis.aclose()


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@celery_app.task(name="app.tasks.ws_finnhub.run_ws_worker", bind=True)
def run_ws_worker(self):
    """Long-running WS worker. Start with: celery -A celery_worker worker -Q ws --pool=solo"""
    _run(_ws_loop())


@celery_app.task(name="app.tasks.ws_finnhub.flush_ws_bars")
def flush_ws_bars() -> dict:
    """Drain Redis stream → bulk_insert_intraday_bars. Runs every 1 min via beat."""
    return _run(_flush())
