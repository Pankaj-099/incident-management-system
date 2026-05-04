"""
Work Item Service — PostgreSQL CRUD with retry logic.
All state transitions are validated here (Phase 4 will add full State pattern).
"""

import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, desc
from sqlalchemy.exc import SQLAlchemyError

from app.models.work_item import WorkItem, WorkItemStatus
from app.schemas.work_item import WorkItemOut

logger = logging.getLogger("ims.work_item_service")

_MAX_RETRIES = 3
_RETRY_BASE  = 0.1


async def _with_retry(coro_fn, *args, **kwargs):
    """Retry a coroutine on transient DB errors with exponential backoff."""
    for attempt in range(_MAX_RETRIES):
        try:
            return await coro_fn(*args, **kwargs)
        except SQLAlchemyError as exc:
            if attempt == _MAX_RETRIES - 1:
                raise
            delay = _RETRY_BASE * (2 ** attempt)
            logger.warning("DB retry %d/%d in %.2fs: %s", attempt + 1, _MAX_RETRIES, delay, exc)
            await asyncio.sleep(delay)


async def get_work_item(db: AsyncSession, work_item_id: str) -> WorkItem | None:
    result = await db.execute(
        select(WorkItem).where(WorkItem.id == work_item_id)
    )
    return result.scalar_one_or_none()


async def list_work_items(
    db: AsyncSession,
    status: str | None = None,
    priority: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[WorkItem], int]:
    """Return (items, total_count) sorted by priority then created_at desc."""

    # Priority sort order: P0 first
    priority_order = {
        "P0": 0, "P1": 1, "P2": 2, "P3": 3,
    }

    q = select(WorkItem)
    if status:
        q = q.where(WorkItem.status == status)
    if priority:
        q = q.where(WorkItem.priority == priority)

    # Count
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    # Fetch with ordering
    q = q.order_by(WorkItem.priority.asc(), desc(WorkItem.created_at))
    q = q.limit(limit).offset(offset)
    result = await db.execute(q)
    items = list(result.scalars().all())
    return items, total


async def update_work_item_status(
    db: AsyncSession,
    work_item_id: str,
    new_status: str,
) -> WorkItem | None:
    """Basic status update — full State machine validation added in Phase 4."""
    async def _do_update():
        wi = await get_work_item(db, work_item_id)
        if not wi:
            return None

        extra: dict = {"updated_at": datetime.now(timezone.utc)}
        if new_status == WorkItemStatus.RESOLVED:
            extra["resolved_at"] = datetime.now(timezone.utc)
        elif new_status == WorkItemStatus.CLOSED:
            extra["closed_at"] = datetime.now(timezone.utc)

        await db.execute(
            update(WorkItem)
            .where(WorkItem.id == work_item_id)
            .values(status=new_status, **extra)
        )
        await db.commit()
        await db.refresh(wi)
        return wi

    return await _with_retry(_do_update)


async def get_stats(db: AsyncSession) -> dict:
    """Dashboard summary stats."""
    rows = await db.execute(
        select(WorkItem.status, func.count().label("cnt"))
        .group_by(WorkItem.status)
    )
    by_status = {r.status: r.cnt for r in rows}

    p_rows = await db.execute(
        select(WorkItem.priority, func.count().label("cnt"))
        .where(WorkItem.status != WorkItemStatus.CLOSED)
        .group_by(WorkItem.priority)
    )
    by_priority = {r.priority: r.cnt for r in p_rows}

    return {
        "by_status": by_status,
        "by_priority": by_priority,
        "total_open": by_status.get(WorkItemStatus.OPEN, 0),
        "total_investigating": by_status.get(WorkItemStatus.INVESTIGATING, 0),
        "total_resolved": by_status.get(WorkItemStatus.RESOLVED, 0),
        "total_closed": by_status.get(WorkItemStatus.CLOSED, 0),
    }
