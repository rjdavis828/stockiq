import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_redis, get_superuser
from app.db.models import JobConfig, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


class TaskEnqueued(BaseModel):
    task_id: str
    task_name: str


class TaskStatus(BaseModel):
    task_id: str
    status: str
    result: object | None = None


class ActiveTaskInfo(BaseModel):
    task_id: str
    task_name: str
    time_start: float | None = None


class TaskLogs(BaseModel):
    task_id: str
    logs: list[str]


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


@router.get("/tasks/active", response_model=list[ActiveTaskInfo])
async def list_active_tasks(_: User = Depends(get_superuser)):
    from celery_worker import celery_app

    def _inspect():
        inspector = celery_app.control.inspect(timeout=2.0)
        return inspector.active() or {}

    active = await asyncio.get_event_loop().run_in_executor(None, _inspect)
    tasks = []
    for worker_tasks in active.values():
        for t in worker_tasks:
            tasks.append(
                ActiveTaskInfo(
                    task_id=t["id"],
                    task_name=t["name"],
                    time_start=t.get("time_start"),
                )
            )
    return tasks


@router.delete("/tasks/{task_id}")
async def revoke_task(task_id: str, _: User = Depends(get_superuser)):
    from celery_worker import celery_app

    await asyncio.get_event_loop().run_in_executor(
        None, lambda: celery_app.control.revoke(task_id, terminate=True)
    )
    return {"revoked": task_id}


@router.get("/tasks/{task_id}/logs", response_model=TaskLogs)
async def get_task_logs(
    task_id: str,
    _: User = Depends(get_superuser),
    redis=Depends(get_redis),
):
    key = f"task_logs:{task_id}"
    raw = await redis.lrange(key, 0, -1)
    return TaskLogs(task_id=task_id, logs=raw or [])


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


# --- Job Configuration ---

class JobConfigResponse(BaseModel):
    id: int
    job_name: str
    enabled: bool
    universe_filter: str
    cron_schedule: str | None
    extra_config: dict
    updated_at: str


class JobConfigUpdate(BaseModel):
    enabled: bool | None = None
    universe_filter: str | None = None
    cron_schedule: str | None = None
    extra_config: dict | None = None


def _serialize_job_config(c: JobConfig) -> JobConfigResponse:
    return JobConfigResponse(
        id=c.id,
        job_name=c.job_name,
        enabled=c.enabled,
        universe_filter=c.universe_filter,
        cron_schedule=c.cron_schedule,
        extra_config=c.extra_config or {},
        updated_at=c.updated_at.isoformat(),
    )


@router.get("/job-configs", response_model=list[JobConfigResponse])
async def list_job_configs(
    _: User = Depends(get_superuser),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(select(JobConfig).order_by(JobConfig.job_name))
    return [_serialize_job_config(c) for c in result.scalars().all()]


@router.put("/job-configs/{job_name}", response_model=JobConfigResponse)
async def update_job_config(
    job_name: str,
    body: JobConfigUpdate,
    _: User = Depends(get_superuser),
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    result = await session.execute(select(JobConfig).where(JobConfig.job_name == job_name))
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="Job config not found")

    # Store old values for cache cleanup
    old_universe_filter = config.universe_filter

    # Update only the fields that were provided
    if body.enabled is not None:
        config.enabled = body.enabled
    if body.universe_filter is not None:
        config.universe_filter = body.universe_filter
    if body.cron_schedule is not None:
        config.cron_schedule = body.cron_schedule
    if body.extra_config is not None:
        config.extra_config = body.extra_config
    config.updated_at = datetime.now(timezone.utc)

    # Commit and refresh to ensure changes are persisted
    await session.commit()
    await session.refresh(config)

    # Invalidate all relevant caches so worker picks up changes on next task execution
    cache_keys_to_delete = [
        f"job_config:{job_name}",
        f"intraday_poll:symbols:{old_universe_filter}",
    ]

    # If universe_filter changed, also delete the new one
    if config.universe_filter != old_universe_filter:
        cache_keys_to_delete.append(f"intraday_poll:symbols:{config.universe_filter}")

    # Delete all cache keys
    for key in cache_keys_to_delete:
        await redis.delete(key)
        logger.info(f"Deleted cache key: {key}")

    logger.info(
        f"Updated job config {job_name}: "
        f"enabled={config.enabled}, "
        f"universe_filter={config.universe_filter}, "
        f"cron_schedule={config.cron_schedule}, "
        f"extra_config={config.extra_config}"
    )

    return _serialize_job_config(config)
