"""Pydantic response models for the School Command Center.

Every section carries an ``available`` flag so the frontend can render
graceful partial failure: if one data source errors, the rest of the
command center still renders.
"""

from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel


class Metric(BaseModel):
    """A single school-health metric with an optional trend delta."""

    key: str
    label: str
    value: float
    display: str  # pre-formatted display value ("1,240", "87.5%", "₹12.4L")
    status: str = "neutral"  # good | warn | critical | neutral
    drill_down: Optional[str] = None  # frontend route
    trend: Optional[float] = None  # delta vs previous period, if known


class TrendPoint(BaseModel):
    label: str  # e.g. "2026-07-01" or "2026-07"
    value: float


class SchoolHealth(BaseModel):
    available: bool = True
    metrics: list[Metric] = []
    trends: dict[str, list[TrendPoint]] = {}  # e.g. {"attendance": [...], "collection": [...]}


class Alert(BaseModel):
    """A deterministic, actionable alert on the command center."""

    id: str
    severity: str  # critical | warning | info
    category: str  # attendance | fees | admissions | approvals | documents | rollover | jobs
    title: str
    message: str
    count: Optional[int] = None
    action_label: str = "View"
    drill_down: Optional[str] = None


class NeedsAttention(BaseModel):
    available: bool = True
    alerts: list[Alert] = []


class TodayEvent(BaseModel):
    """A single operational event that happened today."""

    id: str
    type: str  # attendance | payment | admission | approval | leave | announcement
    title: str
    description: str
    time: Optional[str] = None
    drill_down: Optional[str] = None


class TodaySection(BaseModel):
    available: bool = True
    events: list[TodayEvent] = []


class QuickAction(BaseModel):
    id: str
    label: str
    description: str
    route: str
    icon: str  # icon key the frontend maps to an SVG path


class CommandCenterOverview(BaseModel):
    generated_at: datetime.datetime
    role: str
    campus_id: Optional[int] = None
    academic_year: Optional[str] = None
    sections: dict[str, bool] = {}  # per-section availability flags
    school_health: SchoolHealth = SchoolHealth()
    needs_attention: NeedsAttention = NeedsAttention()
    today: TodaySection = TodaySection()
    quick_actions: list[QuickAction] = []
