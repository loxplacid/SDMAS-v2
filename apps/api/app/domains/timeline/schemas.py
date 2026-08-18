"""Pydantic schemas for the Unified Operational Timeline.

Includes institutional-history query/response models for deterministic
timeline projections (TASK 18).
"""

from __future__ import annotations

import datetime
from typing import Any, Optional

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Existing timeline models (unchanged)
# ---------------------------------------------------------------------------


class TimelineItem(BaseModel):
    """A single normalized timeline event.

    Aggregated from existing persisted sources — audit logs, workflow
    approval history, notifications, payments, enrollments, admissions
    and risk findings. ``id`` is a composite ``{source}:{row_id}`` so
    events from different sources never collide.
    """

    id: str
    event_type: str
    timestamp: datetime.datetime
    actor: str
    entity: str
    description: str
    severity: str  # info | success | warning | critical
    source: str
    metadata: dict[str, Any] = {}
    deep_link: Optional[str] = None


class TimelineSourceInfo(BaseModel):
    """Per-source availability + count (drives filter chips in the UI)."""

    key: str
    label: str
    count: int = 0
    available: bool = True


class TimelineResponse(BaseModel):
    items: list[TimelineItem]
    total: int
    page: int
    page_size: int
    sources: list[TimelineSourceInfo]
    degraded: bool = False


# ---------------------------------------------------------------------------
# Institutional History (TASK 18)
# ---------------------------------------------------------------------------


class HistoryEvent(BaseModel):
    """A single deterministic history event.

    Projects a row from any canonical event source (outbox_events,
    audit_logs, case_events, system_exception_events, approval_history)
    into a uniform representation.  ``id`` is a composite
    ``{source}:{row_id}``; ``causation_id`` links to the event that
    triggered this one.
    """

    id: str
    source: str  # outbox | audit | case | exception | workflow | domain
    event_type: str
    timestamp: datetime.datetime
    actor: str
    entity: str
    description: str
    severity: str = "info"  # info | success | warning | critical
    causation_id: str | None = None
    correlation_id: str | None = None
    metadata: dict[str, Any] = {}


class HistoryProjection(BaseModel):
    """A deterministic timeline projection for a query.

    Contains a chronological list of history events and summary
    statistics computed from the data — no AI-generated narratives.
    """

    events: list[HistoryEvent]
    total: int
    summary: HistorySummary
    query_type: str
    query_params: dict[str, Any] = {}


class HistorySummary(BaseModel):
    """Deterministic summary statistics for a history projection."""

    total_events: int
    sources: dict[str, int]  # source -> count
    severity_distribution: dict[str, int]  # severity -> count
    actors: list[str]  # unique actors, most active first
    first_event_at: datetime.datetime | None = None
    last_event_at: datetime.datetime | None = None
    date_range_days: float | None = None


class CausalChain(BaseModel):
    """The causal chain leading to a specific event.

    Traces back through causation_id links to find the root cause
    event and all intermediate events in the chain.
    """

    target_event: HistoryEvent
    chain: list[HistoryEvent]  # root -> ... -> target (chronological)
    root_event: HistoryEvent
    depth: int  # number of links in the chain


class EntityHistory(BaseModel):
    """Complete history for a specific entity (student, class, teacher, etc.).

    Groups events by source and provides lifecycle milestones.
    """

    entity_type: str
    entity_id: int
    events: list[HistoryEvent]
    total: int
    lifecycle: list[LifecycleMilestone]
    summary: HistorySummary


class LifecycleMilestone(BaseModel):
    """A significant lifecycle transition extracted from the timeline."""

    event_id: str
    timestamp: datetime.datetime
    event_type: str
    from_state: str | None = None
    to_state: str | None = None
    actor: str
    description: str


class DateRangeDiff(BaseModel):
    """What changed between two dates.

    Deterministic projection of all events in a date range, grouped
    by source with count comparisons.
    """

    start: datetime.datetime
    end: datetime.datetime
    events: list[HistoryEvent]
    total: int
    summary: HistorySummary
    by_source: dict[str, list[HistoryEvent]]  # source -> events
    most_active_actor: str | None = None
    most_changed_entity: str | None = None
