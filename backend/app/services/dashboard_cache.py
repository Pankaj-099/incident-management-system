"""
Dashboard Cache — Redis hot-path cache for work item list.
Avoids hitting PostgreSQL on every UI refresh.
TTL: 10 seconds (invalidated immediately on any WI mutation).
"""

import json
import logging
from app.db.redis import get_redis

logger = logging.getLogger("ims.cache")

_DASHBOARD_KEY  = "cache:dashboard:work_items"
_STATS_KEY      = "cache:dashboard:stats"
_CACHE_TTL      = 10  # seconds


async def get_cached_work_items() -> list[dict] | None:
    try:
        redis = await get_redis()
        val = await redis.get(_DASHBOARD_KEY)
        if val:
            return json.loads(val)
    except Exception as exc:
        logger.debug("Cache GET error: %s", exc)
    return None


async def set_cached_work_items(items: list[dict]) -> None:
    try:
        redis = await get_redis()
        await redis.set(_DASHBOARD_KEY, json.dumps(items, default=str), ex=_CACHE_TTL)
    except Exception as exc:
        logger.debug("Cache SET error: %s", exc)


async def get_cached_stats() -> dict | None:
    try:
        redis = await get_redis()
        val = await redis.get(_STATS_KEY)
        if val:
            return json.loads(val)
    except Exception as exc:
        logger.debug("Cache stats GET error: %s", exc)
    return None


async def set_cached_stats(stats: dict) -> None:
    try:
        redis = await get_redis()
        await redis.set(_STATS_KEY, json.dumps(stats, default=str), ex=_CACHE_TTL)
    except Exception as exc:
        logger.debug("Cache stats SET error: %s", exc)


async def invalidate_dashboard_cache() -> None:
    """Call this whenever a Work Item is created or mutated."""
    try:
        redis = await get_redis()
        await redis.delete(_DASHBOARD_KEY, _STATS_KEY)
    except Exception as exc:
        logger.debug("Cache invalidation error: %s", exc)
