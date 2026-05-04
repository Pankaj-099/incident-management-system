"""
Observability API — Phase 5

GET /metrics/full        → full snapshot: queue, signals, work items, MTTR, breakdown
GET /metrics/throughput  → last 30-min per-minute signal counts
GET /metrics/mttr        → MTTR averages per priority
GET /metrics/signals     → top components by signal count (last 24h)
"""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.observability import (
    get_full_observability_snapshot,
    get_throughput_history,
    get_mttr_stats,
    get_signal_breakdown,
)

logger = logging.getLogger("ims.api.observability")
router = APIRouter(prefix="/metrics", tags=["observability"])


@router.get("/full")
async def full_metrics(db: AsyncSession = Depends(get_db)):
    """
    Complete observability snapshot.
    Aggregates queue depth, signal throughput, work item counts,
    MTTR by priority, and top-10 components by signal volume.
    """
    return await get_full_observability_snapshot(db)


@router.get("/throughput")
async def throughput_history(minutes: int = 30):
    """Per-minute signal ingestion counts for the last N minutes (max 60)."""
    minutes = min(minutes, 60)
    history = await get_throughput_history(minutes)
    return {"history": history, "minutes": minutes}


@router.get("/mttr")
async def mttr_stats(db: AsyncSession = Depends(get_db)):
    """Mean Time To Repair grouped by priority (P0–P3)."""
    stats = await get_mttr_stats(db)
    return {"mttr_by_priority": stats}


@router.get("/signals")
async def signal_breakdown(hours: int = 24):
    """Top components by signal volume for the last N hours."""
    hours = min(hours, 168)  # cap at 1 week
    breakdown = await get_signal_breakdown(hours)
    return {"breakdown": breakdown, "hours": hours}
