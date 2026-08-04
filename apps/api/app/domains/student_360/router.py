from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.dependencies import get_current_user, require_permission
from app.domains.student.repository import StudentRepository
from app.domains.student_360.schemas import Student360Response
from app.domains.student_360.service import Student360Service
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.guards import assert_tenant_scope
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/students/{student_id}/360", tags=["student-360"])


async def get_360_service(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> Student360Service:
    return Student360Service(session, tenant)


@router.get("", response_model=Student360Response)
async def get_student_360(
    student_id: int,
    service: Student360Service = Depends(get_360_service),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
    _user=Depends(require_permission("students.view")),
) -> Student360Response:
    # Object-level access control: the repository applies the tenant
    # predicate at query construction time, so a cross-tenant id is not
    # even visible here; the explicit assert below remains as defense-in-
    # depth before aggregating any student data.
    student = await StudentRepository(session, tenant).get_by_id(student_id)
    assert_tenant_scope(student, tenant, resource="student")
    return await service.get_student_360(student_id)
