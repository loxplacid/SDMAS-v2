"""Risk & Attention Engine API.

Endpoints
---------
- GET  /api/risk/overview         — counts by severity / category (open)
- GET  /api/risk/findings         — paginated, filterable, RBAC-filtered
- GET  /api/risk/findings/{id}     — single finding (deep-link, RBAC-filtered)
- POST /api/risk/recompute        — run rules and persist snapshot
- GET  /api/risk/config           — rule configuration (admin/principal)
- PUT  /api/risk/config/{code}    — update a rule config (admin only)
- POST /api/risk/findings/{id}/resolve      — resolve with reason (audited)
- POST /api/risk/findings/{id}/acknowledge  — acknowledge (audited)

Tenant isolation: every read/write is scoped to the caller's campus via
``get_school_context``. Unscoped platform admins may pass ``campus_id``.
RBAC: financial-category findings are hidden from roles without
``fees.view``; admissions findings are leadership-only.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.pagination import Page, PaginationParams
from app.domains.auth.dependencies import get_current_user, require_role
from app.domains.risk.schemas import (
    RecomputeResult,
    RiskFindingOut,
    RiskFindingPage,
    RiskOverview,
    RiskResolveIn,
    RuleConfigOut,
    RuleConfigUpdate,
    TeacherRiskSummary,
)
from app.domains.risk.service import RiskService
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import get_school_context
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/api/risk", tags=["risk"])


async def get_risk_service(
    session: AsyncSession = Depends(get_session),
) -> RiskService:
    return RiskService(session)


def _page(
    items,
    total: int,
    pagination: PaginationParams,
    linked: Optional[dict[int, dict]] = None,
) -> RiskFindingPage:
    data = []
    for i in items:
        out = RiskFindingOut.model_validate(i)
        if linked:
            info = linked.get(i.id, {})
            out.case_id = info.get("case_id")
            out.case_number = info.get("case_number")
            out.case_status = info.get("case_status")
        data.append(out)
    return Page.create(
        items=data,
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.get("/overview", response_model=RiskOverview)
async def risk_overview(
    tenant: TenantContext = Depends(get_school_context),
    service: RiskService = Depends(get_risk_service),
    user=Depends(require_role("admin", "principal", "staff")),
) -> RiskOverview:
    return RiskOverview(**await service.get_overview(tenant.campus_id, role=user.role))


@router.get("/teacher-findings", response_model=TeacherRiskSummary)
async def teacher_findings(
    teacher_id: int = Query(..., description="Teacher whose students' risks to show"),
    tenant: TenantContext = Depends(get_school_context),
    service: RiskService = Depends(get_risk_service),
    user=Depends(require_role("admin", "principal", "staff", "teacher")),
) -> TeacherRiskSummary:
    """Open risk findings for the students a teacher teaches.

    Teachers are intentionally included here so class teachers can see
    attendance/academic/documents/operational risks for their students —
    finance and admissions findings are filtered out for them by role.
    A teacher-role caller may only read their own students' risks.
    """
    if user.role == "teacher":
        own_id = await service.resolve_teacher_id_for_user(
            getattr(user, "email", None),
            getattr(user, "display_name", None),
        )
        if own_id is None or own_id != teacher_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Teachers can only view risk findings for their own classes",
            )
    data = await service.get_teacher_risk_summary(
        teacher_id, tenant.campus_id, role=user.role
    )
    return TeacherRiskSummary(**data)


@router.get("/findings", response_model=RiskFindingPage)
async def list_findings(
    pagination: PaginationParams = Depends(),
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    rule_code: Optional[str] = Query(None),
    tenant: TenantContext = Depends(get_school_context),
    service: RiskService = Depends(get_risk_service),
    user=Depends(require_role("admin", "principal", "staff")),
) -> RiskFindingPage:
    items, total = await service.list_findings(
        tenant.campus_id,
        role=user.role,
        category=category,
        severity=severity,
        status=status_filter,
        rule_code=rule_code,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    # P11 — attach the linked case (if any) so the Risk Center can open it.
    linked = {}
    if items:
        linked = await service.linked_cases_for_findings(
            tenant.campus_id, [i.id for i in items]
        )
    return _page(items, total, pagination, linked)


@router.get("/findings/{finding_id}", response_model=RiskFindingOut)
async def get_finding(
    finding_id: int,
    tenant: TenantContext = Depends(get_school_context),
    service: RiskService = Depends(get_risk_service),
    user=Depends(require_role("admin", "principal", "staff")),
) -> RiskFindingOut:
    """Single finding, campus-scoped and RBAC-filtered — used for
    deep-linking from a case back to its originating finding so the
    Risk Center → finding → case → finding loop never loses context.
    """
    try:
        f = await service.get_finding(finding_id, tenant.campus_id, role=user.role)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found"
        )
    out = RiskFindingOut.model_validate(f)
    linked = await service.linked_cases_for_findings(tenant.campus_id, [f.id])
    info = linked.get(f.id, {})
    out.case_id = info.get("case_id")
    out.case_number = info.get("case_number")
    out.case_status = info.get("case_status")
    return out


@router.post("/recompute", response_model=RecomputeResult)
async def recompute(
    tenant: TenantContext = Depends(get_school_context),
    service: RiskService = Depends(get_risk_service),
    user=Depends(require_role("admin", "principal")),
) -> RecomputeResult:
    result = await service.recompute(tenant.campus_id, actor_user_id=user.id)
    return RecomputeResult(**result)


@router.get("/config", response_model=list[RuleConfigOut])
async def get_config(
    tenant: TenantContext = Depends(get_school_context),
    service: RiskService = Depends(get_risk_service),
    _user=Depends(require_role("admin", "principal")),
) -> list[RuleConfigOut]:
    return [RuleConfigOut(**c) for c in await service.get_config(tenant.campus_id)]


@router.put("/config/{rule_code}", response_model=RuleConfigOut)
async def update_config(
    rule_code: str,
    data: RuleConfigUpdate,
    tenant: TenantContext = Depends(get_school_context),
    service: RiskService = Depends(get_risk_service),
    user=Depends(require_role("admin")),
) -> RuleConfigOut:
    result = await service.update_config(
        tenant.campus_id,
        rule_code,
        enabled=data.enabled,
        thresholds=data.thresholds,
        severity_overrides=data.severity_overrides,
        actor_user_id=user.id,
    )
    # Return the merged, effective config for this rule.
    configs = {c["rule_code"]: c for c in await service.get_config(tenant.campus_id)}
    return RuleConfigOut(**configs[rule_code])


@router.post("/findings/{finding_id}/resolve", response_model=RiskFindingOut)
async def resolve_finding(
    finding_id: int,
    data: RiskResolveIn,
    tenant: TenantContext = Depends(get_school_context),
    service: RiskService = Depends(get_risk_service),
    user=Depends(require_role("admin", "principal")),
) -> RiskFindingOut:
    try:
        f = await service.resolve_finding(
            finding_id, tenant.campus_id, user.id, data.reason
        )
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return RiskFindingOut.model_validate(f)


@router.post("/findings/{finding_id}/acknowledge", response_model=RiskFindingOut)
async def acknowledge_finding(
    finding_id: int,
    tenant: TenantContext = Depends(get_school_context),
    service: RiskService = Depends(get_risk_service),
    user=Depends(require_role("admin", "principal", "staff")),
) -> RiskFindingOut:
    try:
        f = await service.acknowledge_finding(
            finding_id, tenant.campus_id, user.id
        )
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return RiskFindingOut.model_validate(f)
