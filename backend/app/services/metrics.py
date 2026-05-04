"""
Metrics service — lightweight counters stored in Redis.
Throughput is logged to console every N seconds by the metrics logger in main.py.
"""

import logging
import time
from app.db.redis import get_redis

logger = logging.getLogger("ims.metrics")

# Redis keys
_KEY_SIGNALS_TOTAL = "metrics:signals_total"
_KEY_SIGNALS_WINDOW = "metrics:signals_window"  # rolling 5s window count
_KEY_WORK_ITEMS_OPEN = "metrics:work_items_open"
_KEY_QUEUE_DEPTH = "metrics:queue_depth"
_KEY_WINDOW_TS = "metrics:window_ts"


async def increment_signal_count(n: int = 1) -> None:
    try:
        redis = await get_redis()
        pipe = redis.pipeline()
        pipe.incrby(_KEY_SIGNALS_TOTAL, n)
        pipe.incrby(_KEY_SIGNALS_WINDOW, n)
        await pipe.execute()
    except Exception as exc:
        logger.debug("Metrics increment error: %s", exc)


async def set_queue_depth(depth: int) -> None:
    try:
        redis = await get_redis()
        await redis.set(_KEY_QUEUE_DEPTH, depth)
    except Exception as exc:
        logger.debug("Metrics queue depth error: %s", exc)


async def increment_open_work_items(n: int = 1) -> None:
    try:
        redis = await get_redis()
        await redis.incrby(_KEY_WORK_ITEMS_OPEN, n)
    except Exception as exc:
        logger.debug("Metrics work items error: %s", exc)


async def decrement_open_work_items(n: int = 1) -> None:
    try:
        redis = await get_redis()
        val = await redis.get(_KEY_WORK_ITEMS_OPEN)
        current = int(val or 0)
        new_val = max(0, current - n)
        await redis.set(_KEY_WORK_ITEMS_OPEN, new_val)
    except Exception as exc:
        logger.debug("Metrics decrement error: %s", exc)


async def get_throughput_snapshot() -> dict:
    """Returns current metrics snapshot for the /metrics endpoint."""
    try:
        redis = await get_redis()
        signals_total, signals_window, work_items_open, queue_depth = await redis.mget(
            _KEY_SIGNALS_TOTAL,
            _KEY_SIGNALS_WINDOW,
            _KEY_WORK_ITEMS_OPEN,
            _KEY_QUEUE_DEPTH,
        )
        # Reset rolling window
        await redis.set(_KEY_SIGNALS_WINDOW, 0)
        return {
            "signals_total": int(signals_total or 0),
            "signals_per_window": int(signals_window or 0),
            "work_items_open": int(work_items_open or 0),
            "queue_depth": int(queue_depth or 0),
            "timestamp": time.time(),
        }
    except Exception as exc:
        logger.warning("Could not fetch metrics snapshot: %s", exc)
        return {}
