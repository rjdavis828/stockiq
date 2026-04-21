import asyncio
import logging
from datetime import date, datetime, timedelta, timezone, time

from celery_worker import celery_app
from sqlalchemy import select, update

logger = logging.getLogger(__name__)

_MARKET_OPEN = time(9, 30)
_MARKET_CLOSE = time(16, 5)
_ET = timezone(timedelta(hours=-4))
_LAST_POLL_KEY = "intraday_poll:last_ts"
_FALLBACK_MINUTES = 5


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _is_market_hours() -> bool:
    now_et = datetime.now(_ET).time()
    return _MARKET_OPEN <= now_et <= _MARKET_CLOSE


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def ingest_daily_ohlcv(self) -> dict:
    """Fetch yesterday's OHLCV bars for all active tickers and upsert into DB."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy import select

    from app.config import settings
    from app.db.models import Ticker
    from app.ingestion.normalizer import bulk_insert_daily_bars
    from app.ingestion.providers.polygon import PolygonProvider

    async def _ingest():
        engine = create_async_engine(settings.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        provider = PolygonProvider()
        target_date = date.today() - timedelta(days=1)

        try:
            async with factory() as session:
                result = await session.execute(
                    select(Ticker.symbol).where(Ticker.active.is_(True))
                )
                symbols = [row.symbol for row in result]

            all_bars = []
            async with factory() as session:
                bars_by_symbol = await provider.fetch_daily_batch(symbols, target_date, target_date)
                for bars in bars_by_symbol.values():
                    all_bars.extend(bars)
                inserted = await bulk_insert_daily_bars(session, all_bars)

            return {"date": str(target_date), "symbols": len(symbols), "bars_inserted": inserted}
        finally:
            await provider.close()
            await engine.dispose()

    try:
        return _run(_ingest())
    except Exception as exc:
        logger.exception("ingest_daily_ohlcv failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=600)
def refresh_tickers(self) -> dict:
    """Pull latest ticker reference data from Polygon and upsert into DB."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.config import settings
    from app.ingestion.normalizer import upsert_tickers
    from app.ingestion.providers.polygon import PolygonProvider

    async def _refresh():
        engine = create_async_engine(settings.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        provider = PolygonProvider()

        try:
            ticker_infos = await provider.fetch_tickers()
            async with factory() as session:
                upserted = await upsert_tickers(session, ticker_infos)
            return {"tickers_upserted": upserted}
        finally:
            await provider.close()
            await engine.dispose()

    try:
        return _run(_refresh())
    except Exception as exc:
        logger.exception("refresh_tickers failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def run_active_scans(self) -> dict:
    """Run all active scans and persist results after ingestion."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy import select

    from app.config import settings
    from app.db.models import Scan
    from app.scanner.engine import ScannerEngine

    async def _run_scans():
        engine = create_async_engine(settings.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        try:
            async with factory() as session:
                result = await session.execute(select(Scan).where(Scan.active.is_(True)))
                scans = result.scalars().all()

                engine_inst = ScannerEngine(session)
                total_results = 0

                for scan in scans:
                    try:
                        results, count = await engine_inst.run_scan(scan)
                        total_results += count

                        from app.db.models import ScannerResult
                        for result in results:
                            sr = ScannerResult(
                                scan_id=scan.id,
                                ticker_id=result["ticker_id"],
                                triggered_at=datetime.fromisoformat(
                                    result["triggered_at"]
                                ),
                                condition_snapshot=result["condition_snapshot"],
                                values_snapshot=result["values_snapshot"],
                            )
                            session.add(sr)

                        scan.last_run = datetime.now(timezone.utc)
                    except Exception as e:
                        logger.exception("Error running scan %d: %s", scan.id, e)

                await session.commit()
                return {"scans_run": len(scans), "total_results": total_results}
        finally:
            await engine.dispose()

    try:
        return _run(_run_scans())
    except Exception as exc:
        logger.exception("run_active_scans failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=600, name="app.ingestion.tasks.ingest_fundamentals")
def ingest_fundamentals(self) -> dict:
    """Fetch quarterly fundamentals via yfinance for all active tickers and upsert."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.config import settings
    from app.db.models import Fundamental, Ticker
    from app.ingestion.providers.yfinance_provider import YFinanceProvider

    async def _ingest():
        engine = create_async_engine(settings.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        provider = YFinanceProvider()

        try:
            async with factory() as session:
                result = await session.execute(
                    select(Ticker.id, Ticker.symbol).where(Ticker.active.is_(True))
                )
                tickers = result.all()

            logger.info(f"Found {len(tickers)} active tickers")

            total_upserted = 0
            for ticker_id, symbol in tickers:
                try:
                    fundamentals = await provider.fetch_fundamentals(symbol)
                    if not fundamentals:
                        continue

                    async with factory() as session:
                        for fd in fundamentals:
                            stmt = (
                                pg_insert(Fundamental)
                                .values(
                                    ticker_id=ticker_id,
                                    period=fd.period,
                                    revenue=fd.revenue,
                                    eps=fd.eps,
                                    pe_ratio=fd.pe_ratio,
                                    market_cap=fd.market_cap,
                                    reported_at=fd.reported_at,
                                )
                                .on_conflict_do_update(
                                    constraint="uq_fundamentals_ticker_period",
                                    set_={
                                        "revenue": fd.revenue,
                                        "eps": fd.eps,
                                        "pe_ratio": fd.pe_ratio,
                                        "market_cap": fd.market_cap,
                                        "reported_at": fd.reported_at,
                                    },
                                )
                            )
                            await session.execute(stmt)
                        await session.commit()
                        total_upserted += len(fundamentals)
                except Exception:
                    logger.exception("Failed to ingest fundamentals for %s", symbol)

            return {"tickers_processed": len(tickers), "rows_upserted": total_upserted}
        finally:
            await engine.dispose()

    try:
        return _run(_ingest())
    except Exception as exc:
        logger.exception("ingest_fundamentals failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(name="tasks.intraday_poll.poll_intraday_bars")
def poll_intraday_bars() -> dict:
    """Poll Polygon REST API every 5 minutes during market hours for 1-minute OHLCV bars."""
    return _run(_poll_intraday())


async def _poll_intraday() -> dict:
    if not _is_market_hours():
        logger.info("Outside market hours, skipping intraday poll.")
        return {"skipped": True}

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    import redis.asyncio as aioredis

    from app.config import settings
    from app.db.models import Ticker
    from app.ingestion.providers.polygon import PolygonProvider
    from app.ingestion.normalizer import bulk_insert_intraday_bars

    engine = create_async_engine(settings.database_url, echo=False)
    db_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    provider = PolygonProvider()
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)

    try:
        async with db_factory() as session:
            result = await session.execute(
                select(Ticker.symbol).where(Ticker.active.is_(True))
            )
            symbols = [row.symbol for row in result]

        if not symbols:
            logger.warning("No active symbols in tickers table.")
            return {"bars_inserted": 0, "symbols": 0}

        now = datetime.now(timezone.utc)

        last_ts_str = await redis.get(_LAST_POLL_KEY)
        if last_ts_str:
            from_dt = datetime.fromisoformat(last_ts_str)
        else:
            from_dt = now - timedelta(minutes=_FALLBACK_MINUTES)

        bars = await provider.fetch_intraday_for_symbols(
            symbols, from_dt=from_dt, to_dt=now, timeframe_minutes=1,
            concurrency=settings.intraday_poll_concurrency,
        )

        async with db_factory() as session:
            inserted = await bulk_insert_intraday_bars(session, bars, timeframe="1m")

        await redis.set(_LAST_POLL_KEY, now.isoformat())

        try:
            from app.tasks.alert_eval import evaluate_alerts_for_bar
            latest_by_symbol: dict[str, dict] = {}
            for b in bars:
                sym = b["symbol"]
                if sym not in latest_by_symbol or b["ts"] > latest_by_symbol[sym]["ts"]:
                    latest_by_symbol[sym] = b

            for sym, bar in latest_by_symbol.items():
                bar_payload = {
                    "type": "bar",
                    "symbol": sym,
                    "ts": bar["ts"].isoformat(),
                    "open": bar["open"],
                    "high": bar["high"],
                    "low": bar["low"],
                    "close": bar["close"],
                    "volume": bar["volume"],
                    "vwap": bar.get("vwap"),
                    "trade_count": bar.get("trade_count"),
                }
                evaluate_alerts_for_bar.delay(sym, bar_payload)
        except Exception:
            logger.exception("Failed to queue alert evaluations")

        logger.info(
            "Intraday poll: %d symbols, %d bars fetched, %d upserted",
            len(symbols), len(bars), inserted,
        )
        return {"symbols": len(symbols), "bars_fetched": len(bars), "bars_inserted": inserted}

    finally:
        await provider.close()
        await engine.dispose()
        await redis.aclose()
