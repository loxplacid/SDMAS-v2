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

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


@router.get("/overview", response_model=AnalyticsOverview)
async def get_analytics_overview(
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
) -> AnalyticsOverview:
    svc = AnalyticsService(session)
    return AnalyticsOverview(**await svc.get_overview())


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
) -> AttendanceOverview:
    svc = AnalyticsService(session)
    return AttendanceOverview(
        **await svc.get_attendance_overview(
            academic_year_id=academic_year_id,
            class_id=class_id,
            section_id=section_id,
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
) -> AttendanceTrend:
    svc = AnalyticsService(session)
    return AttendanceTrend(
        **await svc.get_attendance_trends(
            academic_year_id=academic_year_id,
            class_id=class_id,
            section_id=section_id,
            granularity=granularity,
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
) -> list[ClassAttendanceComparison]:
    svc = AnalyticsService(session)
    data = await svc.get_attendance_class_comparison(
        academic_year_id=academic_year_id
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
) -> list[SectionAttendanceComparison]:
    svc = AnalyticsService(session)
    data = await svc.get_attendance_section_comparison(
        academic_year_id=academic_year_id,
        class_id=class_id,
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
) -> list[LowAttendanceStudent]:
    svc = AnalyticsService(session)
    data = await svc.get_low_attendance_students(
        threshold=threshold,
        academic_year_id=academic_year_id,
        min_records=min_records,
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
) -> list[TermAttendanceAnalytics]:
    svc = AnalyticsService(session)
    data = await svc.get_all_term_attendance(
        academic_year_id=academic_year_id
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
) -> FinanceOverview:
    svc = AnalyticsService(session)
    return FinanceOverview(
        **await svc.get_finance_overview(
            academic_year_id=academic_year_id
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
) -> CollectionTrend:
    svc = AnalyticsService(session)
    return CollectionTrend(
        **await svc.get_collection_trends(
            academic_year_id=academic_year_id,
            granularity=granularity,
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
) -> list[FeeTypeCollection]:
    svc = AnalyticsService(session)
    data = await svc.get_fee_type_collection(
        academic_year_id=academic_year_id
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
) -> list[ClassFeeCollection]:
    svc = AnalyticsService(session)
    data = await svc.get_class_fee_collection(
        academic_year_id=academic_year_id
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
) -> list[PaymentMethodDistribution]:
    svc = AnalyticsService(session)
    data = await svc.get_payment_method_distribution(
        academic_year_id=academic_year_id
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
) -> list[FeeStatusDistribution]:
    svc = AnalyticsService(session)
    data = await svc.get_fee_status_distribution(
        academic_year_id=academic_year_id
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
) -> StudentOverview:
    svc = AnalyticsService(session)
    return StudentOverview(**await svc.get_student_overview())


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
) -> list[StudentsByClass]:
    svc = AnalyticsService(session)
    data = await svc.get_students_by_class(
        academic_year_id=academic_year_id
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
) -> list[StudentsBySection]:
    svc = AnalyticsService(session)
    data = await svc.get_students_by_section(
        academic_year_id=academic_year_id,
        class_id=class_id,
    )
    return [StudentsBySection(**d) for d in data]


@router.get(
    "/students/enrollment-trends",
    response_model=list[EnrollmentTrend],
)
async def get_enrollment_trends(
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
) -> list[EnrollmentTrend]:
    svc = AnalyticsService(session)
    data = await svc.get_enrollment_trends()
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
) -> AcademicOverview:
    svc = AnalyticsService(session)
    return AcademicOverview(**await svc.get_academic_overview())


@router.get(
    "/academic/teacher-workload",
    response_model=list[TeacherWorkload],
)
async def get_teacher_workload(
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
) -> list[TeacherWorkload]:
    svc = AnalyticsService(session)
    data = await svc.get_teacher_workload()
    return [TeacherWorkload(**d) for d in data]


@router.get(
    "/academic/subjects",
    response_model=list[SubjectDistribution],
)
async def get_subject_distribution(
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
) -> list[SubjectDistribution]:
    svc = AnalyticsService(session)
    data = await svc.get_subject_distribution()
    return [SubjectDistribution(**d) for d in data]
