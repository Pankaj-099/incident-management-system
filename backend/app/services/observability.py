"""
Observability Service — Phase 5

Provides:
  - Per-component signal rate (SQLite)
  - Work Item lifecycle stats (PostgreSQL)
  - MTTR averages per priority
  - Throughput history (Redis rolling buckets)
"""

import logging
import time
from datetime import datetime, timezone, timedelta

import aiosqlite
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from app.core.config import settings
from app.models.work_item import WorkItem, WorkItemStatus
from app.models.rca import RCA
from app.db.redis import get_redis

logger = logging.getLogger("ims.observability")

_THROUGHPUT_BUCKET_KEY = "obs:throughput:"  # prefix + epoch_minute
_BUCKET_TTL = 3600  # keep 1 hour of buckets


async def record_signal_throughput(count: int = 1) -> None:
    """Increment the current-minute throughput bucket in Redis."""
    try:
        redis = await get_redis()
        minute_key = f"{_THROUGHPUT_BUCKET_KEY}{int(time.time() // 60)}"
        await redis.incrby(minute_key, count)
        await redis.expire(minute_key, _BUCKET_TTL)
    except Exception as exc:
        logger.debug("Throughput record error: %s", exc)


async def get_throughput_history(minutes: int = 30) -> list[dict]:
    """Return per-minute signal counts for the last N minutes."""
    try:
        redis = await get_redis()
        now_minute = int(time.time() // 60)
        keys = [f"{_THROUGHPUT_BUCKET_KEY}{now_minute - i}" for i in range(minutes)]
        values = await redis.mget(*keys)
        result = []
        for i, val in enumerate(values):
            minute_ts = (now_minute - i) * 60
            result.append({
                "minute": datetime.fromtimestamp(minute_ts, tz=timezone.utc).isoformat(),
                "count": int(val or 0),
            })
        return list(reversed(result))
    except Exception as exc:
        logger.warning("Throughput history error: %s", exc)
        return []


async def get_signal_breakdown(hours: int = 24) -> list[dict]:
    """Top components by signal count in the last N hours, from SQLite."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        async with aiosqlite.connect(settings.sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT component_id, severity,
                       COUNT(*) as signal_count
                FROM raw_signals
                WHERE received_at >= ?
                GROUP BY component_id, severity
                ORDER BY signal_count DESC
                LIMIT 30
                """,
                (cutoff,),
            ) as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]
    except Exception as exc:
        logger.warning("Signal breakdown error: %s", exc)
        return []


async def get_mttr_stats(db: AsyncSession) -> dict:
    """Average MTTR grouped by priority, excluding nulls."""
    try:
        result = await db.execute(
            select(
                WorkItem.priority,
                func.avg(WorkItem.mttr_seconds).label("avg_mttr"),
                func.min(WorkItem.mttr_seconds).label("min_mttr"),
                func.max(WorkItem.mttr_seconds).label("max_mttr"),
                func.count().label("count"),
            )
            .where(WorkItem.mttr_seconds.isnot(None))
            .group_by(WorkItem.priority)
        )
        rows = result.all()
        return {
            row.priority: {
                "avg_seconds": round(row.avg_mttr or 0),
                "avg_minutes": round((row.avg_mttr or 0) / 60, 1),
                "min_seconds": row.min_mttr,
                "max_seconds": row.max_mttr,
                "sample_count": row.count,
            }
            for row in rows
        }
    except Exception as exc:
        logger.warning("MTTR stats error: %s", exc)
        return {}


async def get_full_observability_snapshot(db: AsyncSession) -> dict:
    """Aggregate all observability data into a single response."""
    from app.services.metrics import get_throughput_snapshot
    from app.services.signal_queue import queue_depth
    from app.services.ws_manager import ws_manager

    metrics = await get_throughput_snapshot()

    # Work item counts by status
    status_result = await db.execute(
        select(WorkItem.status, func.count().label("cnt")).group_by(WorkItem.status)
    )
    by_status = {r.status: r.cnt for r in status_result}

    # RCA count
    rca_count_result = await db.execute(select(func.count()).select_from(RCA))
    rca_count = rca_count_result.scalar_one_or_none() or 0

    # MTTR stats
    mttr_stats = await get_mttr_stats(db)

    # Signal breakdown (last 24h)
    signal_breakdown = await get_signal_breakdown(hours=24)

    # Throughput history (last 30 min)
    throughput_history = await get_throughput_history(minutes=30)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "queue": {
            "depth": queue_depth(),
            "capacity": settings.queue_max_size,
            "utilization_pct": round(queue_depth() / settings.queue_max_size * 100, 2),
        },
        "websocket": {
            "connected_clients": ws_manager.connection_count,
        },
        "signals": {
            "total_ingested": metrics.get("signals_total", 0),
            "last_window": metrics.get("signals_per_window", 0),
            "window_seconds": settings.metrics_interval_seconds,
        },
        "work_items": {
            "by_status": by_status,
            "open": by_status.get("OPEN", 0),
            "investigating": by_status.get("INVESTIGATING", 0),
            "resolved": by_status.get("RESOLVED", 0),
            "closed": by_status.get("CLOSED", 0),
            "total_rcas": rca_count,
        },
        "mttr": mttr_stats,
        "top_components_24h": signal_breakdown[:10],
        "throughput_history_30m": throughput_history,
    }
