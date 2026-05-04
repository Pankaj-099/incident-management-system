"""
Unit tests — Phase 5: RCA Validation, MTTR, Retry Logic
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pydantic


# ── RCA Schema validation ──────────────────────────────────────────────────────

def make_valid_rca_payload(**overrides):
    base = {
        "incident_start": datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc),
        "incident_end":   datetime(2024, 6, 1, 12, 30, tzinfo=timezone.utc),
        "root_cause_category": "SOFTWARE_BUG",
        "root_cause_description": "A race condition in the connection pool caused cascading failures under load.",
        "fix_applied": "Applied a patch to serialize pool access and deployed to production.",
        "prevention_steps": "Add load testing to CI pipeline and implement circuit breakers.",
        "submitted_by": "jane.doe",
    }
    base.update(overrides)
    return base


def test_valid_rca_payload_passes():
    from app.schemas.rca import RCACreateRequest
    req = RCACreateRequest(**make_valid_rca_payload())
    assert req.root_cause_category.value == "SOFTWARE_BUG"


def test_rca_rejects_end_before_start():
    from app.schemas.rca import RCACreateRequest
    with pytest.raises(pydantic.ValidationError) as exc_info:
        RCACreateRequest(**make_valid_rca_payload(
            incident_start=datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc),
            incident_end=datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc),
        ))
    assert "incident_end" in str(exc_info.value)


def test_rca_rejects_equal_start_end():
    from app.schemas.rca import RCACreateRequest
    t = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
    with pytest.raises(pydantic.ValidationError):
        RCACreateRequest(**make_valid_rca_payload(incident_start=t, incident_end=t))


def test_rca_rejects_short_root_cause_description():
    from app.schemas.rca import RCACreateRequest
    with pytest.raises(pydantic.ValidationError):
        RCACreateRequest(**make_valid_rca_payload(root_cause_description="Too short"))


def test_rca_rejects_short_fix_applied():
    from app.schemas.rca import RCACreateRequest
    with pytest.raises(pydantic.ValidationError):
        RCACreateRequest(**make_valid_rca_payload(fix_applied="short"))


def test_rca_rejects_short_prevention_steps():
    from app.schemas.rca import RCACreateRequest
    with pytest.raises(pydantic.ValidationError):
        RCACreateRequest(**make_valid_rca_payload(prevention_steps="nope"))


def test_rca_allows_all_root_cause_categories():
    from app.schemas.rca import RCACreateRequest
    from app.models.rca import RootCauseCategory
    for cat in RootCauseCategory:
        req = RCACreateRequest(**make_valid_rca_payload(root_cause_category=cat.value))
        assert req.root_cause_category == cat


# ── MTTR calculation ───────────────────────────────────────────────────────────

def test_mttr_basic_calculation():
    from app.services.rca_service import _calculate_mttr
    start = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
    end   = datetime(2024, 6, 1, 12, 30, tzinfo=timezone.utc)
    mttr  = _calculate_mttr(start, end)
    assert mttr == 9000  # 2.5 hours = 9000 seconds


def test_mttr_one_minute():
    from app.services.rca_service import _calculate_mttr
    start = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
    end   = datetime(2024, 6, 1, 10, 1, 0, tzinfo=timezone.utc)
    assert _calculate_mttr(start, end) == 60


def test_mttr_24_hours():
    from app.services.rca_service import _calculate_mttr
    start = datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc)
    end   = datetime(2024, 6, 2, 0, 0, tzinfo=timezone.utc)
    assert _calculate_mttr(start, end) == 86400


def test_mttr_never_negative():
    from app.services.rca_service import _calculate_mttr
    # Even if start > end (shouldn't happen, schema blocks it, but defensive)
    start = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
    end   = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
    assert _calculate_mttr(start, end) == 0


def test_mttr_naive_datetimes_treated_as_utc():
    from app.services.rca_service import _calculate_mttr
    start = datetime(2024, 6, 1, 10, 0, 0)  # naive
    end   = datetime(2024, 6, 1, 11, 0, 0)  # naive
    assert _calculate_mttr(start, end) == 3600


# ── Retry logic ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retry_succeeds_on_second_attempt():
    from app.services.rca_service import _retry
    from sqlalchemy.exc import SQLAlchemyError

    call_count = 0

    async def flaky_fn():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise SQLAlchemyError("transient error")
        return "ok"

    with patch("app.services.rca_service._RETRY_BASE", 0.001):
        result = await _retry(flaky_fn)

    assert result == "ok"
    assert call_count == 2


@pytest.mark.asyncio
async def test_retry_raises_after_max_attempts():
    from app.services.rca_service import _retry
    from sqlalchemy.exc import SQLAlchemyError

    async def always_fails():
        raise SQLAlchemyError("persistent failure")

    with patch("app.services.rca_service._RETRY_BASE", 0.001):
        with pytest.raises(SQLAlchemyError):
            await _retry(always_fails)


@pytest.mark.asyncio
async def test_retry_does_not_retry_on_success():
    from app.services.rca_service import _retry

    call_count = 0

    async def succeeds():
        nonlocal call_count
        call_count += 1
        return "success"

    result = await _retry(succeeds)
    assert result == "success"
    assert call_count == 1


# ── Observability ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_throughput_history_returns_list():
    from app.services.observability import get_throughput_history

    mock_redis = AsyncMock()
    mock_redis.mget = AsyncMock(return_value=[b"5", b"10", b"0", None, b"3"])

    with patch("app.services.observability.get_redis", AsyncMock(return_value=mock_redis)):
        history = await get_throughput_history(minutes=5)

    assert isinstance(history, list)
    assert len(history) == 5
    counts = [h["count"] for h in history]
    assert 5 in counts
    assert 10 in counts


@pytest.mark.asyncio
async def test_signal_breakdown_returns_list_on_db_error():
    from app.services.observability import get_signal_breakdown

    # If SQLite is not available, should return empty list gracefully
    with patch("app.services.observability.aiosqlite.connect", side_effect=Exception("no db")):
        result = await get_signal_breakdown(hours=24)

    assert result == []
