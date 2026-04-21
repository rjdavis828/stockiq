"""Long-running Celery task that streams real-time trades from Polygon WebSocket,
aggregates them into 1-minute OHLCV bars, persists to ohlcv_intraday, and
publishes completed bars to Redis for downstream consumers."""
import asyncio
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal

from celery_worker import celery_app

logger = logging.getLogger(__name__)

_open_bars: dict[str, dict] = {}


def _minute_floor(ms: int) -> datetime:
    return datetime.utcfromtimestamp(ms / 1000).replace(second=0, microsecond=0, tzinfo=timezone.utc)


def _new_bar(symbol: str, ts: datetime, price: float, size: int) -> dict:
    return {
        "symbol": symbol,
        "ts": ts,
        "open": price,
        "high": price,
        "low": price,
        "close": price,
        "volume": size,
        "trade_count": 1,
        "vwap_num": price * size,
        "vwap_den": size,
    }


def _update_bar(bar: dict, price: float, size: int) -> None:
    bar["high"] = max(bar["high"], price)
    bar["low"] = min(bar["low"], price)
    bar["close"] = price
    bar["volume"] += size
    bar["trade_count"] += 1
    bar["vwap_num"] += price * size
    bar["vwap_den"] += size


async def _flush_bar(symbol: str, redis_client, db_factory) -> None:
    bar = _open_bars.pop(symbol)
    vwap = bar["vwap_num"] / bar["vwap_den"] if bar["vwap_den"] else None

    payload = {
        "type": "bar",
        "symbol": bar["symbol"],
        "ts": bar["ts"].isoformat(),
        "open": bar["open"],
        "high": bar["high"],
        "low": bar["low"],
        "close": bar["close"],
        "volume": bar["volume"],
        "vwap": round(vwap, 4) if vwap else None,
        "trade_count": bar["trade_count"],
    }

    try:
        await _upsert_intraday_bar(bar, vwap, db_factory)
    except Exception:
        logger.exception("Failed to persist intraday bar for %s", symbol)

    try:
        from app.config import settings
        channel = f"{settings.ws_bar_channel_prefix}:{symbol}"
        await redis_client.publish(channel, json.dumps(payload))
    except Exception:
        logger.exception("Failed to publish bar to Redis for %s", symbol)

    try:
        from app.tasks.alert_eval import evaluate_alerts_for_bar
        evaluate_alerts_for_bar.delay(symbol, payload)
    except Exception:
        logger.exception("Failed to queue alert eval for %s", symbol)


async def _upsert_intraday_bar(bar: dict, vwap: float | None, db_factory) -> None:
    from sqlalchemy import select, text
    from sqlalchemy.dialects.postgresql import insert
    from app.db.models import OHLCVIntraday, Ticker

    async with db_factory() as session:
        result = await session.execute(select(Ticker.id).where(Ticker.symbol == bar["symbol"]))
        ticker_id = result.scalar_one_or_none()
        if ticker_id is None:
            return

        stmt = insert(OHLCVIntraday).values(
            ticker_id=ticker_id,
            ts=bar["ts"],
            timeframe="1m",
            open=Decimal(str(bar["open"])),
            high=Decimal(str(bar["high"])),
            low=Decimal(str(bar["low"])),
            close=Decimal(str(bar["close"])),
            volume=bar["volume"],
            trade_count=bar["trade_count"],
            vwap=Decimal(str(round(vwap, 4))) if vwap else None,
        ).on_conflict_do_update(
            constraint="uq_ohlcv_intraday_ticker_ts_tf",
            set_={
                "high": text("GREATEST(ohlcv_intraday.high, EXCLUDED.high)"),
                "low": text("LEAST(ohlcv_intraday.low, EXCLUDED.low)"),
                "close": text("EXCLUDED.close"),
                "volume": text("ohlcv_intraday.volume + EXCLUDED.volume"),
                "trade_count": text("ohlcv_intraday.trade_count + EXCLUDED.trade_count"),
                "vwap": text("EXCLUDED.vwap"),
            },
        )
        await session.execute(stmt)
        await session.commit()


async def _accumulate_trade(trade: dict, redis_client, db_factory) -> None:
    symbol = trade.get("sym")
    price = trade.get("p")
    size = trade.get("s", 0)
    ts_ms = trade.get("t")

    if not symbol or price is None or not ts_ms:
        return

    bar_ts = _minute_floor(ts_ms)

    if symbol in _open_bars and _open_bars[symbol]["ts"] != bar_ts:
        await _flush_bar(symbol, redis_client, db_factory)

    if symbol not in _open_bars:
        _open_bars[symbol] = _new_bar(symbol, bar_ts, price, size)
    else:
        _update_bar(_open_bars[symbol], price, size)


async def _stream_loop() -> None:
    import websockets
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.config import settings

    engine = create_async_engine(settings.database_url, echo=False)
    db_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)

    symbols = (
        [s.strip().upper() for s in settings.realtime_symbols.split(",") if s.strip()]
        if settings.realtime_symbols
        else []
    )

    if not symbols:
        logger.warning("No realtime_symbols configured; stream worker idle.")
        await redis_client.aclose()
        await engine.dispose()
        return

    try:
        async with websockets.connect(settings.polygon_ws_url) as ws:
            auth_msg = json.loads(await ws.recv())
            logger.info("Polygon WS connected: %s", auth_msg)

            await ws.send(json.dumps({"action": "auth", "params": settings.polygon_api_key}))
            auth_resp = json.loads(await ws.recv())
            logger.info("Polygon auth: %s", auth_resp)

            for sym in symbols:
                await ws.send(json.dumps({"action": "subscribe", "params": f"T.{sym}"}))

            async for raw in ws:
                messages = json.loads(raw)
                if not isinstance(messages, list):
                    messages = [messages]
                for msg in messages:
                    if msg.get("ev") == "T":
                        await _accumulate_trade(msg, redis_client, db_factory)
    except Exception:
        logger.exception("Polygon WebSocket stream error")
    finally:
        await redis_client.aclose()
        await engine.dispose()


@celery_app.task(name="tasks.stream.run_trade_stream")
def run_trade_stream() -> None:
    asyncio.run(_stream_loop())
