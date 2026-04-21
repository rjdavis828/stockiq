import asyncio
import logging
from datetime import UTC, date, datetime, timedelta, timezone, time

from celery_worker import celery_app
from sqlalchemy import select, update

from app.tasks.ws_finnhub import WS_HB_KEY, _get_hotlist as _get_hotlist_ws

logger = logging.getLogger(__name__)

_MARKET_OPEN = time(9, 30)
_MARKET_CLOSE = time(16, 5)
_ET = timezone(timedelta(hours=-4))
_LAST_POLL_KEY = "intraday_poll:last_ts"
_FALLBACK_MINUTES = 15


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _is_market_hours() -> bool:
    now_et = datetime.now(_ET).time()
    return _MARKET_OPEN <= now_et <= _MARKET_CLOSE


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def ingest_daily_ohlcv(self) -> dict:
    """Fetch yesterday's OHLCV bars for all active tickers via yfinance and upsert into DB."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.config import settings
    from app.ingestion.normalizer import bulk_insert_daily_bars
    from app.ingestion.providers.yfinance_provider import YFinanceProvider
    import redis.asyncio as aioredis

    async def _ingest():
        engine = create_async_engine(settings.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        provider = YFinanceProvider()
        target_date = date.today() - timedelta(days=1)

        redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            job_cfg = await _get_job_config(redis, factory, "ingest-daily-ohlcv")
            universe_filter = job_cfg.get("universe_filter", "XNAS,XNYS")
            symbols = await _get_symbols_cached(redis, factory, universe_filter)

            logger.info("ingest_daily_ohlcv: %d active symbols for %s", len(symbols), target_date)
            if not symbols:
                logger.warning("No active tickers found — skipping fetch")
                return {"date": str(target_date), "symbols": 0, "bars_inserted": 0}

            bars = await provider.fetch_daily_batch(symbols, target_date, target_date)
            logger.info("Fetched %d daily bars for %d symbols", len(bars), len(symbols))

            async with factory() as session:
                inserted = await bulk_insert_daily_bars(session, bars)

            return {"date": str(target_date), "symbols": len(symbols), "bars_inserted": inserted}
        finally:
            await redis.aclose()
            await engine.dispose()

    try:
        return _run(_ingest())
    except Exception as exc:
        logger.exception("ingest_daily_ohlcv failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=600)
def refresh_tickers(self) -> dict:
    """Pull US stock symbols from Finnhub /stock/symbol and upsert into DB."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.config import settings
    from app.ingestion.normalizer import upsert_tickers
    from app.ingestion.providers.finnhub_provider import FinnhubProvider

    async def _refresh():
        engine = create_async_engine(settings.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        provider = FinnhubProvider()

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


_HOTLIST_KEY = "hotlist:symbols"
_SYMBOLS_CACHE_KEY = "intraday_poll:symbols"
_SYMBOLS_CACHE_TTL = 300
_JOB_CONFIG_CACHE_TTL = 300


async def _get_hotlist(redis, db_factory) -> set[str]:
    from app.config import settings
    from app.db.models import Alert, Ticker

    cached = await redis.smembers(_HOTLIST_KEY)
    if cached:
        return set(cached)
    async with db_factory() as session:
        rows = await session.execute(
            select(Ticker.symbol)
            .join(Alert, Alert.ticker_id == Ticker.id)
            .where(Alert.status == "active")
            .limit(settings.finnhub_hotlist_max)
        )
    symbols = {r.symbol for r in rows}
    if symbols:
        await redis.sadd(_HOTLIST_KEY, *symbols)
        await redis.expire(_HOTLIST_KEY, _SYMBOLS_CACHE_TTL)
    return symbols


async def _get_job_config(redis, db_factory, job_name: str) -> dict:
    import json
    cache_key = f"job_config:{job_name}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)
    try:
        from app.db.models import JobConfig
        async with db_factory() as session:
            result = await session.execute(
                select(JobConfig).where(JobConfig.job_name == job_name)
            )
            config = result.scalar_one_or_none()
        if config is None:
            return {"enabled": True, "universe_filter": "XNAS,XNYS", "extra_config": {}}
        data = {
            "enabled": config.enabled,
            "universe_filter": config.universe_filter,
            "cron_schedule": config.cron_schedule,
            "extra_config": config.extra_config or {},
        }
        await redis.set(cache_key, json.dumps(data), ex=_JOB_CONFIG_CACHE_TTL)
        return data
    except Exception:
        logger.exception("Failed to load job config for %s, using defaults", job_name)
        return {"enabled": True, "universe_filter": "XNAS,XNYS", "extra_config": {}}


async def _get_symbols_cached(redis, db_factory, universe_filter: str = "ALL") -> list[str]:
    """Return active symbols, optionally filtered to comma-separated exchange codes.

    universe_filter="ALL" → no exchange filter
    universe_filter="XNAS,XNYS" → only symbols on those exchanges
    """
    import json
    from app.db.models import Ticker

    cache_key = f"{_SYMBOLS_CACHE_KEY}:{universe_filter}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    query = select(Ticker.symbol).where(Ticker.active.is_(True))
    if universe_filter and universe_filter.upper() != "ALL":
        exchange_codes = [c.strip() for c in universe_filter.split(",") if c.strip()]
        if exchange_codes:
            query = query.where(Ticker.exchange.in_(exchange_codes))

    async with db_factory() as session:
        result = await session.execute(query)
        symbols = [row.symbol for row in result]

    logger.info("Symbol list for universe_filter=%r: %d symbols", universe_filter, len(symbols))
    if symbols:
        await redis.set(cache_key, json.dumps(symbols), ex=_SYMBOLS_CACHE_TTL)
    return symbols


@celery_app.task(name="app.ingestion.tasks.poll_yfinance_bars")
def poll_yfinance_bars() -> dict:
    """Poll yfinance every 5 min during market hours for 1-minute OHLCV bars."""
    return _run(_poll_yfinance())


async def _poll_yfinance() -> dict:
    if not _is_market_hours():
        logger.info("Outside market hours, skipping intraday poll.")
        return {"skipped": True}

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    import redis.asyncio as aioredis

    from app.config import settings
    from app.ingestion.providers.yfinance_provider import YFinanceProvider
    from app.ingestion.normalizer import bulk_insert_intraday_bars

    engine = create_async_engine(settings.database_url, echo=False)
    db_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)

    try:
        job_cfg = await _get_job_config(redis, db_factory, "poll-intraday-bars")
        if not job_cfg.get("enabled", True):
            logger.info("poll_yfinance_bars disabled by job config")
            return {"skipped": True, "reason": "disabled"}

        universe_filter = job_cfg.get("universe_filter", "SP500")

        hb = await redis.get(WS_HB_KEY)
        ws_stale = (
            hb is None or
            (datetime.now(UTC) - datetime.fromtimestamp(int(hb), tz=UTC)).total_seconds() > settings.ws_stale_threshold_s
        )

        symbols = await _get_symbols_cached(redis, db_factory, universe_filter)
        if not symbols:
            logger.warning("No active symbols in tickers table.")
            return {"bars_inserted": 0, "symbols": 0}

        now = datetime.now(timezone.utc)
        last_ts_str = await redis.get(_LAST_POLL_KEY)
        from_dt = datetime.fromisoformat(last_ts_str) if last_ts_str else now - timedelta(minutes=_FALLBACK_MINUTES)

        if ws_stale:
            hot_symbols = await _get_hotlist_ws(redis)
            fetch_symbols = list(set(symbols) | hot_symbols)
        else:
            fetch_symbols = symbols

        interval = job_cfg.get("extra_config", {}).get("interval", "5m")
        bars = await YFinanceProvider().fetch_intraday_batch(fetch_symbols, from_dt, now, interval=interval)

        async with db_factory() as session:
            inserted = await bulk_insert_intraday_bars(session, bars, timeframe=interval)

        await redis.set(_LAST_POLL_KEY, now.isoformat())

        try:
            from app.tasks.alert_eval import evaluate_alerts_for_bar
            hot = await _get_hotlist(redis, db_factory)
            latest_by_symbol: dict[str, dict] = {}
            for b in bars:
                sym = b["symbol"]
                if sym not in latest_by_symbol or b["ts"] > latest_by_symbol[sym]["ts"]:
                    latest_by_symbol[sym] = b
            for sym, bar in latest_by_symbol.items():
                if sym not in hot:
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
            logger.exception("Failed to queue alert evaluations")

        logger.info("yfinance poll: %d symbols, %d bars fetched, %d upserted (ws_stale=%s)", len(fetch_symbols), len(bars), inserted, ws_stale)
        return {"symbols": len(fetch_symbols), "bars_fetched": len(bars), "bars_inserted": inserted, "ws_stale": ws_stale}

    finally:
        await engine.dispose()
        await redis.aclose()
