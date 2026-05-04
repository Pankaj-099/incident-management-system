"""
Debounce Engine — Phase 3

Key rule: if 100 signals arrive for the same component_id within 10 seconds,
only ONE Work Item is created. All 100 signals are linked to it in SQLite.

Redis keys:
  debounce:{component_id}          → work_item_id (TTL = 10s)
  debounce:lock:{component_id}     → "1"          (TTL = 30s, creation lock)

Flow:
  1. Signal arrives with component_id
  2. GET debounce:{component_id} from Redis
     a. EXISTS  → return existing work_item_id (debounced, no new WI)
     b. MISSING → acquire creation lock, create Work Item in PG,
                  SET debounce key with TTL, release lock
  3. Link signal to work_item_id in SQLite
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.redis import get_redis
from app.models.work_item import WorkItem, WorkItemStatus, Priority, ComponentType
from app.services.ws_manager import ws_manager
from app.services.metrics import increment_open_work_items

logger = logging.getLogger("ims.debounce")

# Priority map: component type → priority
_PRIORITY_MAP: dict[str, str] = {
    "RDBMS":    Priority.P0,
    "MCP_HOST": Priority.P0,
    "API":      Priority.P1,
    "QUEUE":    Priority.P1,
    "NOSQL":    Priority.P2,
    "CACHE":    Priority.P2,
}

_DEBOUNCE_KEY_PREFIX = "debounce:"
_LOCK_KEY_PREFIX     = "debounce:lock:"
_LOCK_TTL_S          = 30   # max seconds to hold creation lock
_SIGNAL_COUNT_PREFIX = "debounce:count:"


def _debounce_key(component_id: str) -> str:
    return f"{_DEBOUNCE_KEY_PREFIX}{component_id}"


def _lock_key(component_id: str) -> str:
    return f"{_LOCK_KEY_PREFIX}{component_id}"


def _count_key(component_id: str) -> str:
    return f"{_SIGNAL_COUNT_PREFIX}{component_id}"


async def _create_work_item(
    component_id: str,
    component_type: str,
    severity: str,
    message: str,
    db: AsyncSession,
) -> WorkItem:
    """Create a new Work Item in PostgreSQL (transactional)."""
    priority = _PRIORITY_MAP.get(component_type, Priority.P2)

    wi = WorkItem(
        id=str(uuid.uuid4()),
        component_id=component_id,
        component_type=component_type,
        status=WorkItemStatus.OPEN,
        priority=priority,
        title=f"[{priority}] {component_id}: {message[:80]}",
        description=f"Auto-created from signal. Component: {component_id} ({component_type}). "
                    f"First signal severity: {severity}.",
        signal_count=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(wi)
    await db.flush()   # get the ID without full commit
    await db.commit()  # transactional commit
    await db.refresh(wi)

    logger.info(
        "📋 Work Item created: %s [%s] for %s",
        wi.id[:8],
        wi.priority,
        wi.component_id,
    )
    return wi


async def _increment_signal_count(work_item_id: str, db: AsyncSession) -> int:
    """Increment signal_count on the work item and return the new count."""
    from sqlalchemy import update, select
    await db.execute(
        update(WorkItem)
        .where(WorkItem.id == work_item_id)
        .values(
            signal_count=WorkItem.signal_count + 1,
            updated_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()
    result = await db.execute(
        select(WorkItem.signal_count).where(WorkItem.id == work_item_id)
    )
    return result.scalar_one_or_none() or 1


async def process_signal_debounce(
    component_id: str,
    component_type: str,
    severity: str,
    message: str,
    signal_id: str,
    db: AsyncSession,
) -> tuple[str, bool]:
    """
    Core debounce logic.

    Returns:
        (work_item_id, is_new)
        is_new=True  → a fresh Work Item was created
        is_new=False → signal was folded into an existing Work Item
    """
    redis = await get_redis()
    dkey  = _debounce_key(component_id)
    lkey  = _lock_key(component_id)

    # ── Fast path: debounce window active ─────────────────────────────────────
    existing_wi_id = await redis.get(dkey)
    if existing_wi_id:
        # Fold this signal into the existing Work Item
        await _increment_signal_count(existing_wi_id, db)
        logger.debug(
            "🔁 Debounced signal %s → Work Item %s", signal_id[:8], existing_wi_id[:8]
        )
        return existing_wi_id, False

    # ── Slow path: acquire creation lock (prevents race between workers) ──────
    acquired = await redis.set(lkey, "1", nx=True, ex=_LOCK_TTL_S)

    if not acquired:
        # Another worker is creating the WI right now — wait briefly and retry
        for _ in range(20):
            await asyncio.sleep(0.05)
            existing_wi_id = await redis.get(dkey)
            if existing_wi_id:
                await _increment_signal_count(existing_wi_id, db)
                return existing_wi_id, False
        # Fallback: give up waiting, create independently (rare edge case)
        logger.warning("Lock wait timed out for %s — creating fallback WI", component_id)

    try:
        # Double-check: another worker may have created it while we waited
        existing_wi_id = await redis.get(dkey)
        if existing_wi_id:
            await _increment_signal_count(existing_wi_id, db)
            return existing_wi_id, False

        # Create the Work Item in PostgreSQL
        wi = await _create_work_item(component_id, component_type, severity, message, db)

        # Set debounce window key (expires after N seconds)
        await redis.set(dkey, wi.id, ex=settings.debounce_window_seconds)

        # Track open work item count for metrics
        await increment_open_work_items()

        # Broadcast new Work Item to dashboard via WebSocket
        await ws_manager.broadcast(
            "work_item_created",
            {
                "id": wi.id,
                "component_id": wi.component_id,
                "component_type": wi.component_type,
                "status": wi.status,
                "priority": wi.priority,
                "title": wi.title,
                "signal_count": wi.signal_count,
                "created_at": wi.created_at.isoformat(),
                "updated_at": wi.updated_at.isoformat(),
            },
        )

        return wi.id, True

    finally:
        # Always release the lock
        if acquired:
            await redis.delete(lkey)
