"""Pydantic schemas for the Data Quality Center."""

from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DataQualityFindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    check_code: str
    category: str
    severity: str
    entity_type: str
    entity_id: int
    student_id: Optional[int] = None
    field: str
    description: str
    evidence: Optional[dict] = None
    status: str
    detected_at: datetime.datetime
    last_verified_at: datetime.datetime
    resolved_at: Optional[datetime.datetime] = None
    resolved_by: Optional[int] = None
    resolved_reason: Optional[str] = None


class DataQualityFindingPage(BaseModel):
    items: list[DataQualityFindingOut]
    total: int
    page: int
    size: int
    pages: int


class DataQualityOverview(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    total: int = 0
    by_category: dict[str, int] = {}
    overall_quality: float = 100.0
    severity_weights: dict[str, float] = {}
    total_checks: int = 0


class DataQualityRecomputeResult(BaseModel):
    created: int
    updated: int
    resolved: int
    total_open: int
    run_at: str


class DataQualityResolveIn(BaseModel):
    reason: str
