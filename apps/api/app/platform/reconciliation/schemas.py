"""Universal reconciliation engine — Pydantic schemas (API contract)."""

from __future__ import annotations

import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.platform.reconciliation.models import (
    APPROVAL_DECISIONS,
    EXCEPTION_SEVERITIES,
    EXCEPTION_STATUSES,
    MATCH_STATUSES,
    RUN_STATUSES,
)

# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


class ReconciliationRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    run_type: str = Field(min_length=1, max_length=80)
    source_dataset: str = Field(min_length=1, max_length=255)
    target_dataset: str = Field(min_length=1, max_length=255)
    match_keys: list[dict[str, Any]] = Field(default_factory=list)
    comparison_fields: list[dict[str, Any]] = Field(default_factory=list)
    idempotency_key: Optional[str] = Field(default=None, max_length=200)
    rule_config_id: Optional[int] = None
    created_by: Optional[int] = None


class ReconciliationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    name: str
    run_type: str
    source_dataset: str
    target_dataset: str
    status: str
    match_keys: Optional[dict[str, Any]] = None
    comparison_fields: Optional[dict[str, Any]] = None
    idempotency_key: Optional[str] = None
    rule_config_id: Optional[int] = None
    summary: Optional[dict[str, Any]] = None
    created_by: Optional[int] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# Rule configs
# ---------------------------------------------------------------------------


class RuleConfigCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    run_type: str = Field(min_length=1, max_length=80)
    description: Optional[str] = Field(default=None, max_length=1000)
    match_keys: list[dict[str, Any]] = Field(default_factory=list)
    comparison_fields: list[dict[str, Any]] = Field(default_factory=list)


class RuleConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    name: str
    run_type: str
    description: Optional[str] = None
    match_keys: Optional[dict[str, Any]] = None
    comparison_fields: Optional[dict[str, Any]] = None
    is_active: bool
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# Match inputs / outputs
# ---------------------------------------------------------------------------


class ReconcileInput(BaseModel):
    """Source + target records for a single reconciliation execution."""

    model_config = ConfigDict(extra="forbid")

    source_records: list[dict[str, Any]]
    target_records: list[dict[str, Any]]


class ReconciliationMatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    run_id: int
    source_ref: str
    source_payload: Optional[dict[str, Any]] = None
    target_ref: Optional[str] = None
    target_payload: Optional[dict[str, Any]] = None
    status: str
    differences: Optional[dict[str, Any]] = None
    within_tolerance: bool
    exception_code: Optional[str] = None
    exception_reason: Optional[str] = None
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ExceptionResolve(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: accept | reject | correct
    decision: str = Field(pattern=r"^(accept|reject|correct)$")
    note: Optional[str] = Field(default=None, max_length=1000)
    corrected_value: Optional[Any] = None
    resolved_by: Optional[int] = None


class ReconciliationExceptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    run_id: int
    match_id: int
    code: str
    severity: str
    reason: Optional[str] = None
    status: str
    resolution: Optional[dict[str, Any]] = None
    resolved_by: Optional[int] = None
    resolved_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------


class ApprovalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str = Field(max_length=20)
    approver_id: Optional[int] = None
    comment: Optional[str] = Field(default=None, max_length=1000)


class ApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    run_id: int
    decision: str
    approver_id: Optional[int] = None
    comment: Optional[str] = None
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


class EvidenceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(default="audit", max_length=30)
    reference: str = Field(min_length=1, max_length=512)
    match_id: Optional[int] = None
    checksum: Optional[str] = Field(default=None, max_length=128)
    note: Optional[str] = Field(default=None, max_length=1000)


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    run_id: int
    match_id: Optional[int] = None
    kind: str
    reference: str
    checksum: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime.datetime


__all__ = [
    "ReconciliationRunCreate",
    "ReconciliationRunRead",
    "RuleConfigCreate",
    "RuleConfigRead",
    "ReconcileInput",
    "ReconciliationMatchRead",
    "ExceptionResolve",
    "ReconciliationExceptionRead",
    "ApprovalCreate",
    "ApprovalRead",
    "EvidenceCreate",
    "EvidenceRead",
    "RUN_STATUSES",
    "MATCH_STATUSES",
    "EXCEPTION_STATUSES",
    "EXCEPTION_SEVERITIES",
    "APPROVAL_DECISIONS",
]
