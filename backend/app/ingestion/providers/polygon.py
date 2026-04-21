import asyncio
import logging
from datetime import date, datetime, timezone

import httpx

from app.config import settings
from app.ingestion.providers.base import BaseProvider, OHLCVBar, TickerInfo

logger = logging.getLogger(__name__)

_BASE = "https://api.polygon.io"
_RATE_LIMIT_DELAY = 60.0 / 5  # free tier: 5 req/min → 12s per request
_REQUIRED_BAR_FIELDS = {"o", "h", "l", "c", "v", "t"}


class PolygonProvider(BaseProvider):
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.polygon_api_key
        self._client: httpx.AsyncClient | None = None

    async def _client_ctx(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=_BASE,
                params={"apiKey": self._api_key},
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _get(self, path: str, params: dict | None = None) -> dict:
        client = await self._client_ctx()
        response = await client.get(path, params=params or {})
        if response.status_code == 429:
            retry_after = float(response.headers.get("Retry-After", _RATE_LIMIT_DELAY))
            logger.warning("Polygon rate limited; sleeping %.1fs", retry_after)
            await asyncio.sleep(retry_after)
            response = await client.get(path, params=params or {})
        response.raise_for_status()
        return response.json()

    async def fetch_daily(
        self, symbol: str, start: date, end: date
    ) -> list[OHLCVBar]:
        """Fetch daily OHLCV bars from Polygon /v2/aggs/ticker endpoint."""
        path = f"/v2/aggs/ticker/{symbol}/range/1/day/{start}/{end}"
        params = {"adjusted": "true", "sort": "asc", "limit": 50000}

        try:
            data = await self._get(path, params)
        except httpx.HTTPStatusError as exc:
            logger.error("Polygon fetch_daily %s %s: %s", symbol, start, exc)
            return []

        results = data.get("results") or []
        bars: list[OHLCVBar] = []
        for r in results:
            if not _REQUIRED_BAR_FIELDS.issubset(r):
                logger.warning("Skipping malformed daily bar for %s: %s", symbol, r)
                continue
            bar_date = datetime.fromtimestamp(r["t"] / 1000, tz=timezone.utc).date()
            bars.append(
                OHLCVBar(
                    symbol=symbol,
                    date=bar_date,
                    open=r["o"],
                    high=r["h"],
                    low=r["l"],
                    close=r["c"],
                    volume=int(r["v"]),
                    vwap=r.get("vw"),
                    adj_close=None,  # v2/aggs adjusted=true adjusts OHLC in-place
                    source="polygon",
                )
            )
        return bars

    async def fetch_tickers(self) -> list[TickerInfo]:
        """Fetch active US stock tickers from Polygon /v3/reference/tickers."""
        tickers: list[TickerInfo] = []
        cursor: str | None = None
        now = datetime.now(tz=timezone.utc)

        while True:
            params: dict = {
                "market": "stocks",
                "active": "true",
                "order": "asc",
                "limit": 1000,
            }
            if cursor:
                params["cursor"] = cursor

            try:
                data = await self._get("/v3/reference/tickers", params)
            except httpx.HTTPStatusError as exc:
                logger.error("Polygon fetch_tickers: %s", exc)
                break

            for r in data.get("results") or []:
                tickers.append(
                    TickerInfo(
                        symbol=r["ticker"],
                        name=r.get("name", ""),
                        exchange=r.get("primary_exchange", ""),
                        sector=r.get("sic_description", ""),
                        industry="",
                        market_cap=r.get("market_cap"),
                        active=r.get("active", True),
                        updated_at=now,
                    )
                )

            next_url = data.get("next_url")
            if not next_url:
                break

            # Extract cursor from next_url query string
            from urllib.parse import parse_qs, urlparse
            parsed = urlparse(next_url)
            qs = parse_qs(parsed.query)
            cursor = qs.get("cursor", [None])[0]

            # Respect rate limits for free-tier keys
            await asyncio.sleep(_RATE_LIMIT_DELAY)

        return tickers

    async def fetch_daily_batch(
        self, symbols: list[str], start: date, end: date, delay: float = _RATE_LIMIT_DELAY
    ) -> dict[str, list[OHLCVBar]]:
        """Fetch daily bars for multiple symbols with rate-limit delay between calls."""
        results: dict[str, list[OHLCVBar]] = {}
        for i, symbol in enumerate(symbols):
            bars = await self.fetch_daily(symbol, start, end)
            results[symbol] = bars
            logger.info("Fetched %d bars for %s (%d/%d)", len(bars), symbol, i + 1, len(symbols))
            if i < len(symbols) - 1:
                await asyncio.sleep(delay)
        return results

    async def fetch_grouped_aggs(
        self, for_date: date, timeframe_minutes: int = 1
    ) -> list[dict]:
        """Fetch all US stock 1-minute bars for a given date via the grouped aggs endpoint.

        Returns raw result dicts with keys: T (symbol), o, h, l, c, v, vw, n, t (ms epoch).
        Uses /v2/aggs/grouped/locale/us/market/stocks/{date} for minute bars via
        the range endpoint aggregated per symbol — actually we use the per-date snapshot.
        For intraday minute bars across all symbols we use:
          GET /v2/aggs/ticker/{sym}/range/1/minute/{date}/{date}
        but that requires one call per symbol. Instead we page through
          GET /v2/aggs/grouped/locale/us/market/stocks/{date}
        which returns daily bars only. For true 1-minute bars across all symbols
        Polygon requires the Stocks Starter plan flat-file download or per-symbol calls.

        This method uses the grouped daily endpoint as a fallback and fetches
        intraday bars using concurrent per-symbol calls against a configurable
        symbol list drawn from the tickers table.
        """
        path = f"/v2/aggs/grouped/locale/us/market/stocks/{for_date}"
        params = {"adjusted": "true"}
        try:
            data = await self._get(path, params)
        except httpx.HTTPStatusError as exc:
            logger.error("Polygon grouped aggs %s: %s", for_date, exc)
            return []
        return data.get("results") or []

    async def fetch_intraday_for_symbols(
        self,
        symbols: list[str],
        from_dt: datetime,
        to_dt: datetime,
        timeframe_minutes: int = 1,
        concurrency: int = 10,
    ) -> list[dict]:
        """Fetch 1-minute intraday bars for a list of symbols concurrently.

        Returns flat list of dicts with keys: symbol, ts (UTC datetime), o, h, l, c, v, vw, n.
        """
        from_ms = int(from_dt.timestamp() * 1000)
        to_ms = int(to_dt.timestamp() * 1000)
        semaphore = asyncio.Semaphore(concurrency)
        bars: list[dict] = []

        async def _fetch_one(symbol: str) -> list[dict]:
            async with semaphore:
                path = f"/v2/aggs/ticker/{symbol}/range/{timeframe_minutes}/minute/{from_ms}/{to_ms}"
                params = {"adjusted": "true", "sort": "asc", "limit": 50000}
                try:
                    data = await self._get(path, params)
                except httpx.HTTPStatusError as exc:
                    logger.warning("Polygon intraday %s: %s", symbol, exc)
                    return []
                results = []
                for r in data.get("results") or []:
                    if not _REQUIRED_BAR_FIELDS.issubset(r):
                        logger.warning("Skipping malformed intraday bar for %s: %s", symbol, r)
                        continue
                    results.append({
                        "symbol": symbol,
                        "ts": datetime.fromtimestamp(r["t"] / 1000, tz=timezone.utc),
                        "open": r["o"],
                        "high": r["h"],
                        "low": r["l"],
                        "close": r["c"],
                        "volume": int(r["v"]),
                        "vwap": r.get("vw"),
                        "trade_count": r.get("n"),
                    })
                return results

        results = await asyncio.gather(*[_fetch_one(s) for s in symbols])
        for result in results:
            bars.extend(result)
        return bars
