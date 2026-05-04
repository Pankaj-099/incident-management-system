"""
Signal Worker — Phase 3 update.

Now wires debounce engine after SQLite persistence:
  1. Persist raw signal → SQLite (audit lake)
  2. Run debounce → get/create Work Item in PostgreSQL
  3. Update SQLite row with work_item_id (link)
  4. Broadcast via WebSocket
  5. Update metrics
"""

import asyncio
import logging

from app.core.config import settings
from app.services.signal_queue import get_signal_queue, QueuedSignal, queue_depth
from app.services.sqlite_sink import persist_signal
from app.services.metrics import increment_signal_count, set_queue_depth
from app.services.ws_manager import ws_manager
from app.services.debounce import process_signal_debounce
from app.services.dashboard_cache import invalidate_dashboard_cache
from app.db.session import AsyncSessionLocal

logger = logging.getLogger("ims.worker")


async def _process_signal(signal: QueuedSignal) -> None:
    """Full signal processing pipeline."""

    # 1. Persist raw signal to SQLite (no work_item_id yet)
    await persist_signal(signal, work_item_id=None)

    # 2. Debounce: get or create Work Item in PostgreSQL
    work_item_id: str | None = None
    is_new_wi = False

    try:
        async with AsyncSessionLocal() as db:
            work_item_id, is_new_wi = await process_signal_debounce(
                component_id=signal.component_id,
                component_type=signal.component_type,
                severity=signal.severity,
                message=signal.message,
                signal_id=signal.signal_id,
                db=db,
            )
    except Exception as exc:
        logger.error("Debounce/WI creation failed for %s: %s", signal.signal_id, exc, exc_info=True)

    # 3. Update SQLite row to link signal to work item
    if work_item_id:
        try:
            import aiosqlite
            async with aiosqlite.connect(settings.sqlite_path) as sdb:
                await sdb.execute(
                    "UPDATE raw_signals SET work_item_id = ? WHERE signal_id = ?",
                    (work_item_id, signal.signal_id),
                )
                await sdb.commit()
        except Exception as exc:
            logger.warning("SQLite link update failed: %s", exc)

    # 4. Invalidate dashboard cache on new WI
    if is_new_wi:
        await invalidate_dashboard_cache()

    # 5. Broadcast raw signal to WebSocket clients
    await ws_manager.broadcast(
        "signal",
        {
            "signal_id": signal.signal_id,
            "component_id": signal.component_id,
            "component_type": signal.component_type,
            "severity": signal.severity,
            "message": signal.message,
            "work_item_id": work_item_id,
            "received_at": signal.received_at.isoformat(),
        },
    )

    # 6. Update throughput counters
    await increment_signal_count()
    await set_queue_depth(queue_depth())

    logger.debug(
        "Signal %s -> WI %s (new=%s)",
        signal.signal_id[:8],
        work_item_id[:8] if work_item_id else "none",
        is_new_wi,
    )


async def signal_worker(worker_id: int) -> None:
    queue = get_signal_queue()
    logger.info("Signal worker %d started", worker_id)

    while True:
        try:
            signal: QueuedSignal = await queue.get()
            try:
                await _process_signal(signal)
            except Exception as exc:
                logger.error("Worker %d failed on %s: %s", worker_id, signal.signal_id, exc, exc_info=True)
            finally:
                queue.task_done()
        except asyncio.CancelledError:
            logger.info("Worker %d shutting down", worker_id)
            break
        except Exception as exc:
            logger.error("Worker %d unexpected error: %s", worker_id, exc)
            await asyncio.sleep(0.1)


async def start_workers() -> list[asyncio.Task]:
    tasks = [
        asyncio.create_task(signal_worker(i), name=f"signal-worker-{i}")
        for i in range(settings.worker_count)
    ]
    logger.info("Started %d signal workers", settings.worker_count)
    return tasks


async def stop_workers(tasks: list[asyncio.Task]) -> None:
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("All signal workers stopped")
