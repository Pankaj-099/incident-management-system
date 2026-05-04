"""
Signal Queue — asyncio.Queue-based in-memory buffer.

Decouples HTTP handlers (producers) from DB writers (consumers).
The HTTP layer never blocks on DB I/O; if the queue is full, a 503 is
returned instead of crashing the process.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings

logger = logging.getLogger("ims.queue")


@dataclass
class QueuedSignal:
    signal_id: str
    component_id: str
    component_type: str
    severity: str
    message: str
    payload: dict[str, Any] | None
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ── Singleton queue ────────────────────────────────────────────────────────────
_signal_queue: asyncio.Queue[QueuedSignal] | None = None


def get_signal_queue() -> asyncio.Queue[QueuedSignal]:
    global _signal_queue
    if _signal_queue is None:
        _signal_queue = asyncio.Queue(maxsize=settings.queue_max_size)
    return _signal_queue


async def enqueue_signal(signal: QueuedSignal) -> bool:
    """
    Non-blocking enqueue. Returns False if queue is full (backpressure).
    Never raises; the caller decides how to respond to the producer.
    """
    queue = get_signal_queue()
    try:
        queue.put_nowait(signal)
        return True
    except asyncio.QueueFull:
        logger.warning(
            "⚠️  Queue full (%d/%d) — dropping signal %s for %s",
            queue.qsize(),
            settings.queue_max_size,
            signal.signal_id,
            signal.component_id,
        )
        return False


def queue_depth() -> int:
    q = get_signal_queue()
    return q.qsize()


def queue_capacity() -> int:
    return settings.queue_max_size
