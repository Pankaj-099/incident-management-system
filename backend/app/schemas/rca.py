"""
RCA Schemas — Phase 5

Strict validation is enforced here AND in the workflow engine.
The API layer uses these schemas; the engine uses _validate_rca() for
domain checks before allowing the CLOSED transition.
"""

from pydantic import BaseModel, Field, model_validator
from datetime import datetime
from typing import Optional
from app.models.rca import RootCauseCategory


class RCACreateRequest(BaseModel):
    incident_start: datetime = Field(..., description="When the incident began")
    incident_end: datetime = Field(..., description="When the incident was resolved")
    root_cause_category: RootCauseCategory
    root_cause_description: str = Field(..., min_length=20, max_length=5000,
                                         description="Detailed description of the root cause")
    fix_applied: str = Field(..., min_length=10, max_length=5000,
                              description="What was done to fix the incident")
    prevention_steps: str = Field(..., min_length=10, max_length=5000,
                                   description="How to prevent recurrence")
    submitted_by: Optional[str] = Field(None, max_length=128)

    @model_validator(mode="after")
    def validate_times(self) -> "RCACreateRequest":
        if self.incident_end <= self.incident_start:
            raise ValueError("incident_end must be strictly after incident_start")
        return self


class RCAOut(BaseModel):
    id: str
    work_item_id: str
    incident_start: datetime
    incident_end: datetime
    root_cause_category: str
    root_cause_description: str
    fix_applied: str
    prevention_steps: str
    submitted_by: Optional[str]
    mttr_seconds: int
    created_at: datetime

    model_config = {"from_attributes": True}
