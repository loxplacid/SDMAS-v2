"""Unified Operational Timeline API.

GET /api/timeline — aggregated operational events across the school
(with optional entity scoping for the 360 views).

Security
--------
- Authenticated staff roles only (admin/principal/accountant/staff/teacher).
- Every read is tenant-scoped to the caller's campus via ``get_school_context``.
- Financial/admissions/approval events are RBAC-filtered in the service.
"""

from __future__ import annotations

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.dependencies import require_role
from app.domains.timeline.schemas import TimelineResponse
from app.domains.timeline.service import TimelineFilters, TimelineService
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.guards import effective_campus_id
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/api/timeline", tags=["timeline"])


async def get_timeline_service(
    session: AsyncSession = Depends(get_session),
) -> TimelineService:
    return TimelineService(session)


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


@router.get("", response_model=TimelineResponse)
async def get_timeline(
    entity_type: str = Query("school", pattern="^(school|student|class|teacher)$"),
    entity_id: Optional[int] = Query(None),
    source: Optional[str] = Query(
        None,
        description="Restrict to one source: audit, workflow, notification, fees, academic, admissions, risk",
    ),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    actor: Optional[str] = Query(None, description="Filter by actor name"),
    start: Optional[str] = Query(None, description="ISO start datetime (UTC)"),
    end: Optional[str] = Query(None, description="ISO end datetime (UTC)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant: TenantContext = Depends(require_tenant_context),
    service: TimelineService = Depends(get_timeline_service),
    user=Depends(require_role("admin", "principal", "accountant", "staff", "teacher")),
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
