from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.dependencies import get_current_user, require_role
from app.domains.auth.models import User
from app.domains.analytics.schemas import (
    AcademicOverview,
    AnalyticsOverview,
    AttendanceOverview,
    AttendanceTrend,
    ClassAttendanceComparison,
    ClassFeeCollection,
    CollectionTrend,
    EnrollmentTrend,
    FeeStatusDistribution,
    FeeTypeCollection,
    FinanceOverview,
    LowAttendanceStudent,
    PaymentMethodDistribution,
    SectionAttendanceComparison,
    StudentOverview,
    StudentsByClass,
    StudentsBySection,
    SubjectDistribution,
    TeacherWorkload,
    TermAttendanceAnalytics,
)
from app.domains.analytics.service import AnalyticsService
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.guards import effective_campus_id
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _scoped_campus(tenant: TenantContext) -> Optional[int]:
    """Resolve the tenant's campus for analytics queries (None = cross-tenant
    platform caller, who is explicitly authorized).

    Plain function (not ``async``) because it must return the resolved id
    synchronously — earlier versions were ``async def`` and callers
    forgot to ``await`` them, passing a coroutine into the SQL layer.
    """
    return effective_campus_id(tenant, None)


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


@router.get("/overview", response_model=AnalyticsOverview)
async def get_analytics_overview(
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AnalyticsOverview:
    svc = AnalyticsService(session)
    return AnalyticsOverview(**await svc.get_overview(campus_id=_scoped_campus(tenant)))


# ---------------------------------------------------------------------------
# Attendance analytics
# ---------------------------------------------------------------------------


@router.get(
    "/attendance/overview",
    response_model=AttendanceOverview,
)
async def get_attendance_overview(
    academic_year_id: Optional[int] = Query(
        default=None, alias="academic_year_id"
    ),
    class_id: Optional[int] = Query(default=None, alias="class_id"),
    section_id: Optional[int] = Query(default=None, alias="section_id"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AttendanceOverview:
    svc = AnalyticsService(session)
    return AttendanceOverview(
        **await svc.get_attendance_overview(
            academic_year_id=academic_year_id,
            class_id=class_id,
            section_id=section_id,
            campus_id=_scoped_campus(tenant),
        )
    )


@router.get(
    "/attendance/trends",
    response_model=AttendanceTrend,
)
async def get_attendance_trends(
    academic_year_id: Optional[int] = Query(
        default=None, alias="academic_year_id"
    ),
    class_id: Optional[int] = Query(default=None, alias="class_id"),
    section_id: Optional[int] = Query(default=None, alias="section_id"),
    granularity: str = Query(default="daily", alias="granularity"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AttendanceTrend:
    svc = AnalyticsService(session)
    return AttendanceTrend(
        **await svc.get_attendance_trends(
            academic_year_id=academic_year_id,
            class_id=class_id,
            section_id=section_id,
            granularity=granularity,
            campus_id=_scoped_campus(tenant),
        )
    )


@router.get(
    "/attendance/classes",
    response_model=list[ClassAttendanceComparison],
)
async def get_attendance_class_comparison(
    academic_year_id: Optional[int] = Query(
        default=None, alias="academic_year_id"
    ),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[ClassAttendanceComparison]:
    svc = AnalyticsService(session)
    data = await svc.get_attendance_class_comparison(
        academic_year_id=academic_year_id, campus_id=_scoped_campus(tenant)
    )
    return [ClassAttendanceComparison(**d) for d in data]


@router.get(
    "/attendance/sections",
    response_model=list[SectionAttendanceComparison],
)
async def get_attendance_section_comparison(
    academic_year_id: Optional[int] = Query(
        default=None, alias="academic_year_id"
    ),
    class_id: Optional[int] = Query(default=None, alias="class_id"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[SectionAttendanceComparison]:
    svc = AnalyticsService(session)
    data = await svc.get_attendance_section_comparison(
        academic_year_id=academic_year_id,
        class_id=class_id,
        campus_id=_scoped_campus(tenant),
    )
    return [SectionAttendanceComparison(**d) for d in data]


@router.get(
    "/attendance/low-attendance",
    response_model=list[LowAttendanceStudent],
)
async def get_low_attendance_students(
    threshold: int = Query(default=90, alias="threshold"),
    academic_year_id: Optional[int] = Query(
        default=None, alias="academic_year_id"
    ),
    min_records: int = Query(default=1, alias="min_records"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[LowAttendanceStudent]:
    svc = AnalyticsService(session)
    data = await svc.get_low_attendance_students(
        threshold=threshold,
        academic_year_id=academic_year_id,
        min_records=min_records,
        campus_id=_scoped_campus(tenant),
    )
    return [LowAttendanceStudent(**d) for d in data]


@router.get(
    "/attendance/terms",
    response_model=list[TermAttendanceAnalytics],
)
async def get_term_attendance(
    academic_year_id: Optional[int] = Query(
        default=None, alias="academic_year_id"
    ),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[TermAttendanceAnalytics]:
    svc = AnalyticsService(session)
    data = await svc.get_all_term_attendance(
        academic_year_id=academic_year_id, campus_id=_scoped_campus(tenant)
    )
    return [TermAttendanceAnalytics(**d) for d in data]


# ---------------------------------------------------------------------------
# Financial analytics
# ---------------------------------------------------------------------------


@router.get(
    "/finance/overview",
    response_model=FinanceOverview,
)
async def get_finance_overview(
    academic_year_id: Optional[int] = Query(
        default=None, alias="academic_year_id"
    ),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> FinanceOverview:
    svc = AnalyticsService(session)
    return FinanceOverview(
        **await svc.get_finance_overview(
            academic_year_id=academic_year_id, campus_id=_scoped_campus(tenant)
        )
    )


@router.get(
    "/finance/trends",
    response_model=CollectionTrend,
)
async def get_finance_trends(
    academic_year_id: Optional[int] = Query(
        default=None, alias="academic_year_id"
    ),
    granularity: str = Query(default="daily", alias="granularity"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> CollectionTrend:
    svc = AnalyticsService(session)
    return CollectionTrend(
        **await svc.get_collection_trends(
            academic_year_id=academic_year_id,
            granularity=granularity,
            campus_id=_scoped_campus(tenant),
        )
    )


@router.get(
    "/finance/fee-types",
    response_model=list[FeeTypeCollection],
)
async def get_fee_type_collection(
    academic_year_id: Optional[int] = Query(
        default=None, alias="academic_year_id"
    ),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[FeeTypeCollection]:
    svc = AnalyticsService(session)
    data = await svc.get_fee_type_collection(
        academic_year_id=academic_year_id, campus_id=_scoped_campus(tenant)
    )
    return [FeeTypeCollection(**d) for d in data]


@router.get(
    "/finance/classes",
    response_model=list[ClassFeeCollection],
)
async def get_finance_class_collection(
    academic_year_id: Optional[int] = Query(
        default=None, alias="academic_year_id"
    ),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[ClassFeeCollection]:
    svc = AnalyticsService(session)
    data = await svc.get_class_fee_collection(
        academic_year_id=academic_year_id, campus_id=_scoped_campus(tenant)
    )
    return [ClassFeeCollection(**d) for d in data]


@router.get(
    "/finance/payment-methods",
    response_model=list[PaymentMethodDistribution],
)
async def get_payment_method_distribution(
    academic_year_id: Optional[int] = Query(
        default=None, alias="academic_year_id"
    ),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[PaymentMethodDistribution]:
    svc = AnalyticsService(session)
    data = await svc.get_payment_method_distribution(
        academic_year_id=academic_year_id, campus_id=_scoped_campus(tenant)
    )
    return [PaymentMethodDistribution(**d) for d in data]


@router.get(
    "/finance/status",
    response_model=list[FeeStatusDistribution],
)
async def get_fee_status_distribution(
    academic_year_id: Optional[int] = Query(
        default=None, alias="academic_year_id"
    ),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[FeeStatusDistribution]:
    svc = AnalyticsService(session)
    data = await svc.get_fee_status_distribution(
        academic_year_id=academic_year_id, campus_id=_scoped_campus(tenant)
    )
    return [FeeStatusDistribution(**d) for d in data]


# ---------------------------------------------------------------------------
# Student analytics
# ---------------------------------------------------------------------------


@router.get(
    "/students/overview",
    response_model=StudentOverview,
)
async def get_student_overview(
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> StudentOverview:
    svc = AnalyticsService(session)
    return StudentOverview(**await svc.get_student_overview(campus_id=_scoped_campus(tenant)))


@router.get(
    "/students/classes",
    response_model=list[StudentsByClass],
)
async def get_students_by_class(
    academic_year_id: Optional[int] = Query(
        default=None, alias="academic_year_id"
    ),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[StudentsByClass]:
    svc = AnalyticsService(session)
    data = await svc.get_students_by_class(
        academic_year_id=academic_year_id, campus_id=_scoped_campus(tenant)
    )
    return [StudentsByClass(**d) for d in data]


@router.get(
    "/students/sections",
    response_model=list[StudentsBySection],
)
async def get_students_by_section(
    academic_year_id: Optional[int] = Query(
        default=None, alias="academic_year_id"
    ),
    class_id: Optional[int] = Query(default=None, alias="class_id"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[StudentsBySection]:
    svc = AnalyticsService(session)
    data = await svc.get_students_by_section(
        academic_year_id=academic_year_id,
        class_id=class_id,
        campus_id=_scoped_campus(tenant),
    )
    return [StudentsBySection(**d) for d in data]


@router.get(
    "/students/enrollment-trends",
    response_model=list[EnrollmentTrend],
)
async def get_enrollment_trends(
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[EnrollmentTrend]:
    svc = AnalyticsService(session)
    data = await svc.get_enrollment_trends(campus_id=_scoped_campus(tenant))
    return [EnrollmentTrend(**d) for d in data]


# ---------------------------------------------------------------------------
# Academic analytics
# ---------------------------------------------------------------------------


@router.get(
    "/academic/overview",
    response_model=AcademicOverview,
)
async def get_academic_overview(
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AcademicOverview:
    svc = AnalyticsService(session)
    return AcademicOverview(**await svc.get_academic_overview(campus_id=_scoped_campus(tenant)))


@router.get(
    "/academic/teacher-workload",
    response_model=list[TeacherWorkload],
)
async def get_teacher_workload(
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[TeacherWorkload]:
    svc = AnalyticsService(session)
    data = await svc.get_teacher_workload(campus_id=_scoped_campus(tenant))
    return [TeacherWorkload(**d) for d in data]


@router.get(
    "/academic/subjects",
    response_model=list[SubjectDistribution],
)
async def get_subject_distribution(
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[SubjectDistribution]:
    svc = AnalyticsService(session)
    data = await svc.get_subject_distribution(campus_id=_scoped_campus(tenant))
    return [SubjectDistribution(**d) for d in data]
