"""Teacher 360 router.

Read-only aggregated view of a teacher.  Protected by ``teachers.view`` and
pinned to the caller's tenant (campus) so cross-campus data can never leak.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.dependencies import require_permission
from app.domains.auth.permissions import TEACHERS_VIEW
from app.domains.teacher_360.schemas import Teacher360Response
from app.domains.teacher_360.service import Teacher360Service
from app.domains.academic.repository import TeacherRepository
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.guards import assert_tenant_scope, effective_campus_id
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/teachers/{teacher_id}/360", tags=["teacher-360"])


async def get_360_service(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> Teacher360Service:
    return Teacher360Service(session, tenant)


@router.get("", response_model=Teacher360Response)
async def get_teacher_360(
    teacher_id: int,
    service: Teacher360Service = Depends(get_360_service),
    tenant: TenantContext = Depends(require_tenant_context),
    campus_id: int | None = Query(default=None),
    _user=Depends(require_permission(TEACHERS_VIEW)),
) -> Teacher360Response:
    # The repository applies the tenant predicate at query construction
    # time; the explicit assert remains as defense-in-depth.
    session = service.session
    teacher = await TeacherRepository(session, tenant).get_by_id(teacher_id)
    assert_tenant_scope(teacher, tenant, resource="teacher")

    scope = effective_campus_id(tenant, campus_id)
    return await service.get_teacher_360(teacher_id, campus_id=scope)
