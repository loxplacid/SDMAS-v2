"""Operational Case Management — API.

Endpoints
---------
- GET  /api/cases                — paginated, filterable work queue
- GET  /api/cases/overview       — count chips for the queue views
- GET  /api/cases/metrics        — operations workflow metrics
- GET  /api/cases/workload       — open-case workload per assignee
- GET  /api/cases/assignable     — users the actor may assign to
- POST /api/cases                — create (manual or from a P7 finding)
- GET  /api/cases/{id}           — detail with events/comments/evidence
- POST /api/cases/{id}/transition
- POST /api/cases/{id}/assign
- POST /api/cases/{id}/priority
- POST /api/cases/{id}/due-date
- POST /api/cases/{id}/comment
- POST /api/cases/{id}/evidence
- POST /api/cases/bulk/assign | bulk/priority | bulk/status | bulk/due-date
- POST /api/cases/escalate       — run deterministic escalation (leadership)

Tenant isolation: every read/write is scoped to the caller's campus via
``get_school_context``.  RBAC: staff may view and comment; reassign,
priority changes, resolution and escalation require admin/principal.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.pagination import Page, PaginationParams
from app.domains.auth.dependencies import require_role
from app.domains.cases.schemas import (
    AssignableUser,
    BulkAssignIn,
    BulkDueDateIn,
    BulkPriorityIn,
    BulkResult,
    BulkStatusIn,
    CaseAssignIn,
    CaseCommentIn,
    CaseCommentOut,
    CaseCreateIn,
    CaseDetailOut,
    CaseDueDateIn,
    CaseEventOut,
    CaseEvidenceIn,
    CaseEvidenceOut,
    CaseMetrics,
    CaseOut,
    CaseOverview,
    CasePage,
    CasePriorityIn,
    CaseTransitionIn,
    EscalationResult,
    WorkloadItem,
)
from app.domains.cases.service import CaseService
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import get_school_context
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/api/cases", tags=["cases"])

_CASE_ROLES = ("admin", "principal", "staff")
_LEAD_ROLES = ("admin", "principal")


async def get_case_service(
    session: AsyncSession = Depends(get_session),
) -> CaseService:
    return CaseService(session)


def _out(case, **extra) -> CaseOut:
    data = CaseOut.model_validate(case)
    for k, v in extra.items():
        setattr(data, k, v)
    return data


@router.get("", response_model=CasePage)
async def list_cases(
    pagination: PaginationParams = Depends(),
    view: str = Query("all", pattern="^(all|my|unassigned|open|overdue|due_soon|resolved)$"),
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = Query(None),
    case_type: Optional[str] = Query(None),
    assignee_id: Optional[int] = Query(None),
    source_type: Optional[str] = Query(None),
    student_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    sort: str = Query("updated", pattern="^(priority|due|created|updated)$"),
    tenant: TenantContext = Depends(get_school_context),
    service: CaseService = Depends(get_case_service),
    user=Depends(require_role(*_CASE_ROLES)),
) -> CasePage:
    items, total = await service.list_cases(
        tenant.campus_id,
        view=view,
        user_id=user.id,
        status=status_filter,
        priority=priority,
        case_type=case_type,
        assignee_id=assignee_id,
        source_type=source_type,
        student_id=student_id,
        search=search,
        sort=sort,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    rows = [_out(c, sla_state=service.sla_state(c, now)) for c in items]
    return Page.create(items=rows, total=total, page=pagination.page, size=pagination.size)


@router.get("/overview", response_model=CaseOverview)
async def case_overview(
    tenant: TenantContext = Depends(get_school_context),
    service: CaseService = Depends(get_case_service),
    user=Depends(require_role(*_CASE_ROLES)),
) -> CaseOverview:
    return CaseOverview(**await service.get_overview(tenant.campus_id, user.id))


@router.get("/metrics", response_model=CaseMetrics)
async def case_metrics(
    tenant: TenantContext = Depends(get_school_context),
    service: CaseService = Depends(get_case_service),
    user=Depends(require_role(*_CASE_ROLES)),
) -> CaseMetrics:
    return CaseMetrics(**await service.get_metrics(tenant.campus_id))


@router.get("/workload", response_model=list[WorkloadItem])
async def case_workload(
    tenant: TenantContext = Depends(get_school_context),
    service: CaseService = Depends(get_case_service),
    user=Depends(require_role(*_CASE_ROLES)),
) -> list[WorkloadItem]:
    return [WorkloadItem(**w) for w in await service.get_workload(tenant.campus_id)]


@router.get("/assignable", response_model=list[AssignableUser])
async def case_assignable(
    tenant: TenantContext = Depends(get_school_context),
    service: CaseService = Depends(get_case_service),
    user=Depends(require_role(*_CASE_ROLES)),
) -> list[AssignableUser]:
    return [
        AssignableUser(**u)
        for u in await service.list_assignable_users(tenant.campus_id, user.role)
    ]


@router.post("", response_model=CaseOut, status_code=status.HTTP_201_CREATED)
async def create_case(
    data: CaseCreateIn,
    tenant: TenantContext = Depends(get_school_context),
    service: CaseService = Depends(get_case_service),
    user=Depends(require_role(*_CASE_ROLES)),
) -> CaseOut:
    try:
        case = await service.create_case(
            campus_id=tenant.campus_id,
            actor_user_id=user.id,
            actor_name=user.display_name,
            title=data.title,
            description=data.description,
            case_type=data.case_type,
            priority=data.priority,
            source_type=data.source_type,
            source_id=data.source_id,
            student_id=data.student_id,
            assigned_to=data.assigned_to,
            due_at=data.due_at,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return _out(case, sla_state=service.sla_state(case))


@router.get("/{case_id}", response_model=CaseDetailOut)
async def case_detail(
    case_id: int,
    tenant: TenantContext = Depends(get_school_context),
    service: CaseService = Depends(get_case_service),
    user=Depends(require_role(*_CASE_ROLES)),
) -> CaseDetailOut:
    try:
        detail = await service.get_case_detail(case_id, tenant.campus_id)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    case = detail["case"]
    return CaseDetailOut(
        case=_out(case, sla_state=detail["sla_state"], assignee_name=detail["assignee_name"]),
        events=[CaseEventOut.model_validate(e) for e in detail["events"]],
        comments=[CaseCommentOut.model_validate(c) for c in detail["comments"]],
        evidence=[CaseEvidenceOut.model_validate(e) for e in detail["evidence"]],
    )


@router.post("/{case_id}/transition", response_model=CaseOut)
async def transition_case(
    case_id: int,
    data: CaseTransitionIn,
    tenant: TenantContext = Depends(get_school_context),
    service: CaseService = Depends(get_case_service),
    user=Depends(require_role(*_CASE_ROLES)),
) -> CaseOut:
    try:
        case = await service.transition_status(
            case_id, tenant.campus_id, user.id, user.display_name,
            data.status, data.reason, data.version,
        )
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return _out(case, sla_state=service.sla_state(case))


@router.post("/{case_id}/assign", response_model=CaseOut)
async def assign_case(
    case_id: int,
    data: CaseAssignIn,
    tenant: TenantContext = Depends(get_school_context),
    service: CaseService = Depends(get_case_service),
    user=Depends(require_role(*_CASE_ROLES)),
) -> CaseOut:
    try:
        case = await service.assign_case(
            case_id, tenant.campus_id, user.id, user.display_name,
            data.assignee_id, data.reason, data.version,
        )
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return _out(case, sla_state=service.sla_state(case))


@router.post("/{case_id}/priority", response_model=CaseOut)
async def change_priority(
    case_id: int,
    data: CasePriorityIn,
    tenant: TenantContext = Depends(get_school_context),
    service: CaseService = Depends(get_case_service),
    user=Depends(require_role(*_LEAD_ROLES)),
) -> CaseOut:
    try:
        case = await service.change_priority(
            case_id, tenant.campus_id, user.id, user.display_name,
            data.priority, data.reason, data.version,
        )
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return _out(case, sla_state=service.sla_state(case))


@router.post("/{case_id}/due-date", response_model=CaseOut)
async def set_due_date(
    case_id: int,
    data: CaseDueDateIn,
    tenant: TenantContext = Depends(get_school_context),
    service: CaseService = Depends(get_case_service),
    user=Depends(require_role(*_LEAD_ROLES)),
) -> CaseOut:
    try:
        case = await service.set_due_date(
            case_id, tenant.campus_id, user.id, user.display_name,
            data.due_at, data.reason, data.version,
        )
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return _out(case, sla_state=service.sla_state(case))


@router.post("/{case_id}/comment", response_model=CaseCommentOut)
async def add_comment(
    case_id: int,
    data: CaseCommentIn,
    tenant: TenantContext = Depends(get_school_context),
    service: CaseService = Depends(get_case_service),
    user=Depends(require_role(*_CASE_ROLES)),
) -> CaseCommentOut:
    try:
        comment = await service.add_comment(
            case_id, tenant.campus_id, user.id, user.display_name, data.body
        )
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return CaseCommentOut.model_validate(comment)


@router.post("/{case_id}/evidence", response_model=CaseEvidenceOut)
async def add_evidence(
    case_id: int,
    data: CaseEvidenceIn,
    tenant: TenantContext = Depends(get_school_context),
    service: CaseService = Depends(get_case_service),
    user=Depends(require_role(*_CASE_ROLES)),
) -> CaseEvidenceOut:
    try:
        evidence = await service.add_evidence(
            case_id, tenant.campus_id, user.id, user.display_name,
            kind=data.kind, title=data.title, summary=data.summary,
            reference_type=data.reference_type, reference_id=data.reference_id,
            metadata=data.metadata,
        )
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return CaseEvidenceOut.model_validate(evidence)


# ---------------------------------------------------------------------------
# Bulk operations (leadership)
# ---------------------------------------------------------------------------


@router.post("/bulk/assign", response_model=BulkResult)
async def bulk_assign(
    data: BulkAssignIn,
    tenant: TenantContext = Depends(get_school_context),
    service: CaseService = Depends(get_case_service),
    user=Depends(require_role(*_LEAD_ROLES)),
) -> BulkResult:
    return BulkResult(
        **await service.bulk_assign(
            tenant.campus_id, user.id, user.display_name, data.case_ids, data.assignee_id
        )
    )


@router.post("/bulk/priority", response_model=BulkResult)
async def bulk_priority(
    data: BulkPriorityIn,
    tenant: TenantContext = Depends(get_school_context),
    service: CaseService = Depends(get_case_service),
    user=Depends(require_role(*_LEAD_ROLES)),
) -> BulkResult:
    return BulkResult(
        **await service.bulk_priority(
            tenant.campus_id, user.id, user.display_name,
            data.case_ids, data.priority, data.reason,
        )
    )


@router.post("/bulk/status", response_model=BulkResult)
async def bulk_status(
    data: BulkStatusIn,
    tenant: TenantContext = Depends(get_school_context),
    service: CaseService = Depends(get_case_service),
    user=Depends(require_role(*_LEAD_ROLES)),
) -> BulkResult:
    return BulkResult(
        **await service.bulk_status(
            tenant.campus_id, user.id, user.display_name,
            data.case_ids, data.status, data.reason,
        )
    )


@router.post("/bulk/due-date", response_model=BulkResult)
async def bulk_due_date(
    data: BulkDueDateIn,
    tenant: TenantContext = Depends(get_school_context),
    service: CaseService = Depends(get_case_service),
    user=Depends(require_role(*_LEAD_ROLES)),
) -> BulkResult:
    return BulkResult(
        **await service.bulk_set_due_date(
            tenant.campus_id, user.id, user.display_name, data.case_ids, data.due_at
        )
    )


@router.post("/escalate", response_model=EscalationResult)
async def escalate(
    tenant: TenantContext = Depends(get_school_context),
    service: CaseService = Depends(get_case_service),
    user=Depends(require_role(*_LEAD_ROLES)),
) -> EscalationResult:
    return EscalationResult(
        **await service.run_escalation(tenant.campus_id, actor_user_id=user.id)
    )
