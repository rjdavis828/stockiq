from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "stock_analyzer",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.ingestion.tasks",
        "app.tasks.alert_eval",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/New_York",
    enable_utc=True,
    beat_schedule={
        "daily-ohlcv-backfill": {
            "task": "app.ingestion.tasks.ingest_daily_ohlcv",
            "schedule": crontab(hour=18, minute=30),
        },
        "ticker-refresh": {
            "task": "app.ingestion.tasks.refresh_tickers",
            "schedule": crontab(hour=6, minute=0, day_of_week="mon-fri"),
        },
        "run-active-scans": {
            "task": "app.ingestion.tasks.run_active_scans",
            "schedule": crontab(hour=19, minute=0),
        },
        "intraday-poll": {
            "task": "tasks.intraday_poll.poll_intraday_bars",
            "schedule": crontab(minute="*/5", hour="9-16", day_of_week="mon-fri"),
        },
        "fundamentals-weekly": {
            "task": "app.ingestion.tasks.ingest_fundamentals",
            "schedule": crontab(hour=5, minute=0, day_of_week="sun"),
        },
    },
)
