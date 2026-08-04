from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, PaginationParams
from app.domains.auth.dependencies import require_permission
from app.domains.auth.permissions import STUDENTS_UPDATE, STUDENTS_VIEW
from app.domains.auth.models import User
from app.domains.student.lifecycle_service import StudentLifecycleService
from app.domains.student.schemas import (
    LifecycleEventOut,
    LifecycleStateOut,
    LifecycleTransitionIn,
)
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.guards import assert_tenant_scope
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/students/{student_id}/lifecycle", tags=["students-lifecycle"])


async def get_lifecycle_service(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> StudentLifecycleService:
    return StudentLifecycleService(session, tenant)


async def _load_scoped_student(
    student_id: int,
    service: StudentLifecycleService = Depends(get_lifecycle_service),
    tenant: TenantContext = Depends(require_tenant_context),
):
    """Load the student and enforce tenant object-level access."""
    from app.domains.student.repository import StudentRepository

    student = await StudentRepository(service.session, tenant).get_by_id(student_id)
    assert_tenant_scope(student, tenant, resource="student")
    return student


@router.get("", response_model=LifecycleStateOut)
async def get_lifecycle_state(
    student_id: int,
    service: StudentLifecycleService = Depends(get_lifecycle_service),
    _user: User = Depends(require_permission(STUDENTS_VIEW)),  # noqa: B008
    _student=Depends(_load_scoped_student),  # noqa: B008
) -> LifecycleStateOut:
    return await service.get_state(student_id)


@router.get("/events", response_model=Page[LifecycleEventOut])
async def list_lifecycle_events(
    student_id: int,
    pagination: PaginationParams = Depends(),
    service: StudentLifecycleService = Depends(get_lifecycle_service),
    _user: User = Depends(require_permission(STUDENTS_VIEW)),  # noqa: B008
    _student=Depends(_load_scoped_student),  # noqa: B008
) -> Page[LifecycleEventOut]:
    events, total = await service.list_events(
        student_id,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return Page.create(
        items=events,
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.post(
    "/transitions",
    response_model=LifecycleStateOut,
    status_code=status.HTTP_200_OK,
)
async def transition_student(
    student_id: int,
    data: LifecycleTransitionIn,
    service: StudentLifecycleService = Depends(get_lifecycle_service),
    current_user: User = Depends(require_permission(STUDENTS_UPDATE)),  # noqa: B008
    _student=Depends(_load_scoped_student),  # noqa: B008
) -> LifecycleStateOut:
    """Perform a deterministic lifecycle transition (auditable)."""
    return await service.transition(
        student_id,
        to_status=data.to_status,
        reason=data.reason,
        actor_user_id=current_user.id,
        actor_username=(
            current_user.username if hasattr(current_user, "username") else None
        ),
    )
