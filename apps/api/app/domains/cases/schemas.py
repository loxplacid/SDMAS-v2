"""Operational Case Management — API schemas."""

from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.domains.cases.models import (
    CASE_EVIDENCE_KINDS,
    CASE_PRIORITIES,
    CASE_VALID_SOURCES,
    CASE_VALID_STATUSES,
)


class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_number: str
    campus_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    case_type: str
    priority: str
    original_priority: str
    status: str
    source_type: str
    source_id: Optional[int] = None
    student_id: Optional[int] = None
    created_by: Optional[int] = None
    assigned_to: Optional[int] = None
    assigned_at: Optional[datetime.datetime] = None
    due_at: Optional[datetime.datetime] = None
    escalated_at: Optional[datetime.datetime] = None
    resolved_at: Optional[datetime.datetime] = None
    resolved_by: Optional[int] = None
    resolved_reason: Optional[str] = None
    closed_at: Optional[datetime.datetime] = None
    closed_by: Optional[int] = None
    version: int = 1
    created_at: datetime.datetime
    updated_at: datetime.datetime

    # Derived (always calculated, never stored)
    sla_state: str = "ON_TRACK"
    assignee_name: Optional[str] = None


class CaseEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_seq: int
    event_type: str
    actor_id: Optional[int] = None
    actor_name: Optional[str] = None
    message: str
    data: Optional[dict] = None
    created_at: datetime.datetime


class CaseCommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author_id: Optional[int] = None
    author_name: Optional[str] = None
    body: str
    created_at: datetime.datetime


class CaseEvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    title: str
    summary: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None
    data: Optional[dict] = None
    added_by: Optional[int] = None
    created_at: datetime.datetime


class CaseDetailOut(BaseModel):
    case: CaseOut
    events: list[CaseEventOut] = []
    comments: list[CaseCommentOut] = []
    evidence: list[CaseEvidenceOut] = []


class CasePage(BaseModel):
    items: list[CaseOut]
    total: int
    page: int
    size: int
    pages: int


class CaseCreateIn(BaseModel):
    title: str
    description: Optional[str] = None
    case_type: str = "administrative"
    priority: Optional[str] = None
    source_type: str = "manual"
    source_id: Optional[int] = None
    student_id: Optional[int] = None
    assigned_to: Optional[int] = None
    due_at: Optional[datetime.datetime] = None

    @field_validator("case_type")
    @classmethod
    def validate_case_type(cls, v: str) -> str:
        allowed = {
            "attendance", "finance", "academic", "documents",
            "data_quality", "admissions", "operational", "administrative",
        }
        if v not in allowed:
            raise ValueError(f"Invalid case type: {v}")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in CASE_PRIORITIES:
            raise ValueError(f"Invalid priority: {v}")
        return v

    @field_validator("source_type")
    @classmethod
    def validate_source(cls, v: str) -> str:
        if v not in CASE_VALID_SOURCES:
            raise ValueError(f"Invalid source type: {v}")
        return v


class CaseTransitionIn(BaseModel):
    status: str
    reason: Optional[str] = None
    version: Optional[int] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in CASE_VALID_STATUSES:
            raise ValueError(f"Invalid status: {v}")
        return v


class CaseAssignIn(BaseModel):
    assignee_id: int
    reason: Optional[str] = None
    version: Optional[int] = None


class CasePriorityIn(BaseModel):
    priority: str
    reason: Optional[str] = None
    version: Optional[int] = None

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        if v not in CASE_PRIORITIES:
            raise ValueError(f"Invalid priority: {v}")
        return v


class CaseDueDateIn(BaseModel):
    due_at: Optional[datetime.datetime] = None
    reason: Optional[str] = None
    version: Optional[int] = None


class CaseCommentIn(BaseModel):
    body: str


class CaseEvidenceIn(BaseModel):
    kind: str
    title: str
    summary: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None
    metadata: Optional[dict] = None

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, v: str) -> str:
        if v not in CASE_EVIDENCE_KINDS:
            raise ValueError(f"Invalid evidence kind: {v}")
        return v


class CaseOverview(BaseModel):
    open: int = 0
    critical: int = 0
    overdue: int = 0
    due_today: int = 0
    my_open: int = 0
    unassigned: int = 0
    by_status: dict[str, int] = {}
    generated_at: str


class CaseMetrics(BaseModel):
    open: int = 0
    critical: int = 0
    overdue: int = 0
    due_today: int = 0
    by_type: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    avg_resolution_hours: Optional[float] = None
    median_resolution_hours: Optional[float] = None
    resolution_rate: Optional[float] = None
    sla_compliance: Optional[float] = None
    generated_at: str


class WorkloadItem(BaseModel):
    assignee_id: int
    assignee_name: Optional[str] = None
    open_cases: int = 0
    critical_cases: int = 0
    overdue_cases: int = 0


class AssignableUser(BaseModel):
    id: int
    name: str
    role: str


class BulkResult(BaseModel):
    updated: list[int]
    skipped: int


class BulkAssignIn(BaseModel):
    case_ids: list[int]
    assignee_id: int


class BulkPriorityIn(BaseModel):
    case_ids: list[int]
    priority: str
    reason: Optional[str] = None


class BulkStatusIn(BaseModel):
    case_ids: list[int]
    status: str
    reason: Optional[str] = None


class BulkDueDateIn(BaseModel):
    case_ids: list[int]
    due_at: Optional[datetime.datetime] = None


class EscalationResult(BaseModel):
    escalated: list[int]
    count: int
