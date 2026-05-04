from pydantic import BaseModel
from datetime import datetime
from app.models.work_item import WorkItemStatus, Priority, ComponentType


class WorkItemOut(BaseModel):
    id: str
    component_id: str
    component_type: str
    status: str
    priority: str
    title: str
    description: str | None
    signal_count: int
    mttr_seconds: int | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    closed_at: datetime | None

    model_config = {"from_attributes": True}


class WorkItemListResponse(BaseModel):
    items: list[WorkItemOut]
    total: int
