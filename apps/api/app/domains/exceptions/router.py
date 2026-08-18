"""Universal Exception Management — FastAPI router (TASK 17).

Every endpoint is permission-gated (``exceptions.view`` /
``exceptions.manage``), tenant-scoped through ``require_tenant_context``,
and audit-attributed through the typed ``AuditActor``.  Frontend hiding
is not authorization — the backend enforces independently.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.pagination import PaginationParams
from app.domains.audit.actors import AuditActor
from app.domains.auth.dependencies import require_permission
from app.domains.auth.models import User
from app.domains.auth.permissions import (
    EXCEPTIONS_MANAGE,
    EXCEPTIONS_VIEW,
)
from app.domains.exceptions.schemas import (
    ExceptionAssign,
    ExceptionCaseLink,
    ExceptionCreate,
    ExceptionDueDateUpdate,
    ExceptionEvidenceAdd,
    ExceptionMetricsResponse,
    ExceptionPage,
    ExceptionResolve,
    ExceptionResponse,
    ExceptionRootCauseUpdate,
    ExceptionSeverityUpdate,
    ExceptionWorkflowLink,
)
from app.domains.exceptions.service import ExceptionService
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/api/exceptions", tags=["exceptions"])


async def get_exception_svc(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> ExceptionService:
    return ExceptionService(session, tenant)


def _actor(user: User) -> AuditActor:
    return AuditActor.user(user.id, user.username)


def _not_found(exception_id: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"SystemException {exception_id} not found",
    )


# ======================================================================
# Reads
# ======================================================================


@router.get("", response_model=ExceptionPage)
async def list_exceptions(
    pagination: PaginationParams = Depends(),
    exception_type: Optional[str] = Query(None, alias="exception_type"),
    severity: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    entity_type: Optional[str] = Query(None, alias="entity_type"),
    entity_id: Optional[int] = Query(None, alias="entity_id"),
    student_id: Optional[int] = Query(None, alias="student_id"),
    owner_id: Optional[int] = Query(None, alias="owner_id"),
    source_domain: Optional[str] = Query(None, alias="source_domain"),
    svc: ExceptionService = Depends(get_exception_svc),
    _user: User = Depends(require_permission(EXCEPTIONS_VIEW)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> ExceptionPage:
    items, total = await svc.list(
        exception_type=exception_type,
        severity=severity,
        status=status_filter,
        entity_type=entity_type,
        entity_id=entity_id,
        student_id=student_id,
        owner_id=owner_id,
        source_domain=source_domain,
        offset=pagination.offset,
        limit=pagination.limit,
    )
    return ExceptionPage.create(
        [ExceptionResponse.model_validate(i) for i in items],
        total,
        pagination.page,
        pagination.size,
    )


@router.get("/metrics", response_model=ExceptionMetricsResponse)
async def exception_metrics(
    svc: ExceptionService = Depends(get_exception_svc),
    _user: User = Depends(require_permission(EXCEPTIONS_VIEW)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> ExceptionMetricsResponse:
    return ExceptionMetricsResponse(**await svc.metrics())


@router.get("/by-source", response_model=Optional[ExceptionResponse])
async def get_exception_by_source(
    source_domain: str = Query(..., min_length=1, max_length=50),
    source_type: str = Query(..., min_length=1, max_length=50),
    source_id: int = Query(...),
    svc: ExceptionService = Depends(get_exception_svc),
    _user: User = Depends(require_permission(EXCEPTIONS_VIEW)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> Optional[ExceptionResponse]:
    """Idempotency helper: fetch the exception for a source triple."""
    exception = await svc.get_by_source(source_domain, source_type, source_id)
    if exception is None:
        return None
    return ExceptionResponse.model_validate(exception)


@router.get("/students/{student_id}", response_model=list[ExceptionResponse])
async def list_student_exceptions(
    student_id: int,
    include_resolved: bool = Query(False, alias="include_resolved"),
    svc: ExceptionService = Depends(get_exception_svc),
    _user: User = Depends(require_permission(EXCEPTIONS_VIEW)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> list[ExceptionResponse]:
    """Exceptions for a specific student (Student 360 view)."""
    items = await svc.list_for_student(student_id, include_resolved=include_resolved)
    return [ExceptionResponse.model_validate(i) for i in items]


@router.get("/{exception_id}", response_model=ExceptionResponse)
async def get_exception(
    exception_id: int,
    svc: ExceptionService = Depends(get_exception_svc),
    _user: User = Depends(require_permission(EXCEPTIONS_VIEW)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> ExceptionResponse:
    try:
        exception = await svc.get(exception_id)
    except NotFoundError:
        raise _not_found(exception_id)
    return ExceptionResponse.model_validate(exception)


# ======================================================================
# Create
# ======================================================================


@router.post("", response_model=ExceptionResponse, status_code=status.HTTP_201_CREATED)
async def create_exception(
    data: ExceptionCreate,
    svc: ExceptionService = Depends(get_exception_svc),
    user: User = Depends(require_permission(EXCEPTIONS_MANAGE)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> ExceptionResponse:
    try:
        exception = await svc.create(
            exception_type=data.exception_type,
            severity=data.severity,
            title=data.title,
            description=data.description,
            source_domain=data.source_domain,
            source_type=data.source_type,
            source_id=data.source_id,
            rule_code=data.rule_code,
            entity_type=data.entity_type,
            entity_id=data.entity_id,
            student_id=data.student_id,
            evidence=data.evidence,
            owner_id=data.owner_id,
            actor_id=user.id,
            actor_name=user.username,
            priority=data.priority,
            due_at=data.due_at,
        )
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return ExceptionResponse.model_validate(exception)


# ======================================================================
# Lifecycle transitions
# ======================================================================


@router.post("/{exception_id}/acknowledge", response_model=ExceptionResponse)
async def acknowledge_exception(
    exception_id: int,
    svc: ExceptionService = Depends(get_exception_svc),
    user: User = Depends(require_permission(EXCEPTIONS_MANAGE)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> ExceptionResponse:
    try:
        exception = await svc.acknowledge(exception_id, user.id, user.username)
    except NotFoundError:
        raise _not_found(exception_id)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return ExceptionResponse.model_validate(exception)


@router.post("/{exception_id}/start", response_model=ExceptionResponse)
async def start_exception(
    exception_id: int,
    svc: ExceptionService = Depends(get_exception_svc),
    user: User = Depends(require_permission(EXCEPTIONS_MANAGE)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> ExceptionResponse:
    try:
        exception = await svc.start(exception_id, user.id, user.username)
    except NotFoundError:
        raise _not_found(exception_id)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return ExceptionResponse.model_validate(exception)


@router.post("/{exception_id}/resolve", response_model=ExceptionResponse)
async def resolve_exception(
    exception_id: int,
    data: ExceptionResolve,
    svc: ExceptionService = Depends(get_exception_svc),
    user: User = Depends(require_permission(EXCEPTIONS_MANAGE)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> ExceptionResponse:
    try:
        exception = await svc.resolve(
            exception_id,
            resolution_type=data.resolution_type,
            resolution_note=data.resolution_note,
            root_cause=data.root_cause,
            actor_id=user.id,
            actor_name=user.username,
        )
    except NotFoundError:
        raise _not_found(exception_id)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return ExceptionResponse.model_validate(exception)


@router.post("/{exception_id}/close", response_model=ExceptionResponse)
async def close_exception(
    exception_id: int,
    svc: ExceptionService = Depends(get_exception_svc),
    user: User = Depends(require_permission(EXCEPTIONS_MANAGE)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> ExceptionResponse:
    try:
        exception = await svc.close(exception_id, user.id, user.username)
    except NotFoundError:
        raise _not_found(exception_id)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return ExceptionResponse.model_validate(exception)


@router.post("/{exception_id}/reopen", response_model=ExceptionResponse)
async def reopen_exception(
    exception_id: int,
    svc: ExceptionService = Depends(get_exception_svc),
    user: User = Depends(require_permission(EXCEPTIONS_MANAGE)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> ExceptionResponse:
    try:
        exception = await svc.reopen(exception_id, user.id, user.username)
    except NotFoundError:
        raise _not_found(exception_id)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return ExceptionResponse.model_validate(exception)


# ======================================================================
# Targeted mutations
# ======================================================================


@router.post("/{exception_id}/assign", response_model=ExceptionResponse)
async def assign_exception(
    exception_id: int,
    data: ExceptionAssign,
    svc: ExceptionService = Depends(get_exception_svc),
    user: User = Depends(require_permission(EXCEPTIONS_MANAGE)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> ExceptionResponse:
    try:
        exception = await svc.assign(exception_id, data.owner_id, user.id, user.username)
    except NotFoundError:
        raise _not_found(exception_id)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return ExceptionResponse.model_validate(exception)


@router.post("/{exception_id}/severity", response_model=ExceptionResponse)
async def update_exception_severity(
    exception_id: int,
    data: ExceptionSeverityUpdate,
    svc: ExceptionService = Depends(get_exception_svc),
    user: User = Depends(require_permission(EXCEPTIONS_MANAGE)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> ExceptionResponse:
    try:
        exception = await svc.update_severity(exception_id, data.severity, user.id, user.username)
    except NotFoundError:
        raise _not_found(exception_id)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return ExceptionResponse.model_validate(exception)


@router.post("/{exception_id}/due-date", response_model=ExceptionResponse)
async def set_exception_due_date(
    exception_id: int,
    data: ExceptionDueDateUpdate,
    svc: ExceptionService = Depends(get_exception_svc),
    user: User = Depends(require_permission(EXCEPTIONS_MANAGE)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> ExceptionResponse:
    try:
        exception = await svc.set_due_date(exception_id, data.due_at, user.id, user.username)
    except NotFoundError:
        raise _not_found(exception_id)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return ExceptionResponse.model_validate(exception)


@router.post("/{exception_id}/root-cause", response_model=ExceptionResponse)
async def set_exception_root_cause(
    exception_id: int,
    data: ExceptionRootCauseUpdate,
    svc: ExceptionService = Depends(get_exception_svc),
    user: User = Depends(require_permission(EXCEPTIONS_MANAGE)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> ExceptionResponse:
    try:
        exception = await svc.set_root_cause(exception_id, data.root_cause, user.id, user.username)
    except NotFoundError:
        raise _not_found(exception_id)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return ExceptionResponse.model_validate(exception)


@router.post("/{exception_id}/evidence", response_model=ExceptionResponse)
async def add_exception_evidence(
    exception_id: int,
    data: ExceptionEvidenceAdd,
    svc: ExceptionService = Depends(get_exception_svc),
    user: User = Depends(require_permission(EXCEPTIONS_MANAGE)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> ExceptionResponse:
    try:
        exception = await svc.add_evidence(exception_id, data.evidence, user.id, user.username)
    except NotFoundError:
        raise _not_found(exception_id)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return ExceptionResponse.model_validate(exception)


@router.post("/{exception_id}/link-case", response_model=ExceptionResponse)
async def link_exception_case(
    exception_id: int,
    data: ExceptionCaseLink,
    svc: ExceptionService = Depends(get_exception_svc),
    user: User = Depends(require_permission(EXCEPTIONS_MANAGE)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> ExceptionResponse:
    try:
        exception = await svc.link_case(exception_id, data.case_id, user.id, user.username)
    except NotFoundError:
        raise _not_found(exception_id)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return ExceptionResponse.model_validate(exception)


@router.post("/{exception_id}/link-workflow", response_model=ExceptionResponse)
async def link_exception_workflow(
    exception_id: int,
    data: ExceptionWorkflowLink,
    svc: ExceptionService = Depends(get_exception_svc),
    user: User = Depends(require_permission(EXCEPTIONS_MANAGE)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> ExceptionResponse:
    try:
        exception = await svc.link_workflow(
            exception_id, data.workflow_instance_id, user.id, user.username
        )
    except NotFoundError:
        raise _not_found(exception_id)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return ExceptionResponse.model_validate(exception)
