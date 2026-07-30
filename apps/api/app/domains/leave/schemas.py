from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.domains.leave.models import LEAVE_TYPES


class LeaveRequestCreate(BaseModel):
    leave_type: str
    start_date: str
    end_date: str
    reason: Optional[str] = None

    @field_validator("leave_type")
    @classmethod
    def validate_leave_type(cls, v: str) -> str:
        if v not in LEAVE_TYPES:
            raise ValueError(f"Invalid leave type. Must be one of {LEAVE_TYPES}")
        return v

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Date cannot be empty")
        return v.strip()


class LeaveRequestUpdate(BaseModel):
    leave_type: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    reason: Optional[str] = None

    @field_validator("leave_type")
    @classmethod
    def validate_leave_type(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in LEAVE_TYPES:
            raise ValueError(f"Invalid leave type. Must be one of {LEAVE_TYPES}")
        return v


class LeaveRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    leave_type: str
    start_date: str
    end_date: str
    reason: Optional[str] = None
    duration_days: int
    workflow_instance_id: Optional[int] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


# Response that includes workflow detail
class LeaveRequestDetailResponse(LeaveRequestResponse):
    workflow_status: Optional[str] = None
    workflow_current_step: Optional[str] = None
