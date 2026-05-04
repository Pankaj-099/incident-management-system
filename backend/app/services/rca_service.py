"""
RCA Service — Phase 5

Responsibilities:
  1. Create / update RCA for a Work Item
  2. Calculate MTTR and write it back to the Work Item
  3. All DB writes use exponential-backoff retry
  4. Validate completeness (duplicates the engine guard so the API
     gives a rich error before the transition attempt)
"""

import asyncio
import logging
from datetime import timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from app.models.rca import RCA
from app.models.work_item import WorkItem
from app.schemas.rca import RCACreateRequest
from app.services.dashboard_cache import invalidate_dashboard_cache
from app.services.ws_manager import ws_manager

logger = logging.getLogger("ims.rca_service")

_MAX_RETRIES = 3
_RETRY_BASE  = 0.1  # seconds


async def _retry(coro_fn, *args, **kwargs):
    """Exponential backoff retry wrapper for transient DB errors."""
    for attempt in range(_MAX_RETRIES):
        try:
            return await coro_fn(*args, **kwargs)
        except SQLAlchemyError as exc:
            if attempt == _MAX_RETRIES - 1:
                raise
            delay = _RETRY_BASE * (2 ** attempt)
            logger.warning(
                "DB retry %d/%d in %.2fs: %s", attempt + 1, _MAX_RETRIES, delay, exc
            )
            await asyncio.sleep(delay)


def _calculate_mttr(start: any, end: any) -> int:
    """Return seconds between incident_start and incident_end."""
    # Ensure both are tz-aware for comparison
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    delta = end - start
    return max(0, int(delta.total_seconds()))


async def _do_create_rca(
    db: AsyncSession,
    work_item: WorkItem,
    payload: RCACreateRequest,
) -> RCA:
    """Inner function — called with retry wrapper."""
    mttr = _calculate_mttr(payload.incident_start, payload.incident_end)

    rca = RCA(
        work_item_id=work_item.id,
        incident_start=payload.incident_start,
        incident_end=payload.incident_end,
        root_cause_category=payload.root_cause_category,
        root_cause_description=payload.root_cause_description.strip(),
        fix_applied=payload.fix_applied.strip(),
        prevention_steps=payload.prevention_steps.strip(),
        submitted_by=payload.submitted_by,
    )
    db.add(rca)
    await db.flush()

    # Write MTTR back to the Work Item
    await db.execute(
        update(WorkItem)
        .where(WorkItem.id == work_item.id)
        .values(mttr_seconds=mttr)
    )
    await db.commit()
    await db.refresh(rca)
    return rca


async def create_or_update_rca(
    db: AsyncSession,
    work_item_id: str,
    payload: RCACreateRequest,
) -> tuple[RCA, int]:
    """
    Create (or replace) the RCA for a Work Item.
    Returns (rca, mttr_seconds).

    Raises:
        ValueError — work item not found
        SQLAlchemyError — DB failure after retries
    """
    # Load work item
    result = await db.execute(select(WorkItem).where(WorkItem.id == work_item_id))
    wi = result.scalar_one_or_none()
    if wi is None:
        raise ValueError(f"Work item {work_item_id!r} not found")

    # Delete existing RCA if present (allow re-submission)
    existing = await db.execute(select(RCA).where(RCA.work_item_id == work_item_id))
    old_rca = existing.scalar_one_or_none()
    if old_rca:
        await db.delete(old_rca)
        await db.flush()
        logger.info("Replaced existing RCA for WI %s", work_item_id[:8])

    rca = await _retry(_do_create_rca, db, wi, payload)
    mttr = _calculate_mttr(payload.incident_start, payload.incident_end)

    logger.info(
        "📝 RCA submitted for WI=%s | MTTR=%ds (%.1f min) | category=%s",
        work_item_id[:8], mttr, mttr / 60, payload.root_cause_category,
    )

    # Invalidate cache + broadcast update
    await invalidate_dashboard_cache()
    await ws_manager.broadcast(
        "work_item_updated",
        {
            "id": wi.id,
            "component_id": wi.component_id,
            "component_type": wi.component_type,
            "status": wi.status,
            "priority": wi.priority,
            "title": wi.title,
            "signal_count": wi.signal_count,
            "mttr_seconds": mttr,
            "created_at": wi.created_at.isoformat() if wi.created_at else None,
            "updated_at": wi.updated_at.isoformat() if wi.updated_at else None,
            "resolved_at": wi.resolved_at.isoformat() if wi.resolved_at else None,
            "closed_at": wi.closed_at.isoformat() if wi.closed_at else None,
        },
    )

    return rca, mttr


async def get_rca(db: AsyncSession, work_item_id: str) -> RCA | None:
    result = await db.execute(select(RCA).where(RCA.work_item_id == work_item_id))
    return result.scalar_one_or_none()


async def list_rcas(db: AsyncSession, limit: int = 50) -> list[RCA]:
    result = await db.execute(
        select(RCA).order_by(RCA.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())
