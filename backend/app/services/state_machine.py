"""
State Pattern — Work Item Lifecycle

Each state encapsulates:
  - Which transitions are allowed FROM this state
  - What side-effects to run on entry (e.g. set timestamps)
  - A human-readable description

Transitions:
  OPEN → INVESTIGATING
  INVESTIGATING → RESOLVED
  RESOLVED → CLOSED  (requires RCA — enforced here)
  RESOLVED → INVESTIGATING  (re-open investigation)
  Any → OPEN  (escalate/reopen, except from CLOSED)

The WorkItemStateMachine orchestrates state objects and executes transitions.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.work_item import WorkItem


class InvalidTransitionError(Exception):
    """Raised when a state transition is not allowed."""
    def __init__(self, from_state: str, to_state: str, reason: str = ""):
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason
        super().__init__(
            f"Cannot transition from {from_state} → {to_state}"
            + (f": {reason}" if reason else "")
        )


class WorkItemStateBase(ABC):
    """Abstract base for all Work Item states."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def allowed_transitions(self) -> set[str]:
        """Set of state names this state can transition TO."""
        ...

    def can_transition_to(self, target: str) -> bool:
        return target in self.allowed_transitions

    def on_enter(self, work_item: "WorkItem") -> None:
        """Side effects when entering this state. Override as needed."""
        work_item.updated_at = datetime.now(timezone.utc)

    def validate_transition(self, target: str, work_item: "WorkItem") -> None:
        """
        Raise InvalidTransitionError if the transition is not allowed.
        Override to add domain-specific guards (e.g. RCA check).
        """
        if not self.can_transition_to(target):
            raise InvalidTransitionError(
                self.name, target,
                f"Allowed from {self.name}: {self.allowed_transitions or 'none'}"
            )


# ── Concrete States ───────────────────────────────────────────────────────────

class OpenState(WorkItemStateBase):
    name = "OPEN"
    allowed_transitions = {"INVESTIGATING"}

    def on_enter(self, work_item: "WorkItem") -> None:
        super().on_enter(work_item)
        # Reset timestamps if reopened
        work_item.resolved_at = None
        work_item.closed_at = None


class InvestigatingState(WorkItemStateBase):
    name = "INVESTIGATING"
    allowed_transitions = {"RESOLVED", "OPEN"}

    def on_enter(self, work_item: "WorkItem") -> None:
        super().on_enter(work_item)


class ResolvedState(WorkItemStateBase):
    name = "RESOLVED"
    allowed_transitions = {"CLOSED", "INVESTIGATING"}

    def on_enter(self, work_item: "WorkItem") -> None:
        super().on_enter(work_item)
        work_item.resolved_at = datetime.now(timezone.utc)


class ClosedState(WorkItemStateBase):
    name = "CLOSED"
    allowed_transitions = set()          # terminal state — no exits

    def on_enter(self, work_item: "WorkItem") -> None:
        super().on_enter(work_item)
        work_item.closed_at = datetime.now(timezone.utc)

    def validate_transition(self, target: str, work_item: "WorkItem") -> None:
        raise InvalidTransitionError("CLOSED", target, "CLOSED is a terminal state")


# ── State Registry ────────────────────────────────────────────────────────────

_STATE_REGISTRY: dict[str, WorkItemStateBase] = {
    "OPEN":          OpenState(),
    "INVESTIGATING": InvestigatingState(),
    "RESOLVED":      ResolvedState(),
    "CLOSED":        ClosedState(),
}


def get_state(status: str) -> WorkItemStateBase:
    state = _STATE_REGISTRY.get(status)
    if not state:
        raise ValueError(f"Unknown work item status: {status!r}")
    return state


def get_allowed_transitions(status: str) -> list[str]:
    """Return the list of states reachable from the given status."""
    return sorted(get_state(status).allowed_transitions)
