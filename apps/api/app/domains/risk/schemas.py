"""Pydantic schemas for the Risk & Attention Engine."""

from __future__ import annotations

import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class RiskFindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    entity_type: str
    entity_id: int
    student_id: Optional[int] = None
    rule_code: str
    category: str
    severity: str
    score: float
    reason: str
    recommended_action: str
    evidence: Optional[dict] = None
    status: str
    detected_at: datetime.datetime
    last_verified_at: datetime.datetime
    resolved_at: Optional[datetime.datetime] = None
    resolved_by: Optional[int] = None
    resolved_reason: Optional[str] = None
    # P11 — linked operational case (null when none exists), so the Risk
    # Center can open the case instead of offering a duplicate create.
    case_id: Optional[int] = None
    case_number: Optional[str] = None
    case_status: Optional[str] = None


class RiskFindingPage(BaseModel):
    items: list[RiskFindingOut]
    total: int
    page: int
    size: int
    pages: int


class RiskOverview(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    total: int = 0
    by_category: dict[str, int] = {}


class RecomputeResult(BaseModel):
    created: int
    updated: int
    resolved: int
    total_open: int
    run_at: str


class RuleConfigOut(BaseModel):
    rule_code: str
    category: str
    name: str
    description: str
    entity_type: str
    enabled: bool
    thresholds: dict[str, Any]
    severity_overrides: Optional[dict] = None
    defaults: dict[str, Any]
    recommended_action: str


class RuleConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    thresholds: Optional[dict[str, Any]] = None
    severity_overrides: Optional[dict[str, Any]] = None


class RiskResolveIn(BaseModel):
    reason: str


class TeacherRiskFindingOut(BaseModel):
    """Risk finding enriched for a teacher's dashboard view."""

    id: int
    student_id: Optional[int] = None
    student_name: Optional[str] = None
    student_number: Optional[str] = None
    class_id: Optional[int] = None
    class_name: Optional[str] = None
    rule_code: str
    category: str
    severity: str
    score: float
    reason: str
    recommended_action: str
    detected_at: datetime.datetime
    evidence: Optional[dict] = None


class TeacherRiskSummary(BaseModel):
    total: int = 0
    by_severity: dict[str, int] = {
        "critical": 0, "high": 0, "medium": 0, "low": 0
    }
    findings: list[TeacherRiskFindingOut] = []
