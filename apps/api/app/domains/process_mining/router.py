"""Process Mining API — deterministic analysis of workflow processes.

GET /api/process-mining/analysis     — full process analysis
GET /api/process-mining/graph        — process discovery graph only
GET /api/process-mining/variants     — process variants only
GET /api/process-mining/bottlenecks  — bottleneck analysis only
GET /api/process-mining/rework       — rework detection only
GET /api/process-mining/sla          — SLA violations only
GET /api/process-mining/transitions  — transition frequency only

Security
--------
- Authenticated staff roles only (admin/principal).
- Every read is tenant-scoped to the caller's campus.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.dependencies import require_role
from app.domains.process_mining.service import ProcessMiningService
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.guards import effective_campus_id
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/api/process-mining", tags=["process-mining"])

_LEAD_ROLES = ("admin", "principal")


async def get_pm_service(
    session: AsyncSession = Depends(get_session),
) -> ProcessMiningService:
    return ProcessMiningService(session)


@router.get("/analysis")
async def full_analysis(
    source: Optional[str] = Query(
        None,
        description="Restrict to one source: workflow, case, exception",
    ),
    limit: int = Query(1000, ge=1, le=10000),
    tenant: TenantContext = Depends(require_tenant_context),
    svc: ProcessMiningService = Depends(get_pm_service),
    _user=Depends(require_role(*_LEAD_ROLES)),
):
    """Full process analysis combining all metrics."""
    campus_id = effective_campus_id(tenant, None)
    result = await svc.analyze(
        campus_id=campus_id, source=source, limit=limit
    )
    return result.model_dump()


@router.get("/graph")
async def process_graph(
    source: Optional[str] = Query(None),
    limit: int = Query(1000, ge=1, le=10000),
    tenant: TenantContext = Depends(require_tenant_context),
    svc: ProcessMiningService = Depends(get_pm_service),
    _user=Depends(require_role(*_LEAD_ROLES)),
):
    """Process discovery graph (nodes + edges) for visualization."""
    campus_id = effective_campus_id(tenant, None)
    result = await svc.analyze(
        campus_id=campus_id, source=source, limit=limit
    )
    return result.graph.model_dump()


@router.get("/variants")
async def process_variants(
    source: Optional[str] = Query(None),
    limit: int = Query(1000, ge=1, le=10000),
    tenant: TenantContext = Depends(require_tenant_context),
    svc: ProcessMiningService = Depends(get_pm_service),
    _user=Depends(require_role(*_LEAD_ROLES)),
):
    """Distinct execution paths (variants) through the process."""
    campus_id = effective_campus_id(tenant, None)
    result = await svc.analyze(
        campus_id=campus_id, source=source, limit=limit
    )
    return [v.model_dump() for v in result.variants]


@router.get("/bottlenecks")
async def bottleneck_analysis(
    source: Optional[str] = Query(None),
    limit: int = Query(1000, ge=1, le=10000),
    tenant: TenantContext = Depends(require_tenant_context),
    svc: ProcessMiningService = Depends(get_pm_service),
    _user=Depends(require_role(*_LEAD_ROLES)),
):
    """Steps with longest waiting times (bottlenecks)."""
    campus_id = effective_campus_id(tenant, None)
    result = await svc.analyze(
        campus_id=campus_id, source=source, limit=limit
    )
    return [b.model_dump() for b in result.bottlenecks]


@router.get("/rework")
async def rework_detection(
    source: Optional[str] = Query(None),
    limit: int = Query(1000, ge=1, le=10000),
    tenant: TenantContext = Depends(require_tenant_context),
    svc: ProcessMiningService = Depends(get_pm_service),
    _user=Depends(require_role(*_LEAD_ROLES)),
):
    """Detected rework loops in case lifecycles."""
    campus_id = effective_campus_id(tenant, None)
    result = await svc.analyze(
        campus_id=campus_id, source=source, limit=limit
    )
    return [r.model_dump() for r in result.rework]


@router.get("/sla")
async def sla_violations(
    source: Optional[str] = Query(None),
    limit: int = Query(1000, ge=1, le=10000),
    tenant: TenantContext = Depends(require_tenant_context),
    svc: ProcessMiningService = Depends(get_pm_service),
    _user=Depends(require_role(*_LEAD_ROLES)),
):
    """Cases that exceeded their SLA time limits."""
    campus_id = effective_campus_id(tenant, None)
    result = await svc.analyze(
        campus_id=campus_id, source=source, limit=limit
    )
    return [v.model_dump() for v in result.sla_violations]


@router.get("/transitions")
async def transition_frequency(
    source: Optional[str] = Query(None),
    limit: int = Query(1000, ge=1, le=10000),
    tenant: TenantContext = Depends(require_tenant_context),
    svc: ProcessMiningService = Depends(get_pm_service),
    _user=Depends(require_role(*_LEAD_ROLES)),
):
    """How often each state-to-state transition occurs."""
    campus_id = effective_campus_id(tenant, None)
    result = await svc.analyze(
        campus_id=campus_id, source=source, limit=limit
    )
    return [t.model_dump() for t in result.transitions]
