import logging
import threading

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
        "app.tasks.ws_finnhub",
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
            "task": "app.ingestion.tasks.poll_yfinance_bars",
            "schedule": crontab(minute="*/15", hour="9-16", day_of_week="mon-fri"),
        },
        "ws-bar-flush": {
            "task": "app.tasks.ws_finnhub.flush_ws_bars",
            "schedule": crontab(minute="*", hour="9-16", day_of_week="mon-fri"),
        },
        "fundamentals-weekly": {
            "task": "app.ingestion.tasks.ingest_fundamentals",
            "schedule": crontab(hour=5, minute=0, day_of_week="sun"),
        },
    },
)

# --- Per-task log capture ---

_current_task_id = threading.local()
_redis_conn_local = threading.local()


def _get_sync_redis():
    if not hasattr(_redis_conn_local, "conn"):
        import redis as _sync_redis
        _redis_conn_local.conn = _sync_redis.from_url(
            settings.redis_url, socket_connect_timeout=2
        )
    return _redis_conn_local.conn


class _TaskLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
        )

    def emit(self, record: logging.LogRecord) -> None:
        task_id = getattr(_current_task_id, "value", None)
        if not task_id:
            return
        try:
            msg = self.format(record)
            r = _get_sync_redis()
            key = f"task_logs:{task_id}"
            r.rpush(key, msg)
            r.expire(key, 7200)
        except Exception:
            pass


def _install_task_log_handler() -> None:
    from celery.signals import task_failure, task_postrun, task_prerun

    logging.getLogger().addHandler(_TaskLogHandler())

    @task_prerun.connect
    def _on_prerun(task_id: str, **_kw) -> None:
        _current_task_id.value = task_id

    @task_postrun.connect
    def _on_postrun(**_kw) -> None:
        _current_task_id.value = None

    @task_failure.connect
    def _on_failure(**_kw) -> None:
        _current_task_id.value = None


from celery.signals import worker_process_init  # noqa: E402


@worker_process_init.connect
def _setup_worker_logging(**_kw) -> None:
    _install_task_log_handler()
