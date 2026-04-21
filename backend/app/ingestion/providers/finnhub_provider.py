import logging
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.ingestion.providers.base import BaseProvider, OHLCVBar, TickerInfo

logger = logging.getLogger(__name__)

_BASE = "https://finnhub.io/api/v1"


class FinnhubProvider(BaseProvider):
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.finnhub_api_key
        self._client: httpx.AsyncClient | None = None

    async def _client_ctx(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=_BASE,
                headers={"X-Finnhub-Token": self._api_key},
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _get(self, path: str, params: dict | None = None) -> dict | list:
        client = await self._client_ctx()
        response = await client.get(path, params=params or {})
        response.raise_for_status()
        return response.json()

    async def fetch_tickers(self) -> list[TickerInfo]:
        """Fetch US stock symbols from Finnhub /stock/symbol with exchange=US."""
        now = datetime.now(tz=timezone.utc)
        try:
            data = await self._get("/stock/symbol", {"exchange": "US"})
        except httpx.HTTPStatusError as exc:
            logger.error("Finnhub fetch_tickers failed: %s", exc)
            return []

        tickers: list[TickerInfo] = []
        for r in data or []:
            symbol = r.get("symbol", "")
            if not symbol:
                continue
            tickers.append(
                TickerInfo(
                    symbol=symbol,
                    name=r.get("description", ""),
                    exchange=r.get("mic", ""),
                    sector="",
                    industry="",
                    market_cap=None,
                    active=True,
                    updated_at=now,
                )
            )

        logger.info("Finnhub returned %d US stock symbols", len(tickers))
        return tickers

    async def fetch_daily(self, symbol: str, start, end) -> list[OHLCVBar]:
        raise NotImplementedError("Use yfinance for OHLCV data")
