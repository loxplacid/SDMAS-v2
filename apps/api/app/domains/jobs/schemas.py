from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class JobCreate(BaseModel):
    job_type: str = Field(..., max_length=64)
    params: dict[str, Any] | None = None
    priority: int = Field(default=100, ge=0, le=1000)
    max_retries: int = Field(default=3, ge=0, le=25)
    scheduled_at: datetime.datetime | None = None
    identity_key: str | None = Field(default=None, max_length=255)
    user_id: int | None = None
    campus_id: int | None = None


class JobUpdate(BaseModel):
    status: str | None = None
    progress: float | None = Field(default=None, ge=0.0, le=100.0)
    result: dict[str, Any] | None = None
    last_error: str | None = None


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_type: str
    status: str
    params: dict[str, Any] | None = None
    priority: int
    max_retries: int
    retry_count: int
    last_error: str | None = None
    progress: float
    result: dict[str, Any] | None = None
    scheduled_at: datetime.datetime | None = None
    started_at: datetime.datetime | None = None
    completed_at: datetime.datetime | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    identity_key: str | None = None
    user_id: int | None = None
    campus_id: int | None = None


class JobListResponse(BaseModel):
    items: list[JobResponse]
    total: int
