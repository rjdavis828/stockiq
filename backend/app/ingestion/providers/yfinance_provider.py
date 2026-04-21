import asyncio
import logging
import math
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Iterator

import yfinance as yf

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

from app.ingestion.providers.base import BaseProvider, FundamentalsData, OHLCVBar, TickerInfo

logger = logging.getLogger(__name__)


def _chunks(lst: list, size: int) -> Iterator[list]:
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def _make_bar(sym: str, ts_idx, row) -> dict | None:
    try:
        o, h, l, c, v = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"]), float(row["Volume"])
        if any(math.isnan(x) for x in (o, h, l, c)):
            return None
        if hasattr(ts_idx, "tzinfo") and ts_idx.tzinfo is not None:
            ts_utc = ts_idx.to_pydatetime().astimezone(timezone.utc)
        else:
            ts_utc = ts_idx.to_pydatetime().replace(tzinfo=timezone.utc)
        return {
            "symbol": sym, "ts": ts_utc,
            "open": o, "high": h, "low": l, "close": c,
            "volume": int(v) if not math.isnan(v) else 0,
            "vwap": None, "trade_count": None,
        }
    except Exception:
        return None


def _normalize_yf_intraday(df, symbols: list[str]) -> list[dict]:
    import pandas as pd
    bars = []
    if df is None or df.empty:
        return bars
    if isinstance(df.columns, pd.MultiIndex):
        for sym in symbols:
            if sym not in df.columns.get_level_values(0):
                continue
            sub = df[sym].dropna(subset=["Open", "Close"])
            for ts_idx, row in sub.iterrows():
                bar = _make_bar(sym, ts_idx, row)
                if bar:
                    bars.append(bar)
    else:
        sym = symbols[0] if len(symbols) == 1 else None
        if sym is None:
            return bars
        sub = df.dropna(subset=["Open", "Close"])
        for ts_idx, row in sub.iterrows():
            bar = _make_bar(sym, ts_idx, row)
            if bar:
                bars.append(bar)
    return bars


def _normalize_yf_daily(df, symbols: list[str]) -> list[OHLCVBar]:
    import pandas as pd
    bars: list[OHLCVBar] = []
    if df is None or df.empty:
        return bars
    if isinstance(df.columns, pd.MultiIndex):
        for sym in symbols:
            if sym not in df.columns.get_level_values(0):
                continue
            sub = df[sym].dropna(subset=["Open", "Close"])
            for ts_idx, row in sub.iterrows():
                try:
                    o, h, l, c, v = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"]), float(row["Volume"])
                    if any(math.isnan(x) for x in (o, h, l, c)):
                        continue
                    bar_date = ts_idx.date() if hasattr(ts_idx, "date") else ts_idx
                    bars.append(OHLCVBar(symbol=sym, date=bar_date, open=o, high=h, low=l, close=c, volume=int(v) if not math.isnan(v) else 0, adj_close=c, source="yfinance"))
                except Exception:
                    continue
    else:
        sym = symbols[0] if len(symbols) == 1 else None
        if sym is None:
            return bars
        sub = df.dropna(subset=["Open", "Close"])
        for ts_idx, row in sub.iterrows():
            try:
                o, h, l, c, v = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"]), float(row["Volume"])
                if any(math.isnan(x) for x in (o, h, l, c)):
                    continue
                bar_date = ts_idx.date() if hasattr(ts_idx, "date") else ts_idx
                bars.append(OHLCVBar(symbol=sym, date=bar_date, open=o, high=h, low=l, close=c, volume=int(v) if not math.isnan(v) else 0, adj_close=c, source="yfinance"))
            except Exception:
                continue
    return bars


class YFinanceProvider(BaseProvider):
    """Provider for OHLCV and fundamental data via yfinance (no API key required)."""

    async def fetch_daily(self, symbol: str, start: date, end: date) -> list[OHLCVBar]:
        from datetime import timedelta
        end_exclusive = end + timedelta(days=1)
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None,
            lambda: yf.download(symbol, start=str(start), end=str(end_exclusive), interval="1d", auto_adjust=True, progress=False),
        )
        return _normalize_yf_daily(df, [symbol])

    async def fetch_daily_batch(
        self, symbols: list[str], start: date, end: date
    ) -> list[OHLCVBar]:
        import os
        from app.config import settings
        from datetime import timedelta
        symbols = [s for s in symbols if not s.startswith("$")]
        end_exclusive = end + timedelta(days=1)
        bars: list[OHLCVBar] = []
        loop = asyncio.get_event_loop()

        # Stale cookies from a prior rate-limit response will cause all subsequent
        # requests to fail immediately. Clear before starting the batch.
        cookie_db = os.path.expanduser("~/.cache/py-yfinance/cookies.db")
        if os.path.exists(cookie_db):
            os.remove(cookie_db)

        consecutive_failures = 0
        for chunk in _chunks(symbols, settings.yfinance_chunk_size):
            try:
                df = await loop.run_in_executor(
                    None,
                    lambda c=chunk: yf.download(
                        c,
                        start=str(start),
                        end=str(end_exclusive),
                        interval="1d",
                        group_by="ticker",
                        auto_adjust=True,
                        progress=False,
                        threads=False,
                    ),
                )
                chunk_bars = _normalize_yf_daily(df, chunk)
                bars.extend(chunk_bars)
                if chunk_bars:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
            except Exception:
                logger.exception("yfinance daily chunk failed: %s", chunk)
                consecutive_failures += 1

            # Back off progressively if Yahoo starts returning empty results
            if consecutive_failures >= 3:
                backoff = min(settings.yfinance_chunk_sleep * 10, 120)
                logger.warning("3 consecutive empty chunks — backing off %.0fs", backoff)
                if os.path.exists(cookie_db):
                    os.remove(cookie_db)
                await asyncio.sleep(backoff)
                consecutive_failures = 0
            else:
                await asyncio.sleep(settings.yfinance_chunk_sleep)

        return bars

    async def fetch_intraday_batch(
        self,
        symbols: list[str],
        from_dt: datetime,
        to_dt: datetime,
        interval: str = "1m",
    ) -> list[dict]:
        from app.config import settings
        symbols = [s for s in symbols if not s.startswith("$")]
        bars: list[dict] = []
        for chunk in _chunks(symbols, settings.yfinance_chunk_size):
            try:
                df = yf.download(
                    chunk,
                    start=from_dt,
                    end=to_dt,
                    interval=interval,
                    group_by="ticker",
                    auto_adjust=True,
                    progress=False,
                    threads=True,
                )
                bars.extend(_normalize_yf_intraday(df, chunk))
            except Exception:
                logger.exception("yfinance chunk failed: %s", chunk)
            await asyncio.sleep(settings.yfinance_chunk_sleep)
        return bars

    async def fetch_tickers(self) -> list[TickerInfo]:
        raise NotImplementedError("Use PolygonProvider for ticker data")

    async def fetch_fundamentals(self, symbol: str) -> list[FundamentalsData]:
        if symbol.startswith("$"):
            return []
        try:
            ticker = yf.Ticker(symbol)
            results: list[FundamentalsData] = []

            info = ticker.info or {}
            pe_ratio = info.get("trailingPE") or info.get("forwardPE")
            market_cap = info.get("marketCap")

            stmt = ticker.quarterly_income_stmt
            if stmt is None or stmt.empty:
                logger.warning("No quarterly income stmt for %s", symbol)
                return results

            for col in stmt.columns:
                try:
                    period_str = self._col_to_period(col)
                    revenue = self._safe_decimal(stmt.loc["Total Revenue", col] if "Total Revenue" in stmt.index else None)
                    eps = self._safe_decimal(stmt.loc["Diluted EPS", col] if "Diluted EPS" in stmt.index else None)

                    reported_at: datetime | None = None
                    if hasattr(col, "to_pydatetime"):
                        reported_at = col.to_pydatetime().replace(tzinfo=timezone.utc)
                    elif isinstance(col, datetime):
                        reported_at = col.replace(tzinfo=timezone.utc)

                    results.append(
                        FundamentalsData(
                            symbol=symbol,
                            period=period_str,
                            revenue=revenue,
                            eps=eps,
                            pe_ratio=Decimal(str(round(pe_ratio, 4))) if pe_ratio else None,
                            market_cap=int(market_cap) if market_cap else None,
                            reported_at=reported_at,
                        )
                    )
                except Exception:
                    logger.exception("Error parsing quarter %s for %s", col, symbol)
                    continue

            return results

        except Exception:
            logger.exception("fetch_fundamentals failed for %s", symbol)
            return []

    @staticmethod
    def _col_to_period(col) -> str:
        """Convert a pandas Timestamp column label to 'YYYY-QN' string."""
        try:
            dt = col.to_pydatetime() if hasattr(col, "to_pydatetime") else col
            q = (dt.month - 1) // 3 + 1
            return f"{dt.year}-Q{q}"
        except Exception:
            return str(col)

    @staticmethod
    def _safe_decimal(val) -> Decimal | None:
        try:
            if val is None:
                return None
            f = float(val)
            if f != f:  # NaN check
                return None
            return Decimal(str(round(f, 4)))
        except Exception:
            return None
