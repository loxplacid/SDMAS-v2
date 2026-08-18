"""Pydantic schemas for the compliance domain.

All response models carry deterministic evaluation results with full
explainability — no AI narratives.
"""

from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------


class RegulationCreate(BaseModel):
    regulation_id: str = Field(..., min_length=1, max_length=200)
    name: str = Field(..., min_length=1, max_length=300)
    description: str | None = None
    authority: str | None = None
    jurisdiction: str | None = None
    effective_from: datetime.datetime | None = None
    effective_until: datetime.datetime | None = None


class RegulationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    regulation_id: str
    name: str
    description: str | None = None
    authority: str | None = None
    jurisdiction: str | None = None
    effective_from: datetime.datetime | None = None
    effective_until: datetime.datetime | None = None
    status: str
    created_at: datetime.datetime


class RequirementCreate(BaseModel):
    requirement_id: str = Field(..., min_length=1, max_length=200)
    title: str = Field(..., min_length=1, max_length=300)
    description: str | None = None
    category: str | None = None
    severity: str = "medium"
    is_mandatory: bool = True
    effective_from: datetime.datetime | None = None
    effective_until: datetime.datetime | None = None


class RequirementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    regulation_id: int
    requirement_id: str
    title: str
    description: str | None = None
    category: str | None = None
    severity: str
    is_mandatory: bool


class RuleDefinition(BaseModel):
    """A single rule definition within a schema pack."""

    rule_code: str
    rule_type: str = Field(
        ...,
        description=(
            "field_exists | value_range | value_in_set | "
            "count_min | count_max | ratio_min | "
            "custom_query | aggregate_check"
        ),
    )
    target_entity: str
    target_field: str | None = None
    condition: dict[str, Any] | None = None
    expected: dict[str, Any] | None = None
    severity: str = "medium"
    is_mandatory: bool = True
    explanation: str | None = None
    requirement_id: str | None = None


class SchemaCreate(BaseModel):
    schema_id: str = Field(..., min_length=1, max_length=200)
    title: str = Field(..., min_length=1, max_length=300)
    description: str | None = None
    data_sources: list[str] | None = None
    rules: list[RuleDefinition] = []


class SchemaResponse(BaseModel):
    id: int
    schema_id: str
    version: int
    title: str
    description: str | None = None
    data_sources: list[str] | None = None
    is_current: bool
    status: str
    effective_from: datetime.datetime | None = None
    effective_until: datetime.datetime | None = None
    rule_count: int = 0
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class RuleResponse(BaseModel):
    id: int
    schema_id: int
    rule_code: str
    rule_type: str
    target_entity: str
    target_field: str | None = None
    severity: str
    is_mandatory: bool
    explanation: str | None = None
    enabled: bool

    model_config = ConfigDict(from_attributes=True)


class SubmissionCreate(BaseModel):
    regulation_id: int | None = None
    schema_id: int | None = None
    submission_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=300)
    description: str | None = None
    data_snapshot: dict[str, Any] | None = None


class EvaluationResult(BaseModel):
    """Single rule evaluation result with full explainability."""

    rule_code: str
    requirement_id: str | None = None
    result: str  # pass | fail | warning | skipped | error
    severity: str
    expected_value: dict[str, Any] | None = None
    actual_value: dict[str, Any] | None = None
    explanation: str | None = None
    trace: dict[str, Any] | None = None


class SubmissionResponse(BaseModel):
    id: int
    submission_id: str
    title: str
    status: str
    total_rules: int
    passed: int
    failed: int
    warnings: int
    compliance_score: float | None = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class SubmissionDetailResponse(BaseModel):
    submission: SubmissionResponse
    evaluations: list[EvaluationResult]
    explanations: list[RuleExplanation]


class RuleExplanation(BaseModel):
    """Full explanation of what a rule checks and why it passed/failed."""

    rule_code: str
    rule_type: str
    target_entity: str
    target_field: str | None = None
    explanation: str | None = None
    result: str
    severity: str
    expected: dict[str, Any] | None = None
    actual: dict[str, Any] | None = None
    trace_steps: list[str] = []


class ComplianceDashboard(BaseModel):
    """High-level compliance dashboard data."""

    total_regulations: int
    total_requirements: int
    total_schemas: int
    active_schemas: int
    total_submissions: int
    pending_submissions: int
    average_score: float | None = None
    recent_submissions: list[SubmissionResponse] = []


class ApprovalCreate(BaseModel):
    decision: str = Field(
        ..., pattern="^(approved|rejected|needs_revision)$"
    )
    comment: str | None = None


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    submission_id: int
    decision: str
    comment: str | None = None
    created_at: datetime.datetime
