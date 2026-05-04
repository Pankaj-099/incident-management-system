"""
Unit tests — Phase 4: State Machine & Alert Strategy
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone


# ── State Machine tests ────────────────────────────────────────────────────────

def test_open_can_transition_to_investigating():
    from app.services.state_machine import get_state
    state = get_state("OPEN")
    assert state.can_transition_to("INVESTIGATING") is True


def test_open_cannot_transition_to_closed():
    from app.services.state_machine import get_state
    state = get_state("OPEN")
    assert state.can_transition_to("CLOSED") is False


def test_investigating_can_transition_to_resolved():
    from app.services.state_machine import get_state
    state = get_state("INVESTIGATING")
    assert state.can_transition_to("RESOLVED") is True


def test_investigating_can_revert_to_open():
    from app.services.state_machine import get_state
    state = get_state("INVESTIGATING")
    assert state.can_transition_to("OPEN") is True


def test_resolved_can_transition_to_closed():
    from app.services.state_machine import get_state
    state = get_state("RESOLVED")
    assert state.can_transition_to("CLOSED") is True


def test_resolved_can_reopen_investigation():
    from app.services.state_machine import get_state
    state = get_state("RESOLVED")
    assert state.can_transition_to("INVESTIGATING") is True


def test_closed_has_no_allowed_transitions():
    from app.services.state_machine import get_state
    state = get_state("CLOSED")
    assert state.allowed_transitions == set()


def test_closed_raises_on_any_transition():
    from app.services.state_machine import get_state, InvalidTransitionError
    state = get_state("CLOSED")
    wi = MagicMock()
    with pytest.raises(InvalidTransitionError) as exc_info:
        state.validate_transition("OPEN", wi)
    assert "terminal" in str(exc_info.value).lower()


def test_invalid_transition_raises_with_details():
    from app.services.state_machine import get_state, InvalidTransitionError
    state = get_state("OPEN")
    wi = MagicMock()
    with pytest.raises(InvalidTransitionError) as exc_info:
        state.validate_transition("CLOSED", wi)
    err = exc_info.value
    assert err.from_state == "OPEN"
    assert err.to_state == "CLOSED"


def test_get_allowed_transitions_for_open():
    from app.services.state_machine import get_allowed_transitions
    transitions = get_allowed_transitions("OPEN")
    assert "INVESTIGATING" in transitions
    assert "CLOSED" not in transitions


def test_unknown_status_raises():
    from app.services.state_machine import get_state
    with pytest.raises(ValueError):
        get_state("BANANA")


def test_resolved_on_enter_sets_resolved_at():
    from app.services.state_machine import get_state
    state = get_state("RESOLVED")
    wi = MagicMock()
    wi.resolved_at = None
    state.on_enter(wi)
    assert wi.resolved_at is not None


def test_closed_on_enter_sets_closed_at():
    from app.services.state_machine import get_state
    state = get_state("CLOSED")
    wi = MagicMock()
    wi.closed_at = None
    state.on_enter(wi)
    assert wi.closed_at is not None


def test_open_on_enter_resets_timestamps():
    from app.services.state_machine import get_state
    state = get_state("OPEN")
    wi = MagicMock()
    state.on_enter(wi)
    assert wi.resolved_at is None
    assert wi.closed_at is None


# ── Alert Strategy tests ───────────────────────────────────────────────────────

def test_factory_returns_correct_strategy_for_rdbms():
    from app.services.alert_strategy import AlertStrategyFactory
    strategy = AlertStrategyFactory.get("RDBMS")
    assert strategy.priority == "P0"
    assert strategy.channel == "pagerduty"


def test_factory_returns_correct_strategy_for_cache():
    from app.services.alert_strategy import AlertStrategyFactory
    strategy = AlertStrategyFactory.get("CACHE")
    assert strategy.priority == "P2"
    assert strategy.channel == "email"


def test_factory_returns_correct_strategy_for_api():
    from app.services.alert_strategy import AlertStrategyFactory
    strategy = AlertStrategyFactory.get("API")
    assert strategy.priority == "P1"
    assert strategy.channel == "slack"


def test_factory_returns_default_for_unknown():
    from app.services.alert_strategy import AlertStrategyFactory
    strategy = AlertStrategyFactory.get("MYSTERY_COMPONENT")
    assert strategy.priority == "P3"
    assert strategy.channel == "log"


def test_factory_returns_p0_for_mcp_host():
    from app.services.alert_strategy import AlertStrategyFactory
    strategy = AlertStrategyFactory.get("MCP_HOST")
    assert strategy.priority == "P0"


def test_build_alert_contains_required_fields():
    from app.services.alert_strategy import AlertStrategyFactory
    strategy = AlertStrategyFactory.get("RDBMS")
    wi = MagicMock()
    wi.id = "wi-test-001"
    wi.component_id = "RDBMS_PRIMARY"
    wi.component_type = "RDBMS"
    wi.title = "[P0] RDBMS_PRIMARY: Connection refused"
    wi.signal_count = 15
    wi.created_at = datetime.now(timezone.utc)

    alert = strategy.build_alert(wi)
    assert alert.work_item_id == "wi-test-001"
    assert alert.priority == "P0"
    assert alert.channel == "pagerduty"
    assert "RDBMS_PRIMARY" in alert.message
    assert alert.metadata["signal_count"] == 15


def test_all_strategies_returns_list():
    from app.services.alert_strategy import AlertStrategyFactory
    strategies = AlertStrategyFactory.all_strategies()
    assert isinstance(strategies, list)
    assert len(strategies) >= 6
    component_types = {s["component_type"] for s in strategies}
    assert "RDBMS" in component_types
    assert "CACHE" in component_types
    assert "API" in component_types


# ── RCA validation tests ───────────────────────────────────────────────────────

def test_rca_validation_passes_with_complete_rca():
    from app.services.workflow_engine import _validate_rca
    rca = MagicMock()
    rca.root_cause_description = "Database ran out of connections"
    rca.fix_applied = "Increased max_connections to 1000 and restarted"
    rca.prevention_steps = "Add connection pooling via PgBouncer"
    rca.incident_start = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    rca.incident_end   = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    # Should not raise
    _validate_rca(rca)


def test_rca_validation_fails_when_none():
    from app.services.workflow_engine import _validate_rca, RCARequiredError
    with pytest.raises(RCARequiredError) as exc_info:
        _validate_rca(None)
    assert "required" in str(exc_info.value).lower()


def test_rca_validation_fails_with_empty_fix_applied():
    from app.services.workflow_engine import _validate_rca, RCARequiredError
    rca = MagicMock()
    rca.root_cause_description = "Some cause"
    rca.fix_applied = "   "   # whitespace only
    rca.prevention_steps = "Some steps"
    rca.incident_start = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    rca.incident_end   = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(RCARequiredError) as exc_info:
        _validate_rca(rca)
    assert "fix_applied" in str(exc_info.value)


def test_rca_validation_fails_when_end_before_start():
    from app.services.workflow_engine import _validate_rca, RCARequiredError
    rca = MagicMock()
    rca.root_cause_description = "Some cause"
    rca.fix_applied = "Some fix"
    rca.prevention_steps = "Some steps"
    rca.incident_start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    rca.incident_end   = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)  # before start
    with pytest.raises(RCARequiredError) as exc_info:
        _validate_rca(rca)
    assert "incident_end" in str(exc_info.value)
