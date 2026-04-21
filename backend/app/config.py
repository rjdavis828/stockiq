from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://stock:password@localhost:5432/stockdb"
    database_url_sync: str = "postgresql://stock:password@localhost:5432/stockdb"

    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 60

    secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if v == "change-me-in-production":
            raise ValueError("SECRET_KEY must be explicitly set in production")
        return v

    polygon_api_key: str = ""
    alpha_vantage_api_key: str = ""
    finnhub_api_key: str = ""

    yfinance_chunk_size: int = 100
    yfinance_chunk_sleep: float = 5.0
    finnhub_hotlist_max: int = 50
    ws_stale_threshold_s: int = 90

    ingest_universe: str = "SP500"
    backfill_years: int = 5
    intraday_timeframes: str = "1m,5m,15m,1h"

    max_scan_universe_size: int = 5000
    scanner_cache_ttl: int = 300

    cors_origins: list[str] = ["http://localhost:5173"]

    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "alerts@stockanalyzer.local"
    smtp_tls: bool = True

    ws_bar_channel_prefix: str = "bars"
    intraday_poll_concurrency: int = 20


settings = Settings()
