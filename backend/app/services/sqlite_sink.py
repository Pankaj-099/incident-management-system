"""
Raw signal persistence into SQLite (the Data Lake / audit log).
Uses exponential backoff retry for resilience.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

import aiosqlite

from app.core.config import settings
from app.services.signal_queue import QueuedSignal

logger = logging.getLogger("ims.sqlite_sink")

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 0.1  # seconds


async def _write_with_retry(signal: QueuedSignal, work_item_id: str | None = None) -> bool:
    """Persist a signal to SQLite with exponential backoff retry."""
    for attempt in range(_MAX_RETRIES):
        try:
            async with aiosqlite.connect(settings.sqlite_path) as db:
                await db.execute(
                    """
                    INSERT INTO raw_signals
                        (signal_id, component_id, severity, message, payload, work_item_id, received_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        signal.signal_id,
                        signal.component_id,
                        signal.severity,
                        signal.message,
                        json.dumps(signal.payload) if signal.payload else None,
                        work_item_id,
                        signal.received_at.isoformat(),
                    ),
                )
                await db.commit()
            return True
        except Exception as exc:
            delay = _RETRY_BASE_DELAY * (2**attempt)
            logger.warning(
                "SQLite write failed (attempt %d/%d): %s — retrying in %.2fs",
                attempt + 1,
                _MAX_RETRIES,
                exc,
                delay,
            )
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(delay)

    logger.error("SQLite write permanently failed for signal %s", signal.signal_id)
    return False


async def persist_signal(signal: QueuedSignal, work_item_id: str | None = None) -> bool:
    return await _write_with_retry(signal, work_item_id)


async def get_signals_for_work_item(work_item_id: str) -> list[dict]:
    """Fetch all raw signals linked to a work item (for the UI detail view)."""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT signal_id, component_id, severity, message, payload, received_at
            FROM raw_signals
            WHERE work_item_id = ?
            ORDER BY received_at DESC
            LIMIT 500
            """,
            (work_item_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_recent_signals(limit: int = 100) -> list[dict]:
    """Fetch the most recent raw signals (for the live feed)."""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT signal_id, component_id, severity, message, payload, work_item_id, received_at
            FROM raw_signals
            ORDER BY received_at DESC
            LIMIT ?
            """,
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
