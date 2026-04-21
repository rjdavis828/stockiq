import logging
from datetime import date, datetime, timezone
from decimal import Decimal

import yfinance as yf

from app.ingestion.providers.base import BaseProvider, FundamentalsData, OHLCVBar, TickerInfo

logger = logging.getLogger(__name__)


class YFinanceProvider(BaseProvider):
    """Provider for fundamental data via yfinance (no API key required)."""

    async def fetch_daily(self, symbol: str, start: date, end: date) -> list[OHLCVBar]:
        raise NotImplementedError("Use PolygonProvider for OHLCV data")

    async def fetch_tickers(self) -> list[TickerInfo]:
        raise NotImplementedError("Use PolygonProvider for ticker data")

    async def fetch_fundamentals(self, symbol: str) -> list[FundamentalsData]:
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
