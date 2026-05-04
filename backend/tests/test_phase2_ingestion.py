"""
Unit tests for Phase 2: Signal Queue & Ingestion Pipeline
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from app.services.signal_queue import (
    QueuedSignal,
    enqueue_signal,
    queue_depth,
    get_signal_queue,
)
from app.schemas.signal import IngestSignalRequest, SeverityLevel, ComponentType


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_signal(**kwargs) -> QueuedSignal:
    defaults = dict(
        signal_id="test-sig-001",
        component_id="CACHE_CLUSTER_01",
        component_type="CACHE",
        severity="HIGH",
        message="Connection timeout",
        payload={"latency_ms": 5000},
    )
    defaults.update(kwargs)
    return QueuedSignal(**defaults)


# ── Queue tests ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_enqueue_signal_accepted():
    """Signal should be accepted when queue has capacity."""
    import app.services.signal_queue as sq
    sq._signal_queue = asyncio.Queue(maxsize=10)

    signal = make_signal()
    result = await enqueue_signal(signal)

    assert result is True
    assert queue_depth() == 1
    sq._signal_queue = None  # reset


@pytest.mark.asyncio
async def test_enqueue_signal_rejected_when_full():
    """Signal should be rejected (not raise) when queue is full."""
    import app.services.signal_queue as sq
    sq._signal_queue = asyncio.Queue(maxsize=2)

    for i in range(2):
        await enqueue_signal(make_signal(signal_id=f"sig-{i}"))

    # Queue is now full — next enqueue should return False
    result = await enqueue_signal(make_signal(signal_id="overflow"))
    assert result is False
    sq._signal_queue = None  # reset


@pytest.mark.asyncio
async def test_queue_depth_increments():
    """queue_depth() should reflect number of items in the queue."""
    import app.services.signal_queue as sq
    sq._signal_queue = asyncio.Queue(maxsize=100)

    for i in range(5):
        await enqueue_signal(make_signal(signal_id=f"sig-{i}"))

    assert queue_depth() == 5
    sq._signal_queue = None  # reset


# ── Schema validation tests ────────────────────────────────────────────────────

def test_ingest_request_component_id_uppercased():
    """component_id should be uppercased and stripped."""
    req = IngestSignalRequest(
        component_id="  cache_cluster_01  ",
        message="test error",
    )
    assert req.component_id == "CACHE_CLUSTER_01"


def test_ingest_request_defaults():
    """Default values should be set correctly."""
    req = IngestSignalRequest(component_id="API_GW_01", message="timeout")
    assert req.severity == SeverityLevel.MEDIUM
    assert req.component_type == ComponentType.API
    assert req.signal_id is not None


def test_ingest_request_empty_message_invalid():
    """Empty message should fail validation."""
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        IngestSignalRequest(component_id="API_GW_01", message="")


def test_ingest_request_empty_component_id_invalid():
    """Empty component_id should fail validation."""
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        IngestSignalRequest(component_id="", message="some error")


# ── SQLite sink tests ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_persist_signal_success():
    """Signal should be written to SQLite without error."""
    from app.services.sqlite_sink import persist_signal
    from app.db.sqlite import init_sqlite
    import app.core.config as cfg

    # Use an in-memory SQLite for the test
    original = cfg.settings.sqlite_path
    cfg.settings.sqlite_path = ":memory:"

    try:
        await init_sqlite()
        signal = make_signal()
        result = await persist_signal(signal, work_item_id="wi-001")
        assert result is True
    finally:
        cfg.settings.sqlite_path = original


@pytest.mark.asyncio
async def test_persist_signal_retry_on_failure():
    """Persist should retry on transient failure and eventually succeed."""
    from app.services import sqlite_sink

    call_count = 0
    original_write = sqlite_sink._write_with_retry

    async def failing_then_success(signal, work_item_id=None):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise Exception("transient failure")
        return True

    sqlite_sink._write_with_retry = failing_then_success
    try:
        result = await sqlite_sink.persist_signal(make_signal())
        # Since we replaced _write_with_retry, first call triggers it
        assert result is True
    finally:
        sqlite_sink._write_with_retry = original_write
