from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, PaginationParams
from app.domains.auth.dependencies import require_permission
from app.domains.auth.permissions import STUDENTS_DELETE
from app.domains.student.repository import StudentRepository
from app.domains.student.schemas import (
    StudentCreate,
    StudentResponse,
    StudentUpdate,
)
from app.domains.student.service import StudentService
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import get_optional_tenant
from app.multi_tenant.guards import assert_tenant_scope, effective_campus_id, inject_campus
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/students", tags=["students"])


async def get_student_service(
    session: AsyncSession = Depends(get_session),
) -> StudentService:
    return StudentService(StudentRepository(session))


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
    data: StudentCreate,
    service: StudentService = Depends(get_student_service),
    tenant: TenantContext = Depends(get_optional_tenant),
) -> StudentResponse:
    student = await service.create_student(data)
    inject_campus(student, tenant)
    return StudentResponse.model_validate(student)


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: int,
    service: StudentService = Depends(get_student_service),
    tenant: TenantContext = Depends(get_optional_tenant),
) -> StudentResponse:
    student = await service.get_student(student_id)
    assert_tenant_scope(student, tenant, resource="student")
    return StudentResponse.model_validate(student)


@router.get("", response_model=Page[StudentResponse])
async def list_students(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(
        default=None, alias="status", description="Filter by student status"
    ),
    search: Optional[str] = Query(
        default=None, description="Search across name, number, email"
    ),
    campus_id: Optional[int] = Query(
        default=None, alias="campus_id", description="Filter by campus"
    ),
    service: StudentService = Depends(get_student_service),
    tenant: TenantContext = Depends(get_optional_tenant),
) -> Page[StudentResponse]:
    effective_campus = effective_campus_id(tenant, campus_id)
    if search:
        students, total = await service.search_students(
            query=search,
            campus_id=effective_campus,
            skip=pagination.offset,
            limit=pagination.limit,
        )
    else:
        students, total = await service.list_students(
            status=status_filter,
            campus_id=effective_campus,
            skip=pagination.offset,
            limit=pagination.limit,
        )

    items = [StudentResponse.model_validate(s) for s in students]
    return Page.create(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.patch("/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: int,
    data: StudentUpdate,
    service: StudentService = Depends(get_student_service),
    tenant: TenantContext = Depends(get_optional_tenant),
) -> StudentResponse:
    student = await service.get_student(student_id)
    assert_tenant_scope(student, tenant, resource="student")
    student = await service.update_student(student_id, data)
    return StudentResponse.model_validate(student)


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(
    student_id: int,
    service: StudentService = Depends(get_student_service),
    tenant: TenantContext = Depends(get_optional_tenant),
    _user=Depends(require_permission(STUDENTS_DELETE)),  # noqa
) -> None:
    student = await service.get_student(student_id)
    assert_tenant_scope(student, tenant, resource="student")
    await service.delete_student(student_id)