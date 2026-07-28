from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Attendance reports
# ---------------------------------------------------------------------------


class ClassAttendanceSummaryReport(BaseModel):
    class_id: int
    class_name: str
    academic_year_id: int
    total_students: int
    total_records: int
    present: int
    absent: int
    late: int
    excused: int
    present_percentage: float


class SectionAttendanceSummaryReport(BaseModel):
    section_id: int
    section_name: str
    class_id: int
    class_name: str
    total_students: int
    total_records: int
    present: int
    absent: int
    late: int
    excused: int
    present_percentage: float


class AttendanceOverviewReport(BaseModel):
    academic_year_id: int
    total_classes: int
    total_sections: int
    total_students: int
    total_records: int
    present: int
    absent: int
    late: int
    excused: int
    overall_present_percentage: float


# ---------------------------------------------------------------------------
# Fee reports
# ---------------------------------------------------------------------------


class CollectionReportItem(BaseModel):
    class_id: int
    class_name: str
    total_students: int
    total_fees_assigned: int
    total_collected: int
    total_outstanding: int
    collection_percentage: float


class OutstandingReportItem(BaseModel):
    student_id: int
    student_name: str
    student_number: str
    class_name: str
    total_fees: int
    total_paid: int
    outstanding: int
    due_count: int
    unpaid_count: int
    partially_paid_count: int


class DetailedReceipt(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    payment_id: int
    receipt_number: Optional[str] = None
    student_id: int
    student_name: str
    student_number: str
    fee_due_id: int
    amount: int
    payment_date: Optional[str] = None
    payment_method: Optional[str] = None
    academic_year_name: str
    fee_type_name: str
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# Rollover
# ---------------------------------------------------------------------------


class RolloverPreviewItem(BaseModel):
    type: str
    name: str
    source_id: int


class RolloverPreview(BaseModel):
    from_year_id: int
    from_year_name: str
    to_year_name: str
    classes: list[RolloverPreviewItem]
    sections: list[RolloverPreviewItem]
    enrolled_students: int
    total_items: int


class RolloverExecuteInput(BaseModel):
    from_year_id: int
    to_year_name: str
    to_start_date: str
    to_end_date: str


class RolloverResult(BaseModel):
    success: bool
    academic_year_id: int
    academic_year_name: str
    classes_created: int
    sections_created: int
    enrollments_created: int
    message: str


# ---------------------------------------------------------------------------
# Batch operations
# ---------------------------------------------------------------------------


class BatchEnrollItem(BaseModel):
    student_id: int
    class_id: int
    section_id: Optional[int] = None


class BatchEnrollInput(BaseModel):
    academic_year_id: int
    enrollments: list[BatchEnrollItem]


class BatchEnrollResultItem(BaseModel):
    student_id: int
    success: bool
    enrollment_id: Optional[int] = None
    error: Optional[str] = None


class BatchEnrollResult(BaseModel):
    academic_year_id: int
    total: int
    succeeded: int
    failed: int
    results: list[BatchEnrollResultItem]


class BatchFeeDueInput(BaseModel):
    academic_year_id: int
    student_ids: list[int]


class BatchFeeDueResultItem(BaseModel):
    student_id: int
    success: bool
    dues_created: int
    error: Optional[str] = None


class BatchFeeDueResult(BaseModel):
    academic_year_id: int
    total: int
    succeeded: int
    failed: int
    results: list[BatchFeeDueResultItem]


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


class StudentCsvRow(BaseModel):
    student_number: str
    first_name: str
    last_name: str
    email: str
    date_of_birth: str
    status: str


class AttendanceCsvRow(BaseModel):
    student_number: str
    student_name: str
    attendance_date: str
    status: str
    notes: str
    section_name: str
    class_name: str


class PaymentCsvRow(BaseModel):
    receipt_number: str
    student_number: str
    student_name: str
    amount: int
    payment_date: str
    payment_method: str
    fee_type_name: str
    academic_year_name: str