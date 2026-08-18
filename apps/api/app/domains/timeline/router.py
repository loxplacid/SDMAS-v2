"""Unified Operational Timeline + Institutional Memory API.

GET /api/timeline              — aggregated operational events across the school
GET /api/timeline/history      — what happened to a specific entity (TASK 18)
GET /api/timeline/campus       — what changed in this campus (TASK 18)
GET /api/timeline/pre-exception — what happened before this exception (TASK 18)
GET /api/timeline/causal-chain — which events caused this workflow (TASK 18)
GET /api/timeline/date-range   — what changed between two dates (TASK 18)

Security
--------
- Authenticated staff roles only (admin/principal/accountant/staff/teacher).
- Every read is tenant-scoped to the caller's campus via ``get_school_context``.
- Financial/admissions/approval events are RBAC-filtered in the service.
"""

from __future__ import annotations

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.dependencies import require_role
from app.domains.timeline.history import InstitutionalHistoryService
from app.domains.timeline.schemas import (
    CausalChain,
    DateRangeDiff,
    EntityHistory,
    HistoryProjection,
    TimelineResponse,
)
from app.domains.timeline.service import TimelineFilters, TimelineService
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.guards import effective_campus_id
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/api/timeline", tags=["timeline"])

_STAFF_ROLES = ("admin", "principal", "accountant", "staff", "teacher")


async def get_timeline_service(
    session: AsyncSession = Depends(get_session),
) -> TimelineService:
    return TimelineService(session)


async def get_history_service(
    session: AsyncSession = Depends(get_session),
) -> InstitutionalHistoryService:
    return InstitutionalHistoryService(session)


def _parse_datetime(value: Optional[str]) -> Optional[datetime.datetime]:
    if not value:
        return None
    try:
        # Accept ISO date or datetime strings (UTC assumed).
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime.timezone.utc)
        return parsed
    except ValueError:
        return None


# ======================================================================
# Existing timeline endpoint
# ======================================================================


@router.get("", response_model=TimelineResponse)
async def get_timeline(
    entity_type: str = Query("school", pattern="^(school|student|class|teacher)$"),
    entity_id: Optional[int] = Query(None),
    source: Optional[str] = Query(
        None,
        description="Restrict to one source: audit, workflow, fees, academic, etc.",
    ),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    actor: Optional[str] = Query(None, description="Filter by actor name"),
    start: Optional[str] = Query(None, description="ISO start datetime (UTC)"),
    end: Optional[str] = Query(None, description="ISO end datetime (UTC)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant: TenantContext = Depends(require_tenant_context),
    service: TimelineService = Depends(get_timeline_service),
    user=Depends(require_role(*_STAFF_ROLES)),
) -> TimelineResponse:
    """Aggregated operational timeline for the caller's school.

    ``entity_type`` + ``entity_id`` scope the feed to a single student /
    class / teacher (used by the 360 views). ``source`` filters to one
    domain. Sources degrade independently — a failing source reports
    ``available=False`` while the rest of the timeline still renders.
    """
    filters = TimelineFilters(
        entity_type=entity_type,
        entity_id=entity_id,
        source=source,
        event_type=event_type,
        actor=actor,
        start=_parse_datetime(start),
        end=_parse_datetime(end),
        page=page,
        page_size=page_size,
    )
    campus_id = effective_campus_id(tenant, None)
    return await service.get_timeline(
        role=user.role,
        user_id=user.id,
        campus_id=campus_id,
        filters=filters,
    )


# ======================================================================
# TASK 18 — Institutional Memory endpoints
# ======================================================================


@router.get("/history", response_model=EntityHistory)
async def entity_history(
    entity_type: str = Query(
        ...,
        pattern="^(student|class|teacher|admission|payment|enrollment|workflow)$",
    ),
    entity_id: int = Query(..., ge=1),
    limit: int = Query(100, ge=1, le=500),
    tenant: TenantContext = Depends(require_tenant_context),
    svc: InstitutionalHistoryService = Depends(get_history_service),
    _user=Depends(require_role(*_STAFF_ROLES)),
) -> EntityHistory:
    """Complete history for a specific entity.

    Aggregates events from all canonical sources (audit, outbox, cases,
    exceptions, workflow) that reference the entity.  Returns a
    chronological timeline with lifecycle milestones.
    """
    campus_id = effective_campus_id(tenant, None)
    return await svc.entity_history(
        campus_id=campus_id,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
    )


@router.get("/campus", response_model=HistoryProjection)
async def campus_history(
    source: Optional[str] = Query(
        None,
        description="Restrict to one source: outbox, audit, case, exception, workflow",
    ),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    tenant: TenantContext = Depends(require_tenant_context),
    svc: InstitutionalHistoryService = Depends(get_history_service),
    _user=Depends(require_role(*_STAFF_ROLES)),
) -> HistoryProjection:
    """All events for the caller's campus.

    Optionally filtered by source.  Returns a reverse-chronological
    projection with deterministic summary statistics.
    """
    campus_id = effective_campus_id(tenant, None)
    if campus_id is None:
        raise HTTPException(status_code=422, detail="Campus context required")
    return await svc.campus_history(
        campus_id=campus_id,
        source=source,
        limit=limit,
        offset=offset,
    )


@router.get("/pre-exception", response_model=HistoryProjection)
async def pre_exception_timeline(
    exception_id: int = Query(..., ge=1),
    limit: int = Query(50, ge=1, le=200),
    tenant: TenantContext = Depends(require_tenant_context),
    svc: InstitutionalHistoryService = Depends(get_history_service),
    _user=Depends(require_role(*_STAFF_ROLES)),
) -> HistoryProjection:
    """Events that occurred before a specific exception.

    Finds the exception's ``detected_at`` timestamp and returns all
    events from the same entity (or campus) that happened before it.
    """
    campus_id = effective_campus_id(tenant, None)
    return await svc.pre_exception_timeline(
        campus_id=campus_id,
        exception_id=exception_id,
        limit=limit,
    )


@router.get("/causal-chain", response_model=CausalChain)
async def causal_chain(
    event_id: str = Query(..., min_length=1, max_length=128),
    max_depth: int = Query(20, ge=1, le=50),
    tenant: TenantContext = Depends(require_tenant_context),
    svc: InstitutionalHistoryService = Depends(get_history_service),
    _user=Depends(require_role(*_STAFF_ROLES)),
) -> CausalChain:
    """Trace the causal chain leading to an event.

    Follows ``causation_id`` links backwards from the target event to
    find the root cause and all intermediate events.  Useful for
    understanding *why* a workflow was triggered.
    """
    campus_id = effective_campus_id(tenant, None)
    result = await svc.causal_chain(
        campus_id=campus_id,
        event_id=event_id,
        max_depth=max_depth,
    )
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Event '{event_id}' not found or has no causal chain",
        )
    return result


@router.get("/date-range", response_model=DateRangeDiff)
async def date_range_diff(
    start: str = Query(..., description="ISO start datetime (UTC)"),
    end: str = Query(..., description="ISO end datetime (UTC)"),
    source: Optional[str] = Query(
        None,
        description="Restrict to one source: outbox, audit, case, exception, workflow",
    ),
    limit: int = Query(200, ge=1, le=1000),
    tenant: TenantContext = Depends(require_tenant_context),
    svc: InstitutionalHistoryService = Depends(get_history_service),
    _user=Depends(require_role(*_STAFF_ROLES)),
) -> DateRangeDiff:
    """What changed between two dates.

    Deterministic projection of all events in a date range, grouped
    by source with summary statistics.
    """
    campus_id = effective_campus_id(tenant, None)
    start_dt = _parse_datetime(start)
    end_dt = _parse_datetime(end)
    if start_dt is None or end_dt is None:
        raise HTTPException(status_code=422, detail="Invalid datetime format")
    if start_dt >= end_dt:
        raise HTTPException(status_code=422, detail="start must be before end")
    return await svc.date_range_diff(
        campus_id=campus_id,
        start=start_dt,
        end=end_dt,
        source=source,
        limit=limit,
    )
