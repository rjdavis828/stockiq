"""
Manual backfill script.

Usage:
    python -m app.ingestion.backfill --symbol AAPL --years 1
    python -m app.ingestion.backfill --symbol AAPL MSFT GOOGL --start 2024-01-01
"""
import argparse
import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.ingestion.normalizer import bulk_insert_daily_bars, upsert_tickers
from app.ingestion.providers.base import TickerInfo
from app.ingestion.providers.polygon import PolygonProvider, _RATE_LIMIT_DELAY

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def backfill(symbols: list[str], start: date, end: date) -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    provider = PolygonProvider()

    try:
        async with session_factory() as session:
            # Seed ticker rows so the normalizer can resolve symbol → ticker_id
            now = datetime.now(tz=timezone.utc)
            ticker_infos = [
                TickerInfo(symbol=s, name=s, active=True, updated_at=now)
                for s in symbols
            ]
            await upsert_tickers(session, ticker_infos)

            # Fetch OHLCV with rate-limit delay between symbols
            all_bars = await provider.fetch_daily_batch(symbols, start, end, delay=_RATE_LIMIT_DELAY)
            for symbol, bars in all_bars.items():
                if bars:
                    inserted = await bulk_insert_daily_bars(session, bars)
                    logger.info("Inserted %d bars for %s", inserted, symbol)
                else:
                    logger.warning("No bars returned for %s", symbol)
    finally:
        await provider.close()
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill OHLCV data from Polygon.io")
    parser.add_argument("--symbol", nargs="+", required=True, help="Ticker symbol(s)")
    parser.add_argument("--years", type=int, default=1, help="Years of history to fetch")
    parser.add_argument("--start", type=date.fromisoformat, help="Start date (overrides --years)")
    parser.add_argument("--end", type=date.fromisoformat, default=date.today(), help="End date")
    args = parser.parse_args()

    start = args.start or (args.end - timedelta(days=365 * args.years))
    asyncio.run(backfill(args.symbol, start, args.end))


if __name__ == "__main__":
    main()
