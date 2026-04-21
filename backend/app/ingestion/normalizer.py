import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OHLCVDaily, Ticker
from app.ingestion.providers.base import OHLCVBar, TickerInfo

logger = logging.getLogger(__name__)


_TICKER_UPSERT_CHUNK = 1000  # 8 cols × 1000 = 8000 params, well under asyncpg's 32767 limit


async def upsert_tickers(session: AsyncSession, ticker_infos: list[TickerInfo]) -> int:
    if not ticker_infos:
        return 0

    rows = [
        {
            "symbol": t.symbol,
            "name": t.name,
            "exchange": t.exchange,
            "sector": t.sector,
            "industry": t.industry,
            "market_cap": t.market_cap,
            "active": t.active,
            "updated_at": t.updated_at,
        }
        for t in ticker_infos
    ]

    for i in range(0, len(rows), _TICKER_UPSERT_CHUNK):
        chunk = rows[i : i + _TICKER_UPSERT_CHUNK]
        stmt = insert(Ticker).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol"],
            set_={
                "name": stmt.excluded.name,
                "exchange": stmt.excluded.exchange,
                "sector": stmt.excluded.sector,
                "industry": stmt.excluded.industry,
                "market_cap": stmt.excluded.market_cap,
                "active": stmt.excluded.active,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await session.execute(stmt)

    await session.commit()
    logger.info("Upserted %d tickers", len(rows))
    return len(rows)


async def bulk_insert_intraday_bars(
    session: AsyncSession, bars: list[dict], timeframe: str = "1m"
) -> int:
    if not bars:
        return 0

    symbols = {b["symbol"] for b in bars}
    result = await session.execute(
        select(Ticker.id, Ticker.symbol).where(Ticker.symbol.in_(symbols))
    )
    symbol_to_id = {row.symbol: row.id for row in result}

    rows = []
    for bar in bars:
        ticker_id = symbol_to_id.get(bar["symbol"])
        if ticker_id is None:
            continue
        rows.append({
            "ticker_id": ticker_id,
            "ts": bar["ts"],
            "timeframe": timeframe,
            "open": bar["open"],
            "high": bar["high"],
            "low": bar["low"],
            "close": bar["close"],
            "volume": bar["volume"],
            "vwap": bar.get("vwap"),
            "trade_count": bar.get("trade_count"),
        })

    if not rows:
        return 0

    from app.db.models import OHLCVIntraday
    from sqlalchemy import text
    stmt = insert(OHLCVIntraday).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_ohlcv_intraday_ticker_ts_tf",
        set_={
            "high": text("GREATEST(ohlcv_intraday.high, EXCLUDED.high)"),
            "low": text("LEAST(ohlcv_intraday.low, EXCLUDED.low)"),
            "close": text("EXCLUDED.close"),
            "volume": text("ohlcv_intraday.volume + EXCLUDED.volume"),
            "trade_count": text("EXCLUDED.trade_count"),
            "vwap": text("EXCLUDED.vwap"),
        },
    )
    await session.execute(stmt)
    await session.commit()
    logger.info("Upserted %d intraday bars (%s)", len(rows), timeframe)
    return len(rows)


async def bulk_insert_daily_bars(
    session: AsyncSession, bars: list[OHLCVBar]
) -> int:
    if not bars:
        return 0

    symbols = {b.symbol for b in bars}
    result = await session.execute(
        select(Ticker.id, Ticker.symbol).where(Ticker.symbol.in_(symbols))
    )
    symbol_to_id = {row.symbol: row.id for row in result}

    missing = symbols - symbol_to_id.keys()
    if missing:
        logger.warning("No ticker_id found for symbols: %s — skipping", missing)

    rows = []
    for bar in bars:
        ticker_id = symbol_to_id.get(bar.symbol)
        if ticker_id is None:
            continue
        rows.append(
            {
                "ticker_id": ticker_id,
                "date": bar.date,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "vwap": bar.vwap,
                "adj_close": bar.adj_close,
                "source": bar.source,
            }
        )

    if not rows:
        return 0

    stmt = insert(OHLCVDaily).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_ohlcv_daily_ticker_date",
        set_={
            "open": stmt.excluded.open,
            "high": stmt.excluded.high,
            "low": stmt.excluded.low,
            "close": stmt.excluded.close,
            "volume": stmt.excluded.volume,
            "vwap": stmt.excluded.vwap,
            "adj_close": stmt.excluded.adj_close,
            "source": stmt.excluded.source,
        },
    )
    await session.execute(stmt)
    await session.commit()
    logger.info("Upserted %d daily bars", len(rows))
    return len(rows)
