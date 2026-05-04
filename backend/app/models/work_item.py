import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base
import enum


class WorkItemStatus(str, enum.Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class Priority(str, enum.Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class ComponentType(str, enum.Enum):
    RDBMS = "RDBMS"
    NOSQL = "NOSQL"
    CACHE = "CACHE"
    API = "API"
    QUEUE = "QUEUE"
    MCP_HOST = "MCP_HOST"


class WorkItem(Base):
    __tablename__ = "work_items"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    component_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    component_type: Mapped[str] = mapped_column(
        SAEnum(ComponentType), nullable=False, default=ComponentType.API
    )
    status: Mapped[str] = mapped_column(
        SAEnum(WorkItemStatus), nullable=False, default=WorkItemStatus.OPEN, index=True
    )
    priority: Mapped[str] = mapped_column(
        SAEnum(Priority), nullable=False, default=Priority.P2
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    signal_count: Mapped[int] = mapped_column(default=1)
    mttr_seconds: Mapped[int | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<WorkItem {self.id} [{self.status}] {self.component_id}>"
