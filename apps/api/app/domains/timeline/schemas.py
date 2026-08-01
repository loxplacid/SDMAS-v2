"""Pydantic schemas for the Unified Operational Timeline."""

from __future__ import annotations

import datetime
from typing import Any, Optional

from pydantic import BaseModel


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
