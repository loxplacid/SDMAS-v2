"""Policy-as-code foundation — Pydantic schemas (API contract)."""

from __future__ import annotations

import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.platform.policy.models import (
    DECISIONS,
    EFFECTS,
    EXCEPTION_EFFECTS,
    POLICY_SCOPES,
    VERSION_STATUSES,
)

# ---------------------------------------------------------------------------
# Policy definitions
# ---------------------------------------------------------------------------


class PolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9._-]+$")
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    scope: str = Field(min_length=1, max_length=40)
    scope_ref: Optional[str] = Field(default=None, max_length=80)
    created_by: Optional[int] = None


class PolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    policy_id: str
    name: str
    description: Optional[str] = None
    scope: str
    scope_ref: Optional[str] = None
    status: str
    created_by: Optional[int] = None
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# Conditions / rules / exceptions (the JSON DSL)
# ---------------------------------------------------------------------------


class Condition(BaseModel):
    """A condition expression tree — ``{op, field?, value?, conditions?}``."""

    model_config = ConfigDict(extra="forbid")

    op: str = Field(min_length=1, max_length=16)
    field: Optional[str] = None
    value: Optional[Any] = None
    conditions: Optional[list["Condition"]] = None
    condition: Optional["Condition"] = None


class RuleDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9._-]+$")
    description: Optional[str] = Field(default=None, max_length=500)
    condition: Condition
    effect: str = Field(min_length=1, max_length=16)
    reason: Optional[str] = Field(default=None, max_length=500)


class ExceptionDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9._-]+$")
    description: Optional[str] = Field(default=None, max_length=500)
    condition: Condition
    effect: str = Field(default="allow", max_length=16)
    reason: Optional[str] = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Policy versions
# ---------------------------------------------------------------------------


class PolicyVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    rules: list[RuleDef] = Field(default_factory=list)
    exceptions: list[ExceptionDef] = Field(default_factory=list)
    applicability: Optional[Condition] = None
    effective_from: Optional[datetime.datetime] = None
    effective_until: Optional[datetime.datetime] = None
    created_by: Optional[int] = None


class PolicyVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    policy_def_id: int
    version: int
    title: str
    description: Optional[str] = None
    rules: Optional[dict[str, Any]] = None
    exceptions: Optional[dict[str, Any]] = None
    applicability: Optional[dict[str, Any]] = None
    status: str
    is_current: bool
    effective_from: Optional[datetime.datetime] = None
    effective_until: Optional[datetime.datetime] = None
    created_by: Optional[int] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime.datetime] = None
    approval_note: Optional[str] = None
    published_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


class EvaluateInput(BaseModel):
    """Input data for one policy evaluation."""

    model_config = ConfigDict(extra="forbid")

    subject_type: Optional[str] = Field(default=None, max_length=80)
    subject_id: Optional[str] = Field(default=None, max_length=200)
    data: dict[str, Any] = Field(default_factory=dict)
    evaluated_by: Optional[int] = None


class RuleOutcome(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rule_id: str
    satisfied: bool
    effect: str
    reason: Optional[str] = None


class ExceptionOutcome(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    exception_id: str
    satisfied: bool
    effect: str
    reason: Optional[str] = None


class EvaluationResult(BaseModel):
    """The explainable evaluation outcome."""

    decision: str
    reason: str
    policy_id: str
    version: int
    applicable: bool
    rule_results: list[RuleOutcome]
    exceptions_applied: list[ExceptionOutcome]
    evaluated_at: datetime.datetime


class EvaluationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    policy_id: str
    policy_def_id: Optional[int] = None
    policy_version_id: Optional[int] = None
    version: Optional[int] = None
    subject_type: Optional[str] = None
    subject_id: Optional[str] = None
    decision: str
    reason: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    input_snapshot: Optional[dict[str, Any]] = None
    evaluated_by: Optional[int] = None
    evaluated_at: datetime.datetime


class PublishVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: Optional[str] = Field(default=None, max_length=1000)
    effective_from: Optional[datetime.datetime] = None
    approved_by: Optional[int] = None


__all__ = [
    "PolicyCreate",
    "PolicyRead",
    "Condition",
    "RuleDef",
    "ExceptionDef",
    "PolicyVersionCreate",
    "PolicyVersionRead",
    "EvaluateInput",
    "RuleOutcome",
    "ExceptionOutcome",
    "EvaluationResult",
    "EvaluationRead",
    "PublishVersion",
    "POLICY_SCOPES",
    "EFFECTS",
    "EXCEPTION_EFFECTS",
    "DECISIONS",
    "VERSION_STATUSES",
]
