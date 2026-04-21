from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from typing import List

from app.api.deps import get_current_user, get_db
from app.db.models import Scan, ScannerResult, User
from app.scanner.engine import ScannerEngine
from app.schemas.scanner import (
    ScannerCreateRequest,
    ScannerUpdateRequest,
    ScannerResponse,
    ScannerRunResponse,
    ScannerResultItem,
)

router = APIRouter(prefix="/scans", tags=["scans"])


@router.get("", response_model=List[ScannerResponse])
async def list_scans(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    query = (
        select(Scan)
        .where(Scan.user_id == str(user.id))
        .order_by(Scan.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(query)
    scans = result.scalars().all()
    return scans


@router.post("", response_model=ScannerRunResponse)
async def create_and_run_scan(
    req: ScannerCreateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    scan = Scan(
        user_id=str(user.id),
        name=req.name,
        description=req.description,
        conditions=req.conditions,
        universe_filter=req.universe.model_dump() if req.universe else None,
        logic=req.logic,
        active=req.active,
        last_run=now,
        created_at=now,
        updated_at=now,
    )
    session.add(scan)
    await session.flush()

    engine = ScannerEngine(session)
    results, count = await engine.run_scan(scan)

    for result in results:
        sr = ScannerResult(
            scan_id=scan.id,
            ticker_id=result["ticker_id"],
            triggered_at=datetime.fromisoformat(result["triggered_at"]),
            condition_snapshot=result["condition_snapshot"],
            values_snapshot=result["values_snapshot"],
        )
        session.add(sr)

    await session.commit()
    return ScannerRunResponse(scan_id=scan.id, run_at=now.isoformat(), results=[
        ScannerResultItem(
            ticker_id=r["ticker_id"],
            symbol=r["symbol"],
            triggered_at=r["triggered_at"],
            condition_snapshot=r["condition_snapshot"],
            values_snapshot=r["values_snapshot"],
        )
        for r in results
    ], total_matched=count)


@router.get("/{scan_id}", response_model=ScannerResponse)
async def get_scan(
    scan_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    query = select(Scan).where(and_(Scan.id == scan_id, Scan.user_id == str(user.id)))
    result = await session.execute(query)
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404)
    return scan


@router.put("/{scan_id}", response_model=ScannerResponse)
async def update_scan(
    scan_id: int,
    req: ScannerUpdateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    query = select(Scan).where(and_(Scan.id == scan_id, Scan.user_id == str(user.id)))
    result = await session.execute(query)
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404)

    if req.name is not None:
        scan.name = req.name
    if req.description is not None:
        scan.description = req.description
    if req.conditions is not None:
        scan.conditions = req.conditions
    if req.universe is not None:
        scan.universe_filter = req.universe.model_dump()
    if req.logic is not None:
        scan.logic = req.logic
    if req.active is not None:
        scan.active = req.active
    scan.updated_at = datetime.now(timezone.utc)

    await session.commit()
    return scan


@router.delete("/{scan_id}")
async def delete_scan(
    scan_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    query = select(Scan).where(and_(Scan.id == scan_id, Scan.user_id == str(user.id)))
    result = await session.execute(query)
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404)

    session.delete(scan)
    await session.commit()
    return {"deleted": True}


@router.post("/{scan_id}/run", response_model=ScannerRunResponse)
async def run_scan(
    scan_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    query = select(Scan).where(and_(Scan.id == scan_id, Scan.user_id == str(user.id)))
    result = await session.execute(query)
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404)

    now = datetime.now(timezone.utc)
    engine = ScannerEngine(session)
    results, count = await engine.run_scan(scan)

    for result in results:
        sr = ScannerResult(
            scan_id=scan.id,
            ticker_id=result["ticker_id"],
            triggered_at=datetime.fromisoformat(result["triggered_at"]),
            condition_snapshot=result["condition_snapshot"],
            values_snapshot=result["values_snapshot"],
        )
        session.add(sr)

    scan.last_run = now
    await session.commit()
    return ScannerRunResponse(scan_id=scan.id, run_at=now.isoformat(), results=[
        ScannerResultItem(
            ticker_id=r["ticker_id"],
            symbol=r["symbol"],
            triggered_at=r["triggered_at"],
            condition_snapshot=r["condition_snapshot"],
            values_snapshot=r["values_snapshot"],
        )
        for r in results
    ], total_matched=count)


@router.get("/{scan_id}/results")
async def get_scan_results(
    scan_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    query = select(Scan).where(and_(Scan.id == scan_id, Scan.user_id == str(user.id)))
    result = await session.execute(query)
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404)

    results_query = (
        select(ScannerResult)
        .where(ScannerResult.scan_id == scan_id)
        .order_by(ScannerResult.triggered_at.desc())
        .limit(limit)
        .offset(offset)
    )
    results = await session.execute(results_query)
    return results.scalars().all()
