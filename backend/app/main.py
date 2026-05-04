import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.db.session import init_db, close_db
from app.db.redis import get_redis, close_redis
from app.db.sqlite import init_sqlite
from app.api import api_router
from app.workers.signal_worker import start_workers, stop_workers
from app.services.metrics import get_throughput_snapshot
from app.services.ws_manager import ws_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("ims")
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("IMS Backend starting up...")
    await init_db()
    logger.info("PostgreSQL tables ready")
    await init_sqlite()
    logger.info("SQLite signal lake ready")
    redis = await get_redis()
    await redis.ping()
    logger.info("Redis connection established")
    await ws_manager.start()
    logger.info("WebSocket manager started (Redis pub/sub + heartbeat)")
    worker_tasks = await start_workers()
    logger.info("Signal worker pool started (%d workers)", settings.worker_count)
    metrics_task = asyncio.create_task(_metrics_logger())
    logger.info("Metrics logger started (every %ds)", settings.metrics_interval_seconds)
    logger.info("IMS Backend ready on port 8000")
    yield
    logger.info("IMS Backend shutting down...")
    metrics_task.cancel()
    try:
        await metrics_task
    except asyncio.CancelledError:
        pass
    await stop_workers(worker_tasks)
    await ws_manager.stop()
    await close_db()
    await close_redis()
    logger.info("IMS Backend shut down cleanly")


async def _metrics_logger():
    while True:
        await asyncio.sleep(settings.metrics_interval_seconds)
        try:
            snapshot = await get_throughput_snapshot()
            from app.services.signal_queue import queue_depth
            logger.info(
                "METRICS | signals_total=%s | signals/%ds=%s | open=%s | queue=%s | ws=%s",
                snapshot.get("signals_total", 0),
                settings.metrics_interval_seconds,
                snapshot.get("signals_per_window", 0),
                snapshot.get("work_items_open", 0),
                queue_depth(),
                ws_manager.connection_count,
            )
        except Exception as exc:
            logger.warning("Metrics logger error: %s", exc)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Mission-Critical Incident Management System",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000", "http://frontend:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    return app


app = create_app()
