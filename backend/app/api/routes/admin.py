from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_superuser
from app.db.models import User

router = APIRouter(prefix="/admin", tags=["admin"])


class TaskEnqueued(BaseModel):
    task_id: str
    task_name: str


class TaskStatus(BaseModel):
    task_id: str
    status: str
    result: object | None = None


def _enqueue(task, *args) -> TaskEnqueued:
    result = task.delay(*args)
    return TaskEnqueued(task_id=result.id, task_name=task.name)


@router.post("/tasks/ingest-daily-ohlcv", response_model=TaskEnqueued)
async def trigger_ingest_daily_ohlcv(_: User = Depends(get_superuser)):
    from app.ingestion.tasks import ingest_daily_ohlcv
    return _enqueue(ingest_daily_ohlcv)


@router.post("/tasks/refresh-tickers", response_model=TaskEnqueued)
async def trigger_refresh_tickers(_: User = Depends(get_superuser)):
    from app.ingestion.tasks import refresh_tickers
    return _enqueue(refresh_tickers)


@router.post("/tasks/run-active-scans", response_model=TaskEnqueued)
async def trigger_run_active_scans(_: User = Depends(get_superuser)):
    from app.ingestion.tasks import run_active_scans
    return _enqueue(run_active_scans)


@router.post("/tasks/poll-intraday-bars", response_model=TaskEnqueued)
async def trigger_poll_intraday_bars(_: User = Depends(get_superuser)):
    from app.ingestion.tasks import poll_intraday_bars
    return _enqueue(poll_intraday_bars)


@router.post("/tasks/ingest-fundamentals", response_model=TaskEnqueued)
async def trigger_ingest_fundamentals(_: User = Depends(get_superuser)):
    from app.ingestion.tasks import ingest_fundamentals
    return _enqueue(ingest_fundamentals)


@router.get("/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str, _: User = Depends(get_superuser)):
    from celery_worker import celery_app
    result = celery_app.AsyncResult(task_id)
    if result.state == "PENDING" and result.result is None:
        # Celery returns PENDING for unknown IDs too
        pass
    return TaskStatus(
        task_id=task_id,
        status=result.state,
        result=result.result if result.ready() else None,
    )
