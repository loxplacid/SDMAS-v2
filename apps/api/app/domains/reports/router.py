from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.dependencies import get_current_user, require_role
from app.domains.auth.models import User
from app.domains.reports.attendance_reports import AttendanceReportService
from app.domains.reports.batch_service import BatchService
from app.domains.reports.export_service import ExportService
from app.domains.reports.fee_reports import FeeReportService
from app.domains.reports.rollover_service import RolloverService
from app.domains.reports.schemas import (
    BatchEnrollInput,
    BatchEnrollResult,
    BatchFeeDueInput,
    BatchFeeDueResult,
    ClassAttendanceSummaryReport,
    CollectionReportItem,
    DetailedReceipt,
    OutstandingReportItem,
    RolloverExecuteInput,
    RolloverPreview,
    RolloverResult,
    SectionAttendanceSummaryReport,
)
from app.infrastructure.database import get_session

router = APIRouter(prefix="/api/reports", tags=["reports"])


# ---------------------------------------------------------------------------
# Attendance reports
# ---------------------------------------------------------------------------


@router.get(
    "/attendance/class/{class_id}",
    response_model=ClassAttendanceSummaryReport,
)
async def get_class_attendance_report(
    class_id: int,
    academic_year_id: int = Query(..., alias="academic_year_id"),
    start_date: Optional[str] = Query(default=None, alias="start_date"),
    end_date: Optional[str] = Query(default=None, alias="end_date"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
) -> ClassAttendanceSummaryReport:
    service = AttendanceReportService(session)
    report = await service.get_class_attendance_summary(
        class_id, academic_year_id, start_date, end_date
    )
    return ClassAttendanceSummaryReport(**report)


@router.get(
    "/attendance/section/{section_id}",
    response_model=SectionAttendanceSummaryReport,
)
async def get_section_attendance_report(
    section_id: int,
    start_date: Optional[str] = Query(default=None, alias="start_date"),
    end_date: Optional[str] = Query(default=None, alias="end_date"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
) -> SectionAttendanceSummaryReport:
    service = AttendanceReportService(session)
    report = await service.get_section_attendance_summary(
        section_id, start_date, end_date
    )
    return SectionAttendanceSummaryReport(**report)


# ---------------------------------------------------------------------------
# Fee reports
# ---------------------------------------------------------------------------


@router.get(
    "/fees/collection",
    response_model=list[CollectionReportItem],
)
async def get_collection_report(
    academic_year_id: int = Query(..., alias="academic_year_id"),
    start_date: Optional[str] = Query(default=None, alias="start_date"),
    end_date: Optional[str] = Query(default=None, alias="end_date"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
) -> list[CollectionReportItem]:
    service = FeeReportService(session)
    report = await service.get_collection_report(
        academic_year_id, start_date, end_date
    )
    return [CollectionReportItem(**r) for r in report]


@router.get(
    "/fees/outstanding",
    response_model=list[OutstandingReportItem],
)
async def get_outstanding_report(
    academic_year_id: int = Query(..., alias="academic_year_id"),
    class_id: Optional[int] = Query(default=None, alias="class_id"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
) -> list[OutstandingReportItem]:
    service = FeeReportService(session)
    report = await service.get_outstanding_report(academic_year_id, class_id)
    return [OutstandingReportItem(**r) for r in report]


@router.get(
    "/receipts/{payment_id}",
    response_model=DetailedReceipt,
)
async def get_detailed_receipt(
    payment_id: int,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
) -> DetailedReceipt:
    service = FeeReportService(session)
    receipt = await service.get_detailed_receipt(payment_id)
    return DetailedReceipt(**receipt)


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


@router.get("/export/students")
async def export_students(
    status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
):
    service = ExportService(session)
    return await service.export_students_csv(status=status, search=search)


@router.get("/export/attendance")
async def export_attendance(
    section_id: Optional[int] = Query(default=None, alias="section_id"),
    start_date: Optional[str] = Query(default=None, alias="start_date"),
    end_date: Optional[str] = Query(default=None, alias="end_date"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
):
    service = ExportService(session)
    return await service.export_attendance_csv(
        section_id=section_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/export/payments")
async def export_payments(
    academic_year_id: Optional[int] = Query(
        default=None, alias="academic_year_id"
    ),
    start_date: Optional[str] = Query(default=None, alias="start_date"),
    end_date: Optional[str] = Query(default=None, alias="end_date"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
):
    service = ExportService(session)
    return await service.export_payments_csv(
        academic_year_id=academic_year_id,
        start_date=start_date,
        end_date=end_date,
    )


# ---------------------------------------------------------------------------
# Academic year rollover
# ---------------------------------------------------------------------------


@router.post("/rollover/preview", response_model=RolloverPreview)
async def preview_rollover(
    data: RolloverExecuteInput,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
) -> RolloverPreview:
    service = RolloverService(session)
    preview = await service.preview_rollover(
        from_year_id=data.from_year_id,
        to_year_name=data.to_year_name,
        to_start_date=data.to_start_date,
        to_end_date=data.to_end_date,
    )
    return RolloverPreview(**preview)


@router.post(
    "/rollover/execute",
    response_model=RolloverResult,
    status_code=status.HTTP_201_CREATED,
)
async def execute_rollover(
    data: RolloverExecuteInput,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
) -> RolloverResult:
    service = RolloverService(session)
    result = await service.execute_rollover(
        from_year_id=data.from_year_id,
        to_year_name=data.to_year_name,
        to_start_date=data.to_start_date,
        to_end_date=data.to_end_date,
    )
    return RolloverResult(**result)


# ---------------------------------------------------------------------------
# Batch operations
# ---------------------------------------------------------------------------


@router.post(
    "/batch/enroll",
    response_model=BatchEnrollResult,
    status_code=status.HTTP_201_CREATED,
)
async def batch_enroll(
    data: BatchEnrollInput,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
) -> BatchEnrollResult:
    service = BatchService(session)
    enrollments_data = [e.model_dump() for e in data.enrollments]
    result = await service.batch_enroll(data.academic_year_id, enrollments_data)
    return BatchEnrollResult(**result)


@router.post(
    "/batch/fee-dues",
    response_model=BatchFeeDueResult,
    status_code=status.HTTP_201_CREATED,
)
async def batch_create_fee_dues(
    data: BatchFeeDueInput,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
) -> BatchFeeDueResult:
    service = BatchService(session)
    result = await service.batch_create_fee_dues(
        data.academic_year_id, data.student_ids
    )
    return BatchFeeDueResult(**result)