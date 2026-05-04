"""
Workflow Engine — Phase 4

Orchestrates the full Work Item lifecycle:
  1. Validates transition via State Machine
  2. Checks domain guards (e.g. RCA required for CLOSED)
  3. Applies state side-effects (timestamps)
  4. Persists to PostgreSQL (transactional, with retry)
  5. Dispatches alert via Strategy Pattern
  6. Invalidates Redis dashboard cache
  7. Broadcasts ws event to dashboard
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.work_item import WorkItem, WorkItemStatus
from app.models.rca import RCA
from app.services.state_machine import get_state, InvalidTransitionError, get_allowed_transitions
from app.services.alert_strategy import AlertStrategyFactory
from app.services.dashboard_cache import invalidate_dashboard_cache
from app.services.ws_manager import ws_manager
from app.services.metrics import decrement_open_work_items

logger = logging.getLogger("ims.workflow")


class RCARequiredError(Exception):
    """Raised when trying to CLOSE a Work Item without a complete RCA."""
    pass


async def _get_rca(db: AsyncSession, work_item_id: str) -> RCA | None:
    result = await db.execute(
        select(RCA).where(RCA.work_item_id == work_item_id)
    )
    return result.scalar_one_or_none()


def _validate_rca(rca: RCA | None) -> None:
    """Enforce RCA completeness before allowing CLOSED transition."""
    if rca is None:
        raise RCARequiredError(
            "RCA is required before closing a Work Item. "
            "Submit a complete RCA via POST /work-items/{id}/rca first."
        )
    missing = []
    if not rca.root_cause_description or not rca.root_cause_description.strip():
        missing.append("root_cause_description")
    if not rca.fix_applied or not rca.fix_applied.strip():
        missing.append("fix_applied")
    if not rca.prevention_steps or not rca.prevention_steps.strip():
        missing.append("prevention_steps")
    if rca.incident_start >= rca.incident_end:
        missing.append("incident_end must be after incident_start")
    if missing:
        raise RCARequiredError(
            f"RCA is incomplete. Missing or invalid fields: {', '.join(missing)}"
        )


async def transition_work_item(
    db: AsyncSession,
    work_item_id: str,
    target_status: str,
    actor: str | None = None,
) -> WorkItem:
    """
    Execute a validated state transition on a Work Item.

    Raises:
        ValueError            — work item not found
        InvalidTransitionError — transition not allowed by state machine
        RCARequiredError       — CLOSED without complete RCA
    """
    # ── 1. Load work item ──────────────────────────────────────────────────────
    result = await db.execute(
        select(WorkItem).where(WorkItem.id == work_item_id)
    )
    wi = result.scalar_one_or_none()
    if wi is None:
        raise ValueError(f"Work item {work_item_id!r} not found")

    current_status = wi.status
    logger.info(
        "Transition request: WI=%s %s → %s (actor=%s)",
        work_item_id[:8], current_status, target_status, actor or "system"
    )

    # ── 2. State machine validation ────────────────────────────────────────────
    current_state = get_state(current_status)
    current_state.validate_transition(target_status, wi)

    # ── 3. Domain guard: RCA required for CLOSED ──────────────────────────────
    if target_status == WorkItemStatus.CLOSED:
        rca = await _get_rca(db, work_item_id)
        _validate_rca(rca)

    # ── 4. Apply new state side-effects ───────────────────────────────────────
    new_state = get_state(target_status)
    wi.status = target_status
    new_state.on_enter(wi)

    # ── 5. Persist transition (transactional) ─────────────────────────────────
    update_vals: dict = {
        "status": wi.status,
        "updated_at": wi.updated_at,
    }
    if wi.resolved_at:
        update_vals["resolved_at"] = wi.resolved_at
    if wi.closed_at:
        update_vals["closed_at"] = wi.closed_at

    await db.execute(
        update(WorkItem).where(WorkItem.id == work_item_id).values(**update_vals)
    )
    await db.commit()
    await db.refresh(wi)

    logger.info(
        "✅ WI=%s transitioned %s → %s",
        work_item_id[:8], current_status, target_status
    )

    # ── 6. Metrics: decrement open count on close/resolve ────────────────────
    if target_status in (WorkItemStatus.CLOSED, WorkItemStatus.RESOLVED):
        await decrement_open_work_items()

    # ── 7. Alert dispatch via Strategy Pattern ────────────────────────────────
    if target_status == WorkItemStatus.INVESTIGATING:
        strategy = AlertStrategyFactory.get(wi.component_type)
        alert = strategy.build_alert(wi)
        await strategy.dispatch(alert)

    # ── 8. Invalidate dashboard cache ─────────────────────────────────────────
    await invalidate_dashboard_cache()

    # ── 9. Broadcast via WebSocket ────────────────────────────────────────────
    await ws_manager.broadcast(
        "work_item_updated",
        {
            "id": wi.id,
            "component_id": wi.component_id,
            "component_type": wi.component_type,
            "status": wi.status,
            "priority": wi.priority,
            "title": wi.title,
            "signal_count": wi.signal_count,
            "mttr_seconds": wi.mttr_seconds,
            "created_at": wi.created_at.isoformat() if wi.created_at else None,
            "updated_at": wi.updated_at.isoformat() if wi.updated_at else None,
            "resolved_at": wi.resolved_at.isoformat() if wi.resolved_at else None,
            "closed_at": wi.closed_at.isoformat() if wi.closed_at else None,
        },
    )

    return wi


def describe_allowed_transitions(status: str) -> list[dict]:
    """Return transition options with descriptions — used by the UI."""
    transitions = get_allowed_transitions(status)
    labels = {
        "INVESTIGATING": {"label": "Begin Investigation", "description": "Assign and start actively working the incident"},
        "RESOLVED":      {"label": "Mark Resolved",       "description": "The issue is fixed and services are stable"},
        "CLOSED":        {"label": "Close Incident",      "description": "Submit RCA and close — requires complete RCA"},
        "OPEN":          {"label": "Re-open",             "description": "Revert to open if the fix did not hold"},
    }
    return [
        {"status": t, **labels.get(t, {"label": t, "description": ""})}
        for t in transitions
    ]
