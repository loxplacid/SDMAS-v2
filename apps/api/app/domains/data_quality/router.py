"""Data Quality Center API.

Endpoints
---------
- GET  /api/data-quality/overview   — severity/category counts + overall quality
- GET  /api/data-quality/findings   — paginated, filterable, RBAC-filtered
- GET  /api/data-quality/findings/{id} — single finding (deep-link, RBAC-filtered)
- POST /api/data-quality/run        — run checks and persist the snapshot
- POST /api/data-quality/findings/{id}/resolve — resolve with reason (audited)
- POST /api/data-quality/findings/{id}/ignore  — ignore with reason (audited)

Tenant isolation: every read/write is scoped to the caller's campus via
``get_school_context``.  RBAC: financial entity types (payments, fee dues)
are hidden from roles without ``fees.view``; writes (run/resolve/ignore)
are leadership-only.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.pagination import Page, PaginationParams
from app.domains.auth.dependencies import require_role
from app.domains.data_quality.schemas import (
    DataQualityFindingOut,
    DataQualityFindingPage,
    DataQualityOverview,
    DataQualityRecomputeResult,
    DataQualityResolveIn,
)
from app.domains.data_quality.service import DataQualityService
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import get_school_context
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/api/data-quality", tags=["data-quality"])


async def get_data_quality_service(
    session: AsyncSession = Depends(get_session),
) -> DataQualityService:
    return DataQualityService(session)


def _page(items, total: int, pagination: PaginationParams) -> DataQualityFindingPage:
    return Page.create(
        items=[DataQualityFindingOut.model_validate(i) for i in items],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.get("/overview", response_model=DataQualityOverview)
async def data_quality_overview(
    tenant: TenantContext = Depends(get_school_context),
    service: DataQualityService = Depends(get_data_quality_service),
    user=Depends(require_role("admin", "principal", "staff")),
) -> DataQualityOverview:
    return DataQualityOverview(
        **await service.get_overview(tenant.campus_id, role=user.role)
    )


@router.get("/findings", response_model=DataQualityFindingPage)
async def list_findings(
    pagination: PaginationParams = Depends(),
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    check_code: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    tenant: TenantContext = Depends(get_school_context),
    service: DataQualityService = Depends(get_data_quality_service),
    user=Depends(require_role("admin", "principal", "staff")),
) -> DataQualityFindingPage:
    items, total = await service.list_findings(
        tenant.campus_id,
        role=user.role,
        category=category,
        severity=severity,
        status=status_filter,
        check_code=check_code,
        entity_type=entity_type,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return _page(items, total, pagination)


@router.get("/findings/{finding_id}", response_model=DataQualityFindingOut)
async def get_finding(
    finding_id: int,
    tenant: TenantContext = Depends(get_school_context),
    service: DataQualityService = Depends(get_data_quality_service),
    user=Depends(require_role("admin", "principal", "staff")),
) -> DataQualityFindingOut:
    """Single finding, campus-scoped and RBAC-filtered — used for
    deep-linking from a case back to its originating finding so the
    Data Quality → case → finding loop never loses context.
    """
    try:
        f = await service.get_finding(finding_id, tenant.campus_id, role=user.role)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found"
        )
    return DataQualityFindingOut.model_validate(f)


@router.post("/run", response_model=DataQualityRecomputeResult)
async def run_checks(
    tenant: TenantContext = Depends(get_school_context),
    service: DataQualityService = Depends(get_data_quality_service),
    user=Depends(require_role("admin", "principal")),
) -> DataQualityRecomputeResult:
    result = await service.recompute(tenant.campus_id, actor_user_id=user.id)
    return DataQualityRecomputeResult(**result)


@router.post("/findings/{finding_id}/resolve", response_model=DataQualityFindingOut)
async def resolve_finding(
    finding_id: int,
    data: DataQualityResolveIn,
    tenant: TenantContext = Depends(get_school_context),
    service: DataQualityService = Depends(get_data_quality_service),
    user=Depends(require_role("admin", "principal")),
) -> DataQualityFindingOut:
    try:
        f = await service.resolve_finding(
            finding_id, tenant.campus_id, user.id, data.reason
        )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found"
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return DataQualityFindingOut.model_validate(f)


@router.post("/findings/{finding_id}/ignore", response_model=DataQualityFindingOut)
async def ignore_finding(
    finding_id: int,
    data: DataQualityResolveIn,
    tenant: TenantContext = Depends(get_school_context),
    service: DataQualityService = Depends(get_data_quality_service),
    user=Depends(require_role("admin", "principal")),
) -> DataQualityFindingOut:
    try:
        f = await service.ignore_finding(
            finding_id, tenant.campus_id, user.id, data.reason
        )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found"
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return DataQualityFindingOut.model_validate(f)
