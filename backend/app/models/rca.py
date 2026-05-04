import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base
import enum


class RootCauseCategory(str, enum.Enum):
    HARDWARE_FAILURE = "HARDWARE_FAILURE"
    SOFTWARE_BUG = "SOFTWARE_BUG"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    CAPACITY_EXHAUSTION = "CAPACITY_EXHAUSTION"
    NETWORK_ISSUE = "NETWORK_ISSUE"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    HUMAN_ERROR = "HUMAN_ERROR"
    UNKNOWN = "UNKNOWN"


class RCA(Base):
    __tablename__ = "rcas"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    work_item_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("work_items.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    incident_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    incident_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    root_cause_category: Mapped[str] = mapped_column(
        SAEnum(RootCauseCategory), nullable=False
    )
    root_cause_description: Mapped[str] = mapped_column(Text, nullable=False)
    fix_applied: Mapped[str] = mapped_column(Text, nullable=False)
    prevention_steps: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_by: Mapped[str | None] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<RCA {self.id} for WorkItem {self.work_item_id}>"
