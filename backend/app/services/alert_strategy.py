"""
Strategy Pattern — Alerting

Different component failures require different alert payloads and channels.
Each AlertStrategy encapsulates the alerting logic for one class of component.

Usage:
    strategy = AlertStrategyFactory.get("RDBMS")
    alert = strategy.build_alert(work_item)
    await strategy.dispatch(alert)

Adding a new strategy requires only:
  1. Subclass AlertStrategy
  2. Register in AlertStrategyFactory
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from app.models.work_item import WorkItem

logger = logging.getLogger("ims.alerting")


@dataclass
class Alert:
    work_item_id: str
    component_id: str
    component_type: str
    priority: str
    title: str
    channel: str          # "pagerduty" | "slack" | "email" | "log"
    severity_label: str
    message: str
    triggered_at: str
    metadata: dict


class AlertStrategy(ABC):
    """Abstract base — one concrete implementation per component class."""

    @property
    @abstractmethod
    def component_type(self) -> str:
        ...

    @property
    @abstractmethod
    def priority(self) -> str:
        ...

    @property
    @abstractmethod
    def channel(self) -> str:
        ...

    @property
    @abstractmethod
    def severity_label(self) -> str:
        ...

    def build_alert(self, work_item: "WorkItem") -> Alert:
        return Alert(
            work_item_id=work_item.id,
            component_id=work_item.component_id,
            component_type=work_item.component_type,
            priority=self.priority,
            title=work_item.title,
            channel=self.channel,
            severity_label=self.severity_label,
            message=self._compose_message(work_item),
            triggered_at=datetime.now(timezone.utc).isoformat(),
            metadata=self._extra_metadata(work_item),
        )

    @abstractmethod
    def _compose_message(self, work_item: "WorkItem") -> str:
        ...

    def _extra_metadata(self, work_item: "WorkItem") -> dict:
        return {
            "signal_count": work_item.signal_count,
            "created_at": work_item.created_at.isoformat() if work_item.created_at else None,
        }

    async def dispatch(self, alert: Alert) -> None:
        """
        In production this would POST to PagerDuty / Slack / etc.
        For now we log the alert payload — replace with real integrations.
        """
        logger.warning(
            "🚨 ALERT [%s/%s] via %s | %s | signals=%s",
            alert.priority,
            alert.severity_label,
            alert.channel.upper(),
            alert.title,
            alert.metadata.get("signal_count", "?"),
        )


# ── Concrete Strategies ───────────────────────────────────────────────────────

class RDBMSAlertStrategy(AlertStrategy):
    """P0 — Database failures. Page on-call immediately via PagerDuty."""
    component_type = "RDBMS"
    priority = "P0"
    channel = "pagerduty"
    severity_label = "CRITICAL"

    def _compose_message(self, work_item: "WorkItem") -> str:
        return (
            f"🔴 P0 DATABASE OUTAGE — {work_item.component_id}\n"
            f"{work_item.title}\n"
            f"Signal count: {work_item.signal_count} | "
            f"Immediate action required. All dependent services are at risk."
        )

    def _extra_metadata(self, work_item: "WorkItem") -> dict:
        base = super()._extra_metadata(work_item)
        return {**base, "escalation_policy": "database_oncall", "auto_page": True}


class MCPHostAlertStrategy(AlertStrategy):
    """P0 — MCP Host failures. Tool calls failing, page immediately."""
    component_type = "MCP_HOST"
    priority = "P0"
    channel = "pagerduty"
    severity_label = "CRITICAL"

    def _compose_message(self, work_item: "WorkItem") -> str:
        return (
            f"🔴 P0 MCP HOST DOWN — {work_item.component_id}\n"
            f"{work_item.title}\n"
            f"All tool calls through this host are failing. "
            f"Signal count: {work_item.signal_count}"
        )

    def _extra_metadata(self, work_item: "WorkItem") -> dict:
        base = super()._extra_metadata(work_item)
        return {**base, "escalation_policy": "platform_oncall", "auto_page": True}


class APIAlertStrategy(AlertStrategy):
    """P1 — API / Gateway failures. Notify via Slack #incidents."""
    component_type = "API"
    priority = "P1"
    channel = "slack"
    severity_label = "HIGH"

    def _compose_message(self, work_item: "WorkItem") -> str:
        return (
            f"🟠 P1 API INCIDENT — {work_item.component_id}\n"
            f"{work_item.title}\n"
            f"Signal count: {work_item.signal_count}. "
            f"Investigate and update status within 30 minutes."
        )

    def _extra_metadata(self, work_item: "WorkItem") -> dict:
        base = super()._extra_metadata(work_item)
        return {**base, "slack_channel": "#incidents", "mention": "@oncall-api"}


class QueueAlertStrategy(AlertStrategy):
    """P1 — Async queue backlog. Notify via Slack."""
    component_type = "QUEUE"
    priority = "P1"
    channel = "slack"
    severity_label = "HIGH"

    def _compose_message(self, work_item: "WorkItem") -> str:
        return (
            f"🟠 P1 QUEUE BACKLOG — {work_item.component_id}\n"
            f"{work_item.title}\n"
            f"Consumer lag detected. Signal count: {work_item.signal_count}."
        )

    def _extra_metadata(self, work_item: "WorkItem") -> dict:
        base = super()._extra_metadata(work_item)
        return {**base, "slack_channel": "#incidents", "mention": "@oncall-backend"}


class CacheAlertStrategy(AlertStrategy):
    """P2 — Cache failures. Email notification."""
    component_type = "CACHE"
    priority = "P2"
    channel = "email"
    severity_label = "MEDIUM"

    def _compose_message(self, work_item: "WorkItem") -> str:
        return (
            f"🟡 P2 CACHE INCIDENT — {work_item.component_id}\n"
            f"{work_item.title}\n"
            f"Signal count: {work_item.signal_count}. "
            f"DB fallback active. Monitor for escalation."
        )

    def _extra_metadata(self, work_item: "WorkItem") -> dict:
        base = super()._extra_metadata(work_item)
        return {**base, "email_list": ["oncall@company.com"], "sla_minutes": 120}


class NoSQLAlertStrategy(AlertStrategy):
    """P2 — NoSQL / Document store issues. Email notification."""
    component_type = "NOSQL"
    priority = "P2"
    channel = "email"
    severity_label = "MEDIUM"

    def _compose_message(self, work_item: "WorkItem") -> str:
        return (
            f"🟡 P2 NOSQL INCIDENT — {work_item.component_id}\n"
            f"{work_item.title}\n"
            f"Replication or query issues detected. Signal count: {work_item.signal_count}."
        )


class DefaultAlertStrategy(AlertStrategy):
    """P3 fallback — log only."""
    component_type = "UNKNOWN"
    priority = "P3"
    channel = "log"
    severity_label = "LOW"

    def _compose_message(self, work_item: "WorkItem") -> str:
        return f"ℹ️  P3 INCIDENT — {work_item.component_id}: {work_item.title}"


# ── Factory ───────────────────────────────────────────────────────────────────

class AlertStrategyFactory:
    _registry: dict[str, AlertStrategy] = {
        s.component_type: s for s in [
            RDBMSAlertStrategy(),
            MCPHostAlertStrategy(),
            APIAlertStrategy(),
            QueueAlertStrategy(),
            CacheAlertStrategy(),
            NoSQLAlertStrategy(),
            DefaultAlertStrategy(),
        ]
    }

    @classmethod
    def get(cls, component_type: str) -> AlertStrategy:
        return cls._registry.get(component_type, cls._registry["UNKNOWN"])

    @classmethod
    def all_strategies(cls) -> list[dict]:
        """Return metadata about all registered strategies (for docs/UI)."""
        return [
            {
                "component_type": s.component_type,
                "priority": s.priority,
                "channel": s.channel,
                "severity_label": s.severity_label,
            }
            for s in cls._registry.values()
        ]
