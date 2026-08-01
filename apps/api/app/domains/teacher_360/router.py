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
from app.multi_tenant.dependencies import get_optional_tenant
from app.multi_tenant.guards import assert_tenant_scope, effective_campus_id
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/teachers/{teacher_id}/360", tags=["teacher-360"])


async def get_360_service(
    session: AsyncSession = Depends(get_session),
) -> Teacher360Service:
    return Teacher360Service(session)


@router.get("", response_model=Teacher360Response)
async def get_teacher_360(
    teacher_id: int,
    service: Teacher360Service = Depends(get_360_service),
    tenant: TenantContext = Depends(get_optional_tenant),
    campus_id: int | None = Query(default=None),
    _user=Depends(require_permission(TEACHERS_VIEW)),
) -> Teacher360Response:
    # Verify the teacher belongs to the caller's campus before aggregating.
    session = service.session
    teacher = await TeacherRepository(session).get_by_id(teacher_id)
    assert_tenant_scope(teacher, tenant, resource="teacher")

    scope = effective_campus_id(tenant, campus_id)
    return await service.get_teacher_360(teacher_id, campus_id=scope)
