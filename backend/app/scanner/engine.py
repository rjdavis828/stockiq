import pandas as pd
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import selectinload

from app.db.models import Fundamental, Ticker, OHLCVDaily, ScannerResult, Scan
from app.scanner.indicators import IndicatorCompute
from app.schemas.scanner import Condition, FUNDAMENTAL_FIELDS, UniverseFilter


class ScannerEngine:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def run_scan(
        self, scan: Scan, lookback_days: int = 252
    ) -> tuple[List[Dict[str, Any]], int]:
        """Evaluate scan conditions across universe. Returns (results, count)."""
        conditions = scan.conditions
        universe_filter = scan.universe_filter or {}
        logic = scan.logic.upper()

        tickers = await self._get_universe_tickers(universe_filter)
        results = []

        for ticker in tickers:
            df = await self._fetch_ohlcv(ticker.id, lookback_days)
            if df.empty or len(df) < 50:
                continue

            fundamentals = await self._fetch_latest_fundamentals(ticker.id)

            if self._evaluate_conditions(df, conditions, logic, fundamentals):
                indicator_vals = self._snapshot_values(df, conditions)
                results.append(
                    {
                        "ticker_id": ticker.id,
                        "symbol": ticker.symbol,
                        "triggered_at": datetime.now(timezone.utc).isoformat(),
                        "condition_snapshot": conditions,
                        "values_snapshot": indicator_vals,
                    }
                )

        return results, len(results)

    async def _get_universe_tickers(self, universe_filter: Dict) -> List[Ticker]:
        """Fetch tickers matching universe filter."""
        ALLOWED_EXCHANGES = {"NYSE", "NASDAQ", "AMEX"}
        ALLOWED_SECTORS = {
            "Technology", "Healthcare", "Financials", "Energy", "Consumer",
            "Industrials", "Materials", "Real Estate", "Utilities", "Communications"
        }

        query = select(Ticker).where(Ticker.active == True)

        if "min_market_cap" in universe_filter and universe_filter["min_market_cap"]:
            query = query.where(Ticker.market_cap >= universe_filter["min_market_cap"])
        if "max_market_cap" in universe_filter and universe_filter["max_market_cap"]:
            query = query.where(Ticker.market_cap <= universe_filter["max_market_cap"])
        if "exchanges" in universe_filter and universe_filter["exchanges"]:
            exchanges = [e for e in universe_filter["exchanges"] if e in ALLOWED_EXCHANGES]
            if exchanges:
                query = query.where(Ticker.exchange.in_(exchanges))
        if "sectors" in universe_filter and universe_filter["sectors"]:
            sectors = [s for s in universe_filter["sectors"] if s in ALLOWED_SECTORS]
            if sectors:
                query = query.where(Ticker.sector.in_(sectors))

        result = await self.session.execute(query)
        return result.scalars().all()

    async def _fetch_latest_fundamentals(self, ticker_id: int) -> Dict[str, float]:
        """Return the most recent fundamental values for a ticker as a flat dict."""
        result = await self.session.execute(
            select(Fundamental)
            .where(Fundamental.ticker_id == ticker_id)
            .order_by(Fundamental.period.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return {}
        return {
            "eps": float(row.eps) if row.eps is not None else None,
            "pe_ratio": float(row.pe_ratio) if row.pe_ratio is not None else None,
            "revenue": float(row.revenue) if row.revenue is not None else None,
            "market_cap": float(row.market_cap) if row.market_cap is not None else None,
        }

    async def _fetch_ohlcv(self, ticker_id: int, lookback_days: int) -> pd.DataFrame:
        """Fetch daily OHLCV for a ticker."""
        cutoff = datetime.now(timezone.utc).date() - timedelta(days=lookback_days)
        query = (
            select(OHLCVDaily)
            .options(selectinload(OHLCVDaily.ticker))
            .where(OHLCVDaily.ticker_id == ticker_id)
            .where(OHLCVDaily.date >= cutoff)
            .order_by(OHLCVDaily.date)
        )
        result = await self.session.execute(query)
        rows = result.scalars().all()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(
            [
                {
                    "date": r.date,
                    "open": float(r.open),
                    "high": float(r.high),
                    "low": float(r.low),
                    "close": float(r.close),
                    "volume": r.volume,
                }
                for r in rows
            ]
        )
        df.set_index("date", inplace=True)
        return df

    def _evaluate_conditions(
        self, df: pd.DataFrame, conditions: List[Dict], logic: str,
        fundamentals: Optional[Dict[str, float]] = None,
    ) -> bool:
        """Evaluate all conditions and apply AND/OR logic."""
        evals = [self._eval_condition(df, c, fundamentals or {}) for c in conditions]
        if logic == "AND":
            return all(evals)
        else:
            return any(evals)

    def _eval_condition(self, df: pd.DataFrame, cond: Dict, fundamentals: Dict[str, float] = {}) -> bool:
        """Evaluate a single condition against DataFrame."""
        op = cond.get("operator")

        if cond.get("indicator"):
            ind_name = cond["indicator"].upper()
            period = cond.get("period", 20)
            ind_val = self._compute_indicator(df, ind_name, period)

            if op in ("crosses_above", "crosses_below"):
                if cond.get("compare_to", {}).get("indicator"):
                    compare_ind = cond["compare_to"]["indicator"].upper()
                    compare_period = cond["compare_to"].get("period", 20)
                    compare_val = self._compute_indicator(df, compare_ind, compare_period)
                    return self._crossover_check(ind_val, compare_val, op)

            elif op == "between":
                vals = cond.get("value", [])
                return vals[0] <= IndicatorCompute.get_last_value(ind_val) <= vals[1]
            elif op == "outside":
                vals = cond.get("value", [])
                last = IndicatorCompute.get_last_value(ind_val)
                return last < vals[0] or last > vals[1]
            elif op == "gt":
                return IndicatorCompute.get_last_value(ind_val) > cond.get("value", 0)
            elif op == "lt":
                return IndicatorCompute.get_last_value(ind_val) < cond.get("value", 100)
            elif op == "above_upper":
                if ind_name == "BOLLINGER_BANDS" or ind_name == "BBANDS":
                    upper, _, _ = IndicatorCompute.bollinger_bands(df, period)
                    return float(df["close"].iloc[-1]) > IndicatorCompute.get_last_value(upper)
            elif op == "below_lower":
                if ind_name == "BOLLINGER_BANDS" or ind_name == "BBANDS":
                    _, _, lower = IndicatorCompute.bollinger_bands(df, period)
                    return float(df["close"].iloc[-1]) < IndicatorCompute.get_last_value(lower)

        elif cond.get("field") == "volume":
            vol = float(df["volume"].iloc[-1])
            if op == "greater_than":
                compare = cond.get("compare_to", {})
                if compare.get("indicator"):
                    mult = compare.get("multiplier", 1.0)
                    avg = IndicatorCompute.avg_volume(df, compare.get("period", 20))
                    return vol > IndicatorCompute.get_last_value(avg) * mult
            return False

        elif cond.get("field") in FUNDAMENTAL_FIELDS:
            field = cond["field"]
            fval = fundamentals.get(field)
            if fval is None:
                return False
            threshold = cond.get("value", 0)
            if op in ("gt", "greater_than"):
                return fval > threshold
            elif op in ("lt", "less_than"):
                return fval < threshold
            elif op == "between":
                vals = cond.get("value", [])
                return len(vals) == 2 and vals[0] <= fval <= vals[1]
            elif op == "outside":
                vals = cond.get("value", [])
                return len(vals) == 2 and (fval < vals[0] or fval > vals[1])
            return False

        return False

    def _compute_indicator(self, df: pd.DataFrame, name: str, period: int) -> any:
        """Dispatch to IndicatorCompute method."""
        name_lower = name.lower()
        if name_lower == "sma":
            return IndicatorCompute.sma(df, period)
        elif name_lower == "ema":
            return IndicatorCompute.ema(df, period)
        elif name_lower == "rsi":
            return IndicatorCompute.rsi(df, period)
        elif name_lower == "macd":
            macd, sig, _ = IndicatorCompute.macd(df)
            return macd
        elif name_lower == "stochastic":
            k, _ = IndicatorCompute.stochastic(df, period)
            return k
        elif name_lower == "cci":
            return IndicatorCompute.cci(df, period)
        elif name_lower == "atr":
            return IndicatorCompute.atr(df, period)
        elif name_lower == "obv":
            return IndicatorCompute.obv(df)
        elif name_lower == "mfi":
            return IndicatorCompute.mfi(df, period)
        elif name_lower == "avg_volume":
            return IndicatorCompute.avg_volume(df, period)
        return pd.Series([0] * len(df))

    def _crossover_check(self, series1: pd.Series, series2: pd.Series, op: str) -> bool:
        """Check if series1 crossed above/below series2 in last bar."""
        s1 = series1.dropna()
        s2 = series2.dropna()

        if len(s1) < 2 or len(s2) < 2:
            return False

        prev_s1, curr_s1 = float(s1.iloc[-2]), float(s1.iloc[-1])
        prev_s2, curr_s2 = float(s2.iloc[-2]), float(s2.iloc[-1])

        if op == "crosses_above":
            return prev_s1 <= prev_s2 and curr_s1 > curr_s2
        elif op == "crosses_below":
            return prev_s1 >= prev_s2 and curr_s1 < curr_s2
        return False

    def evaluate_condition_on_bar(self, df: pd.DataFrame, condition: Dict, fundamentals: Dict[str, float] = {}) -> bool:
        """Public wrapper for evaluating a single condition; used by alert evaluator."""
        return self._eval_condition(df, condition, fundamentals)

    def _snapshot_values(self, df: pd.DataFrame, conditions: List[Dict]) -> Dict[str, float]:
        """Capture current indicator values for snapshot."""
        snapshot = {}
        for i, cond in enumerate(conditions):
            if cond.get("indicator"):
                name = cond["indicator"].upper()
                period = cond.get("period", 20)
                val = self._compute_indicator(df, name, period)
                snapshot[f"cond_{i}_{name}"] = float(IndicatorCompute.get_last_value(val))
        return snapshot
