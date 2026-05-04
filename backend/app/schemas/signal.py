from pydantic import BaseModel, Field, field_validator
from typing import Any
from enum import Enum
import uuid


class SeverityLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class ComponentType(str, Enum):
    RDBMS = "RDBMS"
    NOSQL = "NOSQL"
    CACHE = "CACHE"
    API = "API"
    QUEUE = "QUEUE"
    MCP_HOST = "MCP_HOST"


class IngestSignalRequest(BaseModel):
    """Incoming signal payload from producers."""

    signal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    component_id: str = Field(..., min_length=1, max_length=128,
                               description="e.g. CACHE_CLUSTER_01, RDBMS_PRIMARY")
    component_type: ComponentType = ComponentType.API
    severity: SeverityLevel = SeverityLevel.MEDIUM
    message: str = Field(..., min_length=1, max_length=1024)
    payload: dict[str, Any] | None = Field(default=None)

    @field_validator("component_id")
    @classmethod
    def uppercase_component_id(cls, v: str) -> str:
        return v.upper().strip()


class IngestSignalResponse(BaseModel):
    accepted: bool
    signal_id: str
    queue_depth: int
    message: str


class SignalRecord(BaseModel):
    """Internal representation stored in SQLite."""

    signal_id: str
    component_id: str
    severity: str
    message: str
    payload: str | None
    work_item_id: str | None = None
    received_at: str | None = None
