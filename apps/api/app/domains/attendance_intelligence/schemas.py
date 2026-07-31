from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.pagination import Page

# ── Constants ──────────────────────────────────────────────────────────

VALID_ATTENDANCE_STATUSES = {"present", "absent", "late", "excused"}
VALID_THRESHOLD_TYPES = {"warning", "critical", "chronic"}
VALID_CORRECTION_STATUSES = {"pending", "approved", "declined"}
VALID_RECORD_TYPES = {"daily", "period"}


# ── Absence Reasons ────────────────────────────────────────────────────


class AbsenceReasonCreate(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    requires_approval: bool = False
    campus_id: Optional[int] = None
    status: str = "active"


class AbsenceReasonUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    requires_approval: Optional[bool] = None
    status: Optional[str] = None


class AbsenceReasonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: Optional[str] = None
    requires_approval: bool = False
    campus_id: Optional[int] = None
    status: str
    created_at: datetime.datetime


AbsenceReasonPage = Page[AbsenceReasonResponse]


# ── Period Attendance ──────────────────────────────────────────────────


class PeriodAttendanceRecordCreate(BaseModel):
    student_id: int
    status: str = "present"
    arrival_time: Optional[str] = None
    departure_time: Optional[str] = None
    late_minutes: Optional[int] = None
    early_departure_minutes: Optional[int] = None
    absence_reason_id: Optional[int] = None
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_ATTENDANCE_STATUSES:
            raise ValueError(
                f"Invalid status. Must be one of: {', '.join(sorted(VALID_ATTENDANCE_STATUSES))}"
            )
        return v


class PeriodAttendanceCreate(BaseModel):
    academic_year_id: int
    class_id: int
    section_id: int
    subject_id: int
    teacher_id: int
    attendance_date: str
    period_number: int
    start_time: str
    end_time: str
    campus_id: Optional[int] = None
    notes: Optional[str] = None

    @field_validator("attendance_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Attendance date is required")
        return v.strip()


class PeriodAttendanceBatchCreate(BaseModel):
    attendance: PeriodAttendanceCreate
    records: list[PeriodAttendanceRecordCreate]


class PeriodAttendanceRecordUpdate(BaseModel):
    status: Optional[str] = None
    arrival_time: Optional[str] = None
    departure_time: Optional[str] = None
    late_minutes: Optional[int] = None
    early_departure_minutes: Optional[int] = None
    absence_reason_id: Optional[int] = None
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_ATTENDANCE_STATUSES:
            raise ValueError(
                f"Invalid status. Must be one of: {', '.join(sorted(VALID_ATTENDANCE_STATUSES))}"
            )
        return v


class PeriodAttendanceRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    period_attendance_id: int
    student_id: int
    status: str
    arrival_time: Optional[str] = None
    departure_time: Optional[str] = None
    late_minutes: Optional[int] = None
    early_departure_minutes: Optional[int] = None
    absence_reason_id: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class PeriodAttendanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    academic_year_id: int
    class_id: int
    section_id: int
    subject_id: int
    teacher_id: int
    attendance_date: str
    period_number: int
    start_time: str
    end_time: str
    campus_id: Optional[int] = None
    status: str
    notes: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    records: list[PeriodAttendanceRecordResponse] = []


PeriodAttendancePage = Page[PeriodAttendanceResponse]


# ── Attendance Corrections ─────────────────────────────────────────────


class AttendanceCorrectionCreate(BaseModel):
    record_type: str
    record_id: int
    requested_status: str
    absence_reason_id: Optional[int] = None
    reason: Optional[str] = None
    campus_id: Optional[int] = None

    @field_validator("record_type")
    @classmethod
    def validate_record_type(cls, v: str) -> str:
        if v not in VALID_RECORD_TYPES:
            raise ValueError(
                f"Invalid record type. Must be one of: {', '.join(VALID_RECORD_TYPES)}"
            )
        return v

    @field_validator("requested_status")
    @classmethod
    def validate_requested_status(cls, v: str) -> str:
        if v not in VALID_ATTENDANCE_STATUSES:
            raise ValueError(
                f"Invalid status. Must be one of: {', '.join(sorted(VALID_ATTENDANCE_STATUSES))}"
            )
        return v


class AttendanceCorrectionUpdate(BaseModel):
    reason: Optional[str] = None
    absence_reason_id: Optional[int] = None


class AttendanceCorrectionReview(BaseModel):
    status: str
    review_notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in {"approved", "declined"}:
            raise ValueError("Review status must be 'approved' or 'declined'")
        return v


class AttendanceCorrectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    record_type: str
    record_id: int
    requested_by: int
    requested_status: str
    previous_status: Optional[str] = None
    absence_reason_id: Optional[int] = None
    reason: Optional[str] = None
    status: str
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime.datetime] = None
    review_notes: Optional[str] = None
    campus_id: Optional[int] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


AttendanceCorrectionPage = Page[AttendanceCorrectionResponse]


# ── Attendance Thresholds ──────────────────────────────────────────────


class AttendanceThresholdCreate(BaseModel):
    campus_id: Optional[int] = None
    academic_year_id: Optional[int] = None
    name: str
    threshold_type: str
    percentage: float
    days_absent_threshold: Optional[int] = None
    consecutive_absences: Optional[int] = None
    notification_enabled: bool = True
    notification_channels: Optional[str] = "in_app"
    applies_to: Optional[str] = None
    status: str = "active"

    @field_validator("threshold_type")
    @classmethod
    def validate_threshold_type(cls, v: str) -> str:
        if v not in VALID_THRESHOLD_TYPES:
            raise ValueError(
                f"Invalid threshold type. Must be one of: {', '.join(VALID_THRESHOLD_TYPES)}"
            )
        return v


class AttendanceThresholdUpdate(BaseModel):
    name: Optional[str] = None
    threshold_type: Optional[str] = None
    percentage: Optional[float] = None
    days_absent_threshold: Optional[int] = None
    consecutive_absences: Optional[int] = None
    notification_enabled: Optional[bool] = None
    notification_channels: Optional[str] = None
    applies_to: Optional[str] = None
    status: Optional[str] = None


class AttendanceThresholdResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    academic_year_id: Optional[int] = None
    name: str
    threshold_type: str
    percentage: float
    days_absent_threshold: Optional[int] = None
    consecutive_absences: Optional[int] = None
    notification_enabled: bool
    notification_channels: Optional[str] = None
    applies_to: Optional[str] = None
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


AttendanceThresholdPage = Page[AttendanceThresholdResponse]


# ── Analytics Schemas ──────────────────────────────────────────────────


class StudentAttendanceTrendPoint(BaseModel):
    date: str
    status: str
    period_number: Optional[int] = None


class StudentAttendanceTrend(BaseModel):
    student_id: int
    start_date: str
    end_date: str
    trend: list[StudentAttendanceTrendPoint]
    total_periods: int
    present_count: int
    absent_count: int
    late_count: int
    excused_count: int
    attendance_percentage: float
    late_arrivals: int
    early_departures: int


class ClassAttendanceTrend(BaseModel):
    class_id: int
    start_date: str
    end_date: str
    total_students: int
    total_periods: int
    average_attendance_percentage: float
    present_count: int
    absent_count: int
    late_count: int
    excused_count: int


class SectionAttendanceTrend(BaseModel):
    section_id: int
    class_id: int
    start_date: str
    end_date: str
    total_students: int
    total_periods: int
    average_attendance_percentage: float
    present_count: int
    absent_count: int
    late_count: int
    excused_count: int


class ChronicAbsenteeismRecord(BaseModel):
    student_id: int
    student_name: Optional[str] = None
    student_number: Optional[str] = None
    section_id: Optional[int] = None
    section_name: Optional[str] = None
    class_id: Optional[int] = None
    class_name: Optional[str] = None
    total_periods: int
    absent_count: int
    attendance_percentage: float
    consecutive_absences: int
    threshold: float
    threshold_name: str


class LowAttendanceAlertItem(BaseModel):
    student_id: int
    student_name: Optional[str] = None
    student_number: Optional[str] = None
    section_id: Optional[int] = None
    section_name: Optional[str] = None
    attendance_percentage: float
    threshold: float
    threshold_name: str
    total_absences: int


class AttendanceIntelligenceDashboard(BaseModel):
    total_students: int
    overall_attendance_percentage: float
    present_today: int
    absent_today: int
    late_today: int
    chronic_count: int
    low_attendance_alerts: list[LowAttendanceAlertItem]
    top_absenteeism: list[ChronicAbsenteeismRecord]
