from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, PaginationParams
from app.domains.attendance_intelligence.schemas import (
    AbsenceReasonCreate,
    AbsenceReasonPage,
    AbsenceReasonResponse,
    AbsenceReasonUpdate,
    AttendanceCorrectionCreate,
    AttendanceCorrectionPage,
    AttendanceCorrectionResponse,
    AttendanceCorrectionReview,
    AttendanceCorrectionUpdate,
    AttendanceIntelligenceDashboard,
    AttendanceThresholdCreate,
    AttendanceThresholdPage,
    AttendanceThresholdResponse,
    AttendanceThresholdUpdate,
    ChronicAbsenteeismRecord,
    ClassAttendanceTrend,
    LowAttendanceAlertItem,
    PeriodAttendanceBatchCreate,
    PeriodAttendancePage,
    PeriodAttendanceRecordResponse,
    PeriodAttendanceRecordUpdate,
    PeriodAttendanceResponse,
    SectionAttendanceTrend,
    StudentAttendanceTrend,
)
from app.domains.attendance_intelligence.service import (
    AbsenceReasonService,
    AttendanceAnalyticsService,
    AttendanceCorrectionService,
    AttendanceThresholdService,
    PeriodAttendanceService,
)
from app.infrastructure.database import get_session

router = APIRouter(prefix="/api/attendance-intelligence", tags=["attendance-intelligence"])


# ── Dependency helpers ──────────────────────────────────────────────────


async def get_absence_reason_svc(
    session: AsyncSession = Depends(get_session),
) -> AbsenceReasonService:
    return AbsenceReasonService(session)


async def get_period_attendance_svc(
    session: AsyncSession = Depends(get_session),
) -> PeriodAttendanceService:
    return PeriodAttendanceService(session)


async def get_correction_svc(
    session: AsyncSession = Depends(get_session),
) -> AttendanceCorrectionService:
    return AttendanceCorrectionService(session)


async def get_threshold_svc(
    session: AsyncSession = Depends(get_session),
) -> AttendanceThresholdService:
    return AttendanceThresholdService(session)


async def get_analytics_svc(
    session: AsyncSession = Depends(get_session),
) -> AttendanceAnalyticsService:
    return AttendanceAnalyticsService(session)


# ═══════════════════════════════════════════════════════════════════════
# ABSENCE REASONS
# ═══════════════════════════════════════════════════════════════════════


@router.post("/absence-reasons", response_model=AbsenceReasonResponse, status_code=status.HTTP_201_CREATED)
async def create_absence_reason(
    data: AbsenceReasonCreate,
    svc: AbsenceReasonService = Depends(get_absence_reason_svc),
) -> AbsenceReasonResponse:
    return AbsenceReasonResponse.model_validate(await svc.create(data))


@router.get("/absence-reasons/{reason_id}", response_model=AbsenceReasonResponse)
async def get_absence_reason(
    reason_id: int,
    svc: AbsenceReasonService = Depends(get_absence_reason_svc),
) -> AbsenceReasonResponse:
    return AbsenceReasonResponse.model_validate(await svc.get(reason_id))


@router.get("/absence-reasons", response_model=AbsenceReasonPage)
async def list_absence_reasons(
    pagination: PaginationParams = Depends(),
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    requires_approval: Optional[bool] = Query(None, alias="requires_approval"),
    status: Optional[str] = Query(None, alias="status"),
    svc: AbsenceReasonService = Depends(get_absence_reason_svc),
) -> AbsenceReasonPage:
    items, total = await svc.list(
        campus_id=campus_id, requires_approval=requires_approval,
        status_filter=status, skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[AbsenceReasonResponse.model_validate(r) for r in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.patch("/absence-reasons/{reason_id}", response_model=AbsenceReasonResponse)
async def update_absence_reason(
    reason_id: int,
    data: AbsenceReasonUpdate,
    svc: AbsenceReasonService = Depends(get_absence_reason_svc),
) -> AbsenceReasonResponse:
    return AbsenceReasonResponse.model_validate(await svc.update(reason_id, data))


@router.delete("/absence-reasons/{reason_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_absence_reason(
    reason_id: int,
    svc: AbsenceReasonService = Depends(get_absence_reason_svc),
) -> None:
    await svc.delete(reason_id)


# ═══════════════════════════════════════════════════════════════════════
# PERIOD ATTENDANCE
# ═══════════════════════════════════════════════════════════════════════


@router.post("/period-attendance", response_model=PeriodAttendanceResponse, status_code=status.HTTP_201_CREATED)
async def create_period_attendance(
    data: PeriodAttendanceBatchCreate,
    svc: PeriodAttendanceService = Depends(get_period_attendance_svc),
) -> PeriodAttendanceResponse:
    return PeriodAttendanceResponse.model_validate(await svc.batch_create(data))


@router.get("/period-attendance/{period_id}", response_model=PeriodAttendanceResponse)
async def get_period_attendance(
    period_id: int,
    svc: PeriodAttendanceService = Depends(get_period_attendance_svc),
) -> PeriodAttendanceResponse:
    return PeriodAttendanceResponse.model_validate(await svc.get_period(period_id))


@router.get("/period-attendance", response_model=PeriodAttendancePage)
async def list_period_attendance(
    pagination: PaginationParams = Depends(),
    section_id: Optional[int] = Query(None, alias="section_id"),
    class_id: Optional[int] = Query(None, alias="class_id"),
    subject_id: Optional[int] = Query(None, alias="subject_id"),
    teacher_id: Optional[int] = Query(None, alias="teacher_id"),
    academic_year_id: Optional[int] = Query(None, alias="academic_year_id"),
    from_date: Optional[str] = Query(None, alias="from_date"),
    to_date: Optional[str] = Query(None, alias="to_date"),
    svc: PeriodAttendanceService = Depends(get_period_attendance_svc),
) -> PeriodAttendancePage:
    items, total = await svc.list_periods(
        section_id=section_id, class_id=class_id, subject_id=subject_id,
        teacher_id=teacher_id, academic_year_id=academic_year_id,
        from_date=from_date, to_date=to_date,
        skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[PeriodAttendanceResponse.model_validate(p) for p in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.patch("/period-attendance/records/{record_id}", response_model=PeriodAttendanceRecordResponse)
async def update_period_record(
    record_id: int,
    data: PeriodAttendanceRecordUpdate,
    svc: PeriodAttendanceService = Depends(get_period_attendance_svc),
) -> PeriodAttendanceRecordResponse:
    return PeriodAttendanceRecordResponse.model_validate(
        await svc.update_record(record_id, data)
    )


@router.get("/period-attendance/student/{student_id}", response_model=Page[PeriodAttendanceRecordResponse])
async def get_student_period_records(
    student_id: int,
    pagination: PaginationParams = Depends(),
    from_date: Optional[str] = Query(None, alias="from_date"),
    to_date: Optional[str] = Query(None, alias="to_date"),
    svc: PeriodAttendanceService = Depends(get_period_attendance_svc),
) -> Page[PeriodAttendanceRecordResponse]:
    items, total = await svc.get_student_records(
        student_id=student_id, from_date=from_date, to_date=to_date,
        skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[PeriodAttendanceRecordResponse.model_validate(r) for r in items],
        total=total, page=pagination.page, size=pagination.size,
    )


# ═══════════════════════════════════════════════════════════════════════
# ATTENDANCE CORRECTIONS
# ═══════════════════════════════════════════════════════════════════════


@router.post("/corrections", response_model=AttendanceCorrectionResponse, status_code=status.HTTP_201_CREATED)
async def create_correction(
    data: AttendanceCorrectionCreate,
    svc: AttendanceCorrectionService = Depends(get_correction_svc),
) -> AttendanceCorrectionResponse:
    return AttendanceCorrectionResponse.model_validate(
        await svc.create(data, requested_by=0)
    )


@router.get("/corrections/{correction_id}", response_model=AttendanceCorrectionResponse)
async def get_correction(
    correction_id: int,
    svc: AttendanceCorrectionService = Depends(get_correction_svc),
) -> AttendanceCorrectionResponse:
    return AttendanceCorrectionResponse.model_validate(await svc.get(correction_id))


@router.get("/corrections", response_model=AttendanceCorrectionPage)
async def list_corrections(
    pagination: PaginationParams = Depends(),
    status: Optional[str] = Query(None, alias="status"),
    record_type: Optional[str] = Query(None, alias="record_type"),
    requested_by: Optional[int] = Query(None, alias="requested_by"),
    svc: AttendanceCorrectionService = Depends(get_correction_svc),
) -> AttendanceCorrectionPage:
    items, total = await svc.list(
        status_filter=status, record_type=record_type,
        requested_by=requested_by, skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[AttendanceCorrectionResponse.model_validate(c) for c in items],
        total=total, page=pagination.page, size=pagination.size,
    )


class ReviewNotesBody(BaseModel):
    review_notes: Optional[str] = None


@router.post("/corrections/{correction_id}/approve", response_model=AttendanceCorrectionResponse)
async def approve_correction(
    correction_id: int,
    body: ReviewNotesBody = ReviewNotesBody(),
    svc: AttendanceCorrectionService = Depends(get_correction_svc),
) -> AttendanceCorrectionResponse:
    data = AttendanceCorrectionReview(status="approved", review_notes=body.review_notes)
    return AttendanceCorrectionResponse.model_validate(
        await svc.review(correction_id, data, reviewed_by=0)
    )


@router.post("/corrections/{correction_id}/decline", response_model=AttendanceCorrectionResponse)
async def decline_correction(
    correction_id: int,
    body: ReviewNotesBody = ReviewNotesBody(),
    svc: AttendanceCorrectionService = Depends(get_correction_svc),
) -> AttendanceCorrectionResponse:
    data = AttendanceCorrectionReview(status="declined", review_notes=body.review_notes)
    return AttendanceCorrectionResponse.model_validate(
        await svc.review(correction_id, data, reviewed_by=0)
    )


@router.delete("/corrections/{correction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_correction(
    correction_id: int,
    svc: AttendanceCorrectionService = Depends(get_correction_svc),
) -> None:
    await svc.delete(correction_id)


# ═══════════════════════════════════════════════════════════════════════
# ATTENDANCE THRESHOLDS
# ═══════════════════════════════════════════════════════════════════════


@router.post("/thresholds", response_model=AttendanceThresholdResponse, status_code=status.HTTP_201_CREATED)
async def create_threshold(
    data: AttendanceThresholdCreate,
    svc: AttendanceThresholdService = Depends(get_threshold_svc),
) -> AttendanceThresholdResponse:
    return AttendanceThresholdResponse.model_validate(await svc.create(data))


@router.get("/thresholds/{threshold_id}", response_model=AttendanceThresholdResponse)
async def get_threshold(
    threshold_id: int,
    svc: AttendanceThresholdService = Depends(get_threshold_svc),
) -> AttendanceThresholdResponse:
    return AttendanceThresholdResponse.model_validate(await svc.get(threshold_id))


@router.get("/thresholds", response_model=AttendanceThresholdPage)
async def list_thresholds(
    pagination: PaginationParams = Depends(),
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    academic_year_id: Optional[int] = Query(None, alias="academic_year_id"),
    threshold_type: Optional[str] = Query(None, alias="threshold_type"),
    status: Optional[str] = Query(None, alias="status"),
    svc: AttendanceThresholdService = Depends(get_threshold_svc),
) -> AttendanceThresholdPage:
    items, total = await svc.list(
        campus_id=campus_id, academic_year_id=academic_year_id,
        threshold_type=threshold_type, status_filter=status,
        skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[AttendanceThresholdResponse.model_validate(t) for t in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.patch("/thresholds/{threshold_id}", response_model=AttendanceThresholdResponse)
async def update_threshold(
    threshold_id: int,
    data: AttendanceThresholdUpdate,
    svc: AttendanceThresholdService = Depends(get_threshold_svc),
) -> AttendanceThresholdResponse:
    return AttendanceThresholdResponse.model_validate(await svc.update(threshold_id, data))


@router.delete("/thresholds/{threshold_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_threshold(
    threshold_id: int,
    svc: AttendanceThresholdService = Depends(get_threshold_svc),
) -> None:
    await svc.delete(threshold_id)


# ═══════════════════════════════════════════════════════════════════════
# ANALYTICS
# ═══════════════════════════════════════════════════════════════════════


@router.get("/analytics/student/{student_id}/trend", response_model=StudentAttendanceTrend)
async def get_student_trend(
    student_id: int,
    start_date: str = Query(alias="start_date"),
    end_date: str = Query(alias="end_date"),
    svc: AttendanceAnalyticsService = Depends(get_analytics_svc),
) -> StudentAttendanceTrend:
    return await svc.get_student_trend(student_id, start_date, end_date)


@router.get("/analytics/class/{class_id}/trend", response_model=ClassAttendanceTrend)
async def get_class_trend(
    class_id: int,
    start_date: str = Query(alias="start_date"),
    end_date: str = Query(alias="end_date"),
    svc: AttendanceAnalyticsService = Depends(get_analytics_svc),
) -> ClassAttendanceTrend:
    return await svc.get_class_trend(class_id, start_date, end_date)


@router.get("/analytics/section/{section_id}/trend", response_model=SectionAttendanceTrend)
async def get_section_trend(
    section_id: int,
    start_date: str = Query(alias="start_date"),
    end_date: str = Query(alias="end_date"),
    svc: AttendanceAnalyticsService = Depends(get_analytics_svc),
) -> SectionAttendanceTrend:
    return await svc.get_section_trend(section_id, start_date, end_date)


@router.get("/analytics/chronic-absenteeism", response_model=list[ChronicAbsenteeismRecord])
async def get_chronic_absenteeism(
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    academic_year_id: Optional[int] = Query(None, alias="academic_year_id"),
    threshold: float = Query(75.0, alias="threshold"),
    consecutive_days: int = Query(5, alias="consecutive_days"),
    limit: int = Query(50),
    svc: AttendanceAnalyticsService = Depends(get_analytics_svc),
) -> list[ChronicAbsenteeismRecord]:
    return await svc.get_chronic_absenteeism(
        campus_id=campus_id, academic_year_id=academic_year_id,
        threshold_pct=threshold, consecutive_days=consecutive_days, limit=limit,
    )


@router.get("/analytics/low-attendance-alerts", response_model=list[LowAttendanceAlertItem])
async def get_low_attendance_alerts(
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    academic_year_id: Optional[int] = Query(None, alias="academic_year_id"),
    svc: AttendanceAnalyticsService = Depends(get_analytics_svc),
) -> list[LowAttendanceAlertItem]:
    return await svc.get_low_attendance_alerts(
        campus_id=campus_id, academic_year_id=academic_year_id,
    )


@router.get("/dashboard", response_model=AttendanceIntelligenceDashboard)
async def get_dashboard(
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    academic_year_id: Optional[int] = Query(None, alias="academic_year_id"),
    today_date: Optional[str] = Query(None, alias="today_date"),
    svc: AttendanceAnalyticsService = Depends(get_analytics_svc),
) -> AttendanceIntelligenceDashboard:
    return await svc.get_dashboard(
        campus_id=campus_id, academic_year_id=academic_year_id,
        today_date=today_date,
    )
