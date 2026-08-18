"""Pydantic schemas for the process mining domain.

All response models are designed for frontend visualization — they carry
deterministic statistics, graph data (nodes + edges for process maps),
and tabular data for dashboards.
"""

from __future__ import annotations

import datetime

from pydantic import BaseModel

# ---------------------------------------------------------------------------


class Activity(BaseModel):
    """A discovered activity (step) in the process."""

    name: str
    count: int
    first_seen: datetime.datetime | None = None
    last_seen: datetime.datetime | None = None


class Transition(BaseModel):
    """A directed edge in the process graph."""

    from_activity: str
    to_activity: str
    count: int
    percentage: float = 0.0
    avg_duration_seconds: float | None = None


class ProcessGraph(BaseModel):
    """Directed graph suitable for frontend process-map visualization.

    Nodes are activities; edges are transitions with frequency weights.
    """

    nodes: list[Activity]
    edges: list[Transition]
    total_cases: int
    total_events: int


class CaseTrace(BaseModel):
    """A single case's execution trace."""

    case_id: str
    entity_type: str
    entity_id: int
    started_at: datetime.datetime
    ended_at: datetime.datetime | None = None
    duration_seconds: float | None = None
    events: list[CaseEvent]
    variant: str
    status: str  # completed | active | stuck


class CaseEvent(BaseModel):
    """A single event within a case trace."""

    activity: str
    timestamp: datetime.datetime
    actor: str | None = None
    duration_from_previous_seconds: float | None = None


class ProcessVariant(BaseModel):
    """A distinct execution path through the process."""

    variant_id: int
    path: str  # e.g. "A -> B -> C -> D"
    path_list: list[str]
    count: int
    percentage: float
    avg_duration_seconds: float | None = None
    min_duration_seconds: float | None = None
    max_duration_seconds: float | None = None


class Bottleneck(BaseModel):
    """A step with disproportionately long waiting time."""

    activity: str
    avg_wait_seconds: float
    median_wait_seconds: float
    p90_wait_seconds: float
    max_wait_seconds: float
    case_count: int
    severity: str  # critical | warning | info


class ReworkInstance(BaseModel):
    """A detected rework loop in a specific case."""

    case_id: str
    entity_type: str
    entity_id: int
    rework_activity: str
    occurrences: int
    first_occurrence: datetime.datetime
    last_occurrence: datetime.datetime


class SLAViolation(BaseModel):
    """A case that exceeded its time limit."""

    case_id: str
    entity_type: str
    entity_id: int
    started_at: datetime.datetime
    duration_seconds: float
    sla_limit_seconds: float
    overshoot_seconds: float
    status: str
    current_activity: str


class TransitionFrequency(BaseModel):
    """How often each transition occurs across all cases."""

    transition: str  # "from -> to"
    count: int
    percentage: float
    avg_duration_seconds: float | None = None


class ProcessSummary(BaseModel):
    """High-level process mining summary for a dashboard."""

    total_cases: int
    total_events: int
    unique_activities: int
    unique_variants: int
    avg_cycle_time_seconds: float | None = None
    median_cycle_time_seconds: float | None = None
    p90_cycle_time_seconds: float | None = None
    completion_rate: float = 0.0  # fraction of cases that reached a terminal state
    rework_rate: float = 0.0  # fraction of cases with rework
    sla_violation_rate: float = 0.0
    bottleneck_count: int = 0
    most_common_variant: str | None = None


class ProcessAnalysisResponse(BaseModel):
    """Full process analysis response combining all metrics."""

    summary: ProcessSummary
    graph: ProcessGraph
    variants: list[ProcessVariant]
    bottlenecks: list[Bottleneck]
    transitions: list[TransitionFrequency]
    rework: list[ReworkInstance]
    sla_violations: list[SLAViolation]
    cases: list[CaseTrace]
