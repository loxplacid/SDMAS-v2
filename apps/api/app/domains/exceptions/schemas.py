"""Universal Exception Management — Pydantic schemas (TASK 17).

Mirrors the response shapes of the existing case/data-quality domains so
the frontend can render exceptions with the same patterns it already
uses elsewhere.
"""

from __future__ import annotations

import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.pagination import Page
from app.domains.exceptions.models import (
    EXCEPTION_SEVERITIES,
    EXCEPTION_TYPES,
)

# ---------------------------------------------------------------------------
# Create / update
# ---------------------------------------------------------------------------


class ExceptionCreate(BaseModel):
    """Payload to create an exception from any source domain.

    ``source_domain`` + ``source_type`` + ``source_id`` identify the
    originating record.  Re-creating an exception for the same source
    triple is rejected (ConflictError) — idempotent callers should query
    ``GET /exceptions/by-source`` first or swallow the conflict.
    """

    exception_type: str
    severity: str
    title: str = Field(min_length=1, max_length=300)
    description: Optional[str] = Field(default=None, max_length=10000)
    source_domain: str = Field(min_length=1, max_length=50)
    source_type: str = Field(min_length=1, max_length=50)
    source_id: Optional[int] = None
    rule_code: Optional[str] = Field(default=None, max_length=100)
    entity_type: Optional[str] = Field(default=None, max_length=50)
    entity_id: Optional[int] = None
    student_id: Optional[int] = None
    evidence: Optional[dict[str, Any]] = None
    owner_id: Optional[int] = None
    priority: Optional[str] = Field(default=None, max_length=20)
    due_at: Optional[datetime.datetime] = None

    @field_validator("exception_type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in EXCEPTION_TYPES:
            raise ValueError(f"exception_type must be one of {sorted(EXCEPTION_TYPES)}, got {v!r}")
        return v

    @field_validator("severity")
    @classmethod
    def _valid_severity(cls, v: str) -> str:
        if v not in EXCEPTION_SEVERITIES:
            raise ValueError(f"severity must be one of {sorted(EXCEPTION_SEVERITIES)}, got {v!r}")
        return v


class ExceptionResolve(BaseModel):
    resolution_type: str
    resolution_note: Optional[str] = Field(default=None, max_length=10000)
    root_cause: Optional[str] = Field(default=None, max_length=10000)


class ExceptionAssign(BaseModel):
    owner_id: Optional[int] = None


class ExceptionSeverityUpdate(BaseModel):
    severity: str

    @field_validator("severity")
    @classmethod
    def _valid_severity(cls, v: str) -> str:
        if v not in EXCEPTION_SEVERITIES:
            raise ValueError(f"severity must be one of {sorted(EXCEPTION_SEVERITIES)}, got {v!r}")
        return v


class ExceptionDueDateUpdate(BaseModel):
    due_at: Optional[datetime.datetime] = None


class ExceptionRootCauseUpdate(BaseModel):
    root_cause: str = Field(min_length=1, max_length=10000)


class ExceptionEvidenceAdd(BaseModel):
    evidence: dict[str, Any]


class ExceptionCaseLink(BaseModel):
    case_id: int


class ExceptionWorkflowLink(BaseModel):
    workflow_instance_id: int


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class ExceptionEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exception_id: int
    event_seq: int
    event_type: str
    actor_id: Optional[int] = None
    actor_name: Optional[str] = None
    message: str
    data: Optional[dict[str, Any]] = None
    created_at: datetime.datetime


class ExceptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    source_domain: str
    source_type: str
    source_id: Optional[int] = None
    exception_type: str
    severity: str
    rule_code: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    student_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    status: str
    owner_id: Optional[int] = None
    priority: str
    due_at: Optional[datetime.datetime] = None
    root_cause: Optional[str] = None
    resolution_type: Optional[str] = None
    resolution_note: Optional[str] = None
    resolved_at: Optional[datetime.datetime] = None
    resolved_by: Optional[int] = None
    closed_at: Optional[datetime.datetime] = None
    closed_by: Optional[int] = None
    evidence: Optional[dict[str, Any]] = None
    case_id: Optional[int] = None
    workflow_instance_id: Optional[int] = None
    detected_at: datetime.datetime
    last_verified_at: datetime.datetime
    version: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    events: list[ExceptionEventResponse] = []


ExceptionPage = Page[ExceptionResponse]


class ExceptionMetricsResponse(BaseModel):
    by_status: dict[str, int]
    open_by_severity: dict[str, int]
    overdue: int


class ExceptionStatusCheck(BaseModel):
    """Response model for transition validation."""

    status: str
    allowed_transitions: list[str]
