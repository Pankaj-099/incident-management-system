from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from redis.asyncio import Redis
from app.db.session import get_db
from app.db.redis import get_redis
from app.core.config import settings
import aiosqlite
import time

router = APIRouter(tags=["health"])

_start_time = time.time()


@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """
    Comprehensive health check for all infrastructure components.
    Returns status of PostgreSQL, Redis, and SQLite.
    """
    results = {
        "status": "healthy",
        "version": settings.app_version,
        "env": settings.env,
        "uptime_seconds": round(time.time() - _start_time, 2),
        "components": {},
    }

    # ── PostgreSQL ─────────────────────────────────────────────────────────────
    try:
        await db.execute(text("SELECT 1"))
        results["components"]["postgres"] = {"status": "healthy"}
    except Exception as exc:
        results["components"]["postgres"] = {"status": "unhealthy", "error": str(exc)}
        results["status"] = "degraded"

    # ── Redis ──────────────────────────────────────────────────────────────────
    try:
        pong = await redis.ping()
        results["components"]["redis"] = {"status": "healthy" if pong else "unhealthy"}
    except Exception as exc:
        results["components"]["redis"] = {"status": "unhealthy", "error": str(exc)}
        results["status"] = "degraded"

    # ── SQLite ─────────────────────────────────────────────────────────────────
    try:
        async with aiosqlite.connect(settings.sqlite_path) as sqlite_db:
            await sqlite_db.execute("SELECT 1")
        results["components"]["sqlite"] = {"status": "healthy"}
    except Exception as exc:
        results["components"]["sqlite"] = {"status": "unhealthy", "error": str(exc)}
        results["status"] = "degraded"

    return results


@router.get("/health/ping")
async def ping():
    """Lightweight liveness probe."""
    return {"ping": "pong"}
