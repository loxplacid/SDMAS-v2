from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, PaginationParams
from app.domains.academic.repository import (
    AcademicYearRepository,
    ClassRepository,
    SectionRepository,
)
from app.domains.attendance.repository import AttendanceRepository
from app.domains.attendance.schemas import (
    AttendanceRecordCreate,
    AttendanceRecordResponse,
    AttendanceRecordUpdate,
    DailyAttendanceCreate,
    SectionAttendanceSummary,
    StudentAttendanceSummary,
)
from app.domains.attendance.service import AttendanceService
from app.domains.auth.dependencies import require_permission
from app.domains.auth.models import User
from app.domains.auth.permissions import (
    ATTENDANCE_RECORD,
    ATTENDANCE_UPDATE,
    ATTENDANCE_VIEW,
)
from app.domains.student.repository import StudentRepository
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.guards import assert_tenant_scope, effective_campus_id, inject_campus
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/attendance", tags=["attendance"])


async def get_attendance_service(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AttendanceService:
    return AttendanceService(
        AttendanceRepository(session, tenant),
        StudentRepository(session, tenant),
        AcademicYearRepository(session, tenant),
        ClassRepository(session, tenant),
        SectionRepository(session, tenant),
        tenant=tenant,
    )


@router.post(
    "",
    response_model=AttendanceRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_attendance(
    data: AttendanceRecordCreate,
    service: AttendanceService = Depends(get_attendance_service),
    tenant: TenantContext = Depends(require_tenant_context),
    _user: User = Depends(require_permission(ATTENDANCE_RECORD)),
) -> AttendanceRecordResponse:
    record = await service.record_attendance(data)
    inject_campus(record, tenant)
    return AttendanceRecordResponse.model_validate(record)


@router.post(
    "/daily",
    response_model=list[AttendanceRecordResponse],
    status_code=status.HTTP_201_CREATED,
)
async def record_daily_attendance(
    data: DailyAttendanceCreate,
    service: AttendanceService = Depends(get_attendance_service),
    tenant: TenantContext = Depends(require_tenant_context),
    _user: User = Depends(require_permission(ATTENDANCE_RECORD)),
) -> list[AttendanceRecordResponse]:
    records = await service.record_daily_attendance(data)
    for r in records:
        inject_campus(r, tenant)
    return [AttendanceRecordResponse.model_validate(r) for r in records]


@router.get("/{record_id}", response_model=AttendanceRecordResponse)
async def get_attendance(
    record_id: int,
    service: AttendanceService = Depends(get_attendance_service),
    tenant: TenantContext = Depends(require_tenant_context),
    _user: User = Depends(require_permission(ATTENDANCE_VIEW)),
) -> AttendanceRecordResponse:
    record = await service.get_attendance(record_id)
    assert_tenant_scope(record, tenant, resource="attendance")
    return AttendanceRecordResponse.model_validate(record)


@router.patch("/{record_id}", response_model=AttendanceRecordResponse)
async def update_attendance(
    record_id: int,
    data: AttendanceRecordUpdate,
    service: AttendanceService = Depends(get_attendance_service),
    tenant: TenantContext = Depends(require_tenant_context),
    _user: User = Depends(require_permission(ATTENDANCE_UPDATE)),
) -> AttendanceRecordResponse:
    record = await service.get_attendance(record_id)
    assert_tenant_scope(record, tenant, resource="attendance")
    record = await service.update_attendance(record_id, data)
    return AttendanceRecordResponse.model_validate(record)


@router.get("", response_model=Page[AttendanceRecordResponse])
async def list_attendance(
    pagination: PaginationParams = Depends(),
    student_id: Optional[int] = Query(
        default=None, alias="student_id", description="Filter by student"
    ),
    section_id: Optional[int] = Query(
        default=None, alias="section_id", description="Filter by section"
    ),
    status_filter: Optional[str] = Query(
        default=None, alias="status", description="Filter by status"
    ),
    attendance_date: Optional[str] = Query(
        default=None, alias="attendance_date", description="Filter by date"
    ),
    campus_id: Optional[int] = Query(
        default=None, alias="campus_id", description="Filter by campus"
    ),
    service: AttendanceService = Depends(get_attendance_service),
    tenant: TenantContext = Depends(require_tenant_context),
    _user: User = Depends(require_permission(ATTENDANCE_VIEW)),
) -> Page[AttendanceRecordResponse]:
    records, total = await service.repo.list(
        student_id=student_id,
        section_id=section_id,
        status=status_filter,
        attendance_date=attendance_date,
        campus_id=effective_campus_id(tenant, campus_id),
        skip=pagination.offset,
        limit=pagination.limit,
    )
    items = [AttendanceRecordResponse.model_validate(r) for r in records]
    return Page.create(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.get(
    "/student/{student_id}",
    response_model=Page[AttendanceRecordResponse],
)
async def get_student_attendance(
    student_id: int,
    pagination: PaginationParams = Depends(),
    academic_year_id: Optional[int] = Query(
        default=None,
        alias="academic_year_id",
        description="Filter by academic year",
    ),
    class_id: Optional[int] = Query(
        default=None, alias="class_id", description="Filter by class"
    ),
    section_id: Optional[int] = Query(
        default=None, alias="section_id", description="Filter by section"
    ),
    status_filter: Optional[str] = Query(
        default=None, alias="status", description="Filter by status"
    ),
    start_date: Optional[str] = Query(
        default=None, alias="start_date", description="Filter start date (inclusive)"
    ),
    end_date: Optional[str] = Query(
        default=None, alias="end_date", description="Filter end date (inclusive)"
    ),
    service: AttendanceService = Depends(get_attendance_service),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
    _user: User = Depends(require_permission(ATTENDANCE_VIEW)),
) -> Page[AttendanceRecordResponse]:
    if tenant.is_tenant_scoped:
        student = await StudentRepository(session, tenant).get_by_id(student_id)
        assert_tenant_scope(student, tenant, resource="student")
    records, total = await service.get_student_attendance(
        student_id=student_id,
        academic_year_id=academic_year_id,
        class_id=class_id,
        section_id=section_id,
        status=status_filter,
        start_date=start_date,
        end_date=end_date,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    items = [AttendanceRecordResponse.model_validate(r) for r in records]
    return Page.create(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.get(
    "/section/{section_id}",
    response_model=list[AttendanceRecordResponse],
)
async def get_section_attendance(
    section_id: int,
    attendance_date: str = Query(..., alias="attendance_date", description="Date to query"),
    service: AttendanceService = Depends(get_attendance_service),
    tenant: TenantContext = Depends(require_tenant_context),
    _user: User = Depends(require_permission(ATTENDANCE_VIEW)),
) -> list[AttendanceRecordResponse]:
    records = await service.get_section_attendance(section_id, attendance_date)
    return [AttendanceRecordResponse.model_validate(r) for r in records]


@router.get(
    "/student/{student_id}/summary",
    response_model=StudentAttendanceSummary,
)
async def get_student_summary(
    student_id: int,
    start_date: str = Query(..., alias="start_date", description="Start date (inclusive)"),
    end_date: str = Query(..., alias="end_date", description="End date (inclusive)"),
    service: AttendanceService = Depends(get_attendance_service),
    tenant: TenantContext = Depends(require_tenant_context),
    _user: User = Depends(require_permission(ATTENDANCE_VIEW)),
) -> StudentAttendanceSummary:
    summary = await service.get_student_summary(student_id, start_date, end_date)
    return StudentAttendanceSummary(**summary)


@router.get(
    "/section/{section_id}/summary",
    response_model=SectionAttendanceSummary,
)
async def get_section_summary(
    section_id: int,
    attendance_date: str = Query(..., alias="attendance_date", description="Date to summarize"),
    service: AttendanceService = Depends(get_attendance_service),
    tenant: TenantContext = Depends(require_tenant_context),
    _user: User = Depends(require_permission(ATTENDANCE_VIEW)),
) -> SectionAttendanceSummary:
    summary = await service.get_section_summary(section_id, attendance_date)
    return SectionAttendanceSummary(**summary)