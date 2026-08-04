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
from app.domains.auth.dependencies import require_permission
from app.domains.auth.models import User
from app.domains.auth.permissions import (
    ATTENDANCE_APPROVE,
    ATTENDANCE_RECORD,
    ATTENDANCE_UPDATE,
    ATTENDANCE_VIEW,
)
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.guards import assert_tenant_scope, effective_campus_id
from app.multi_tenant.models import TenantContext

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
    _actor: User = Depends(require_permission(ATTENDANCE_UPDATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AbsenceReasonResponse:
    reason = await svc.create(data)
    from app.multi_tenant.guards import inject_campus
    inject_campus(reason, tenant)
    return AbsenceReasonResponse.model_validate(reason)


@router.get("/absence-reasons/{reason_id}", response_model=AbsenceReasonResponse)
async def get_absence_reason(
    reason_id: int,
    svc: AbsenceReasonService = Depends(get_absence_reason_svc),
    _actor: User = Depends(require_permission(ATTENDANCE_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AbsenceReasonResponse:
    reason = await svc.get(reason_id)
    assert_tenant_scope(reason, tenant, resource="absence reason")
    return AbsenceReasonResponse.model_validate(reason)


@router.get("/absence-reasons", response_model=AbsenceReasonPage)
async def list_absence_reasons(
    pagination: PaginationParams = Depends(),
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    requires_approval: Optional[bool] = Query(None, alias="requires_approval"),
    status: Optional[str] = Query(None, alias="status"),
    svc: AbsenceReasonService = Depends(get_absence_reason_svc),
    _actor: User = Depends(require_permission(ATTENDANCE_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AbsenceReasonPage:
    items, total = await svc.list(
        campus_id=effective_campus_id(tenant, campus_id), requires_approval=requires_approval,
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
    _actor: User = Depends(require_permission(ATTENDANCE_UPDATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AbsenceReasonResponse:
    existing = await svc.get(reason_id)
    assert_tenant_scope(existing, tenant, resource="absence reason")
    return AbsenceReasonResponse.model_validate(await svc.update(reason_id, data))


@router.delete("/absence-reasons/{reason_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_absence_reason(
    reason_id: int,
    svc: AbsenceReasonService = Depends(get_absence_reason_svc),
    _actor: User = Depends(require_permission(ATTENDANCE_UPDATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    existing = await svc.get(reason_id)
    assert_tenant_scope(existing, tenant, resource="absence reason")
    await svc.delete(reason_id)


# ═══════════════════════════════════════════════════════════════════════
# PERIOD ATTENDANCE
# ═══════════════════════════════════════════════════════════════════════


@router.post("/period-attendance", response_model=PeriodAttendanceResponse, status_code=status.HTTP_201_CREATED)
async def create_period_attendance(
    data: PeriodAttendanceBatchCreate,
    svc: PeriodAttendanceService = Depends(get_period_attendance_svc),
    _actor: User = Depends(require_permission(ATTENDANCE_RECORD)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> PeriodAttendanceResponse:
    period = await svc.batch_create(data)
    from app.multi_tenant.guards import inject_campus
    inject_campus(period, tenant)
    return PeriodAttendanceResponse.model_validate(period)


@router.get("/period-attendance/{period_id}", response_model=PeriodAttendanceResponse)
async def get_period_attendance(
    period_id: int,
    svc: PeriodAttendanceService = Depends(get_period_attendance_svc),
    _actor: User = Depends(require_permission(ATTENDANCE_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> PeriodAttendanceResponse:
    period = await svc.get_period(period_id)
    assert_tenant_scope(period, tenant, resource="period attendance")
    return PeriodAttendanceResponse.model_validate(period)


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
    _actor: User = Depends(require_permission(ATTENDANCE_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> PeriodAttendancePage:
    items, total = await svc.list_periods(
        section_id=section_id, class_id=class_id, subject_id=subject_id,
        teacher_id=teacher_id, academic_year_id=academic_year_id,
        from_date=from_date, to_date=to_date,
        campus_id=effective_campus_id(tenant, None),
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
    _actor: User = Depends(require_permission(ATTENDANCE_UPDATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> PeriodAttendanceRecordResponse:
    record = await svc.get_record(record_id)
    assert_tenant_scope(record.period_attendance, tenant, resource="period attendance record")
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
    _actor: User = Depends(require_permission(ATTENDANCE_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> Page[PeriodAttendanceRecordResponse]:
    items, total = await svc.get_student_records(
        student_id=student_id, from_date=from_date, to_date=to_date,
        campus_id=effective_campus_id(tenant, None),
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
    actor: User = Depends(require_permission(ATTENDANCE_RECORD)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AttendanceCorrectionResponse:
    correction = await svc.create(data, requested_by=actor.id)
    from app.multi_tenant.guards import inject_campus
    inject_campus(correction, tenant)
    return AttendanceCorrectionResponse.model_validate(correction)


@router.get("/corrections/{correction_id}", response_model=AttendanceCorrectionResponse)
async def get_correction(
    correction_id: int,
    svc: AttendanceCorrectionService = Depends(get_correction_svc),
    _actor: User = Depends(require_permission(ATTENDANCE_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AttendanceCorrectionResponse:
    correction = await svc.get(correction_id)
    assert_tenant_scope(correction, tenant, resource="attendance correction")
    return AttendanceCorrectionResponse.model_validate(correction)


@router.get("/corrections", response_model=AttendanceCorrectionPage)
async def list_corrections(
    pagination: PaginationParams = Depends(),
    status: Optional[str] = Query(None, alias="status"),
    record_type: Optional[str] = Query(None, alias="record_type"),
    requested_by: Optional[int] = Query(None, alias="requested_by"),
    svc: AttendanceCorrectionService = Depends(get_correction_svc),
    _actor: User = Depends(require_permission(ATTENDANCE_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AttendanceCorrectionPage:
    items, total = await svc.list(
        status_filter=status, record_type=record_type,
        requested_by=requested_by, campus_id=effective_campus_id(tenant, None),
        skip=pagination.offset, limit=pagination.limit,
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
    actor: User = Depends(require_permission(ATTENDANCE_APPROVE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AttendanceCorrectionResponse:
    existing = await svc.get(correction_id)
    assert_tenant_scope(existing, tenant, resource="attendance correction")
    data = AttendanceCorrectionReview(status="approved", review_notes=body.review_notes)
    return AttendanceCorrectionResponse.model_validate(
        await svc.review(correction_id, data, reviewed_by=actor.id)
    )


@router.post("/corrections/{correction_id}/decline", response_model=AttendanceCorrectionResponse)
async def decline_correction(
    correction_id: int,
    body: ReviewNotesBody = ReviewNotesBody(),
    svc: AttendanceCorrectionService = Depends(get_correction_svc),
    actor: User = Depends(require_permission(ATTENDANCE_APPROVE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AttendanceCorrectionResponse:
    existing = await svc.get(correction_id)
    assert_tenant_scope(existing, tenant, resource="attendance correction")
    data = AttendanceCorrectionReview(status="declined", review_notes=body.review_notes)
    return AttendanceCorrectionResponse.model_validate(
        await svc.review(correction_id, data, reviewed_by=actor.id)
    )


@router.delete("/corrections/{correction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_correction(
    correction_id: int,
    svc: AttendanceCorrectionService = Depends(get_correction_svc),
    _actor: User = Depends(require_permission(ATTENDANCE_UPDATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    existing = await svc.get(correction_id)
    assert_tenant_scope(existing, tenant, resource="attendance correction")
    await svc.delete(correction_id)


# ═══════════════════════════════════════════════════════════════════════
# ATTENDANCE THRESHOLDS
# ═══════════════════════════════════════════════════════════════════════


@router.post("/thresholds", response_model=AttendanceThresholdResponse, status_code=status.HTTP_201_CREATED)
async def create_threshold(
    data: AttendanceThresholdCreate,
    svc: AttendanceThresholdService = Depends(get_threshold_svc),
    _actor: User = Depends(require_permission(ATTENDANCE_APPROVE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AttendanceThresholdResponse:
    threshold = await svc.create(data)
    from app.multi_tenant.guards import inject_campus
    inject_campus(threshold, tenant)
    return AttendanceThresholdResponse.model_validate(threshold)


@router.get("/thresholds/{threshold_id}", response_model=AttendanceThresholdResponse)
async def get_threshold(
    threshold_id: int,
    svc: AttendanceThresholdService = Depends(get_threshold_svc),
    _actor: User = Depends(require_permission(ATTENDANCE_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AttendanceThresholdResponse:
    threshold = await svc.get(threshold_id)
    assert_tenant_scope(threshold, tenant, resource="attendance threshold")
    return AttendanceThresholdResponse.model_validate(threshold)


@router.get("/thresholds", response_model=AttendanceThresholdPage)
async def list_thresholds(
    pagination: PaginationParams = Depends(),
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    academic_year_id: Optional[int] = Query(None, alias="academic_year_id"),
    threshold_type: Optional[str] = Query(None, alias="threshold_type"),
    status: Optional[str] = Query(None, alias="status"),
    svc: AttendanceThresholdService = Depends(get_threshold_svc),
    _actor: User = Depends(require_permission(ATTENDANCE_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AttendanceThresholdPage:
    items, total = await svc.list(
        campus_id=effective_campus_id(tenant, campus_id), academic_year_id=academic_year_id,
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
    _actor: User = Depends(require_permission(ATTENDANCE_APPROVE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AttendanceThresholdResponse:
    existing = await svc.get(threshold_id)
    assert_tenant_scope(existing, tenant, resource="attendance threshold")
    return AttendanceThresholdResponse.model_validate(await svc.update(threshold_id, data))


@router.delete("/thresholds/{threshold_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_threshold(
    threshold_id: int,
    svc: AttendanceThresholdService = Depends(get_threshold_svc),
    _actor: User = Depends(require_permission(ATTENDANCE_APPROVE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    existing = await svc.get(threshold_id)
    assert_tenant_scope(existing, tenant, resource="attendance threshold")
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
    _actor: User = Depends(require_permission(ATTENDANCE_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> StudentAttendanceTrend:
    return await svc.get_student_trend(
        student_id, start_date, end_date, campus_id=effective_campus_id(tenant, None)
    )


@router.get("/analytics/class/{class_id}/trend", response_model=ClassAttendanceTrend)
async def get_class_trend(
    class_id: int,
    start_date: str = Query(alias="start_date"),
    end_date: str = Query(alias="end_date"),
    svc: AttendanceAnalyticsService = Depends(get_analytics_svc),
    _actor: User = Depends(require_permission(ATTENDANCE_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> ClassAttendanceTrend:
    return await svc.get_class_trend(
        class_id, start_date, end_date, campus_id=effective_campus_id(tenant, None)
    )


@router.get("/analytics/section/{section_id}/trend", response_model=SectionAttendanceTrend)
async def get_section_trend(
    section_id: int,
    start_date: str = Query(alias="start_date"),
    end_date: str = Query(alias="end_date"),
    svc: AttendanceAnalyticsService = Depends(get_analytics_svc),
    _actor: User = Depends(require_permission(ATTENDANCE_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> SectionAttendanceTrend:
    return await svc.get_section_trend(
        section_id, start_date, end_date, campus_id=effective_campus_id(tenant, None)
    )


@router.get("/analytics/chronic-absenteeism", response_model=list[ChronicAbsenteeismRecord])
async def get_chronic_absenteeism(
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    academic_year_id: Optional[int] = Query(None, alias="academic_year_id"),
    threshold: float = Query(75.0, alias="threshold"),
    consecutive_days: int = Query(5, alias="consecutive_days"),
    limit: int = Query(50),
    svc: AttendanceAnalyticsService = Depends(get_analytics_svc),
    _actor: User = Depends(require_permission(ATTENDANCE_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[ChronicAbsenteeismRecord]:
    return await svc.get_chronic_absenteeism(
        campus_id=effective_campus_id(tenant, campus_id), academic_year_id=academic_year_id,
        threshold_pct=threshold, consecutive_days=consecutive_days, limit=limit,
    )


@router.get("/analytics/low-attendance-alerts", response_model=list[LowAttendanceAlertItem])
async def get_low_attendance_alerts(
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    academic_year_id: Optional[int] = Query(None, alias="academic_year_id"),
    svc: AttendanceAnalyticsService = Depends(get_analytics_svc),
    _actor: User = Depends(require_permission(ATTENDANCE_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[LowAttendanceAlertItem]:
    return await svc.get_low_attendance_alerts(
        campus_id=effective_campus_id(tenant, campus_id), academic_year_id=academic_year_id,
    )


@router.get("/dashboard", response_model=AttendanceIntelligenceDashboard)
async def get_dashboard(
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    academic_year_id: Optional[int] = Query(None, alias="academic_year_id"),
    today_date: Optional[str] = Query(None, alias="today_date"),
    svc: AttendanceAnalyticsService = Depends(get_analytics_svc),
    _actor: User = Depends(require_permission(ATTENDANCE_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AttendanceIntelligenceDashboard:
    return await svc.get_dashboard(
        campus_id=effective_campus_id(tenant, campus_id), academic_year_id=academic_year_id,
        today_date=today_date,
    )
