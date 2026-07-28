from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.pagination import Page

VALID_ATTENDANCE_STATUSES = {"present", "absent", "late", "excused"}


def validate_status(v: str) -> str:
    if v not in VALID_ATTENDANCE_STATUSES:
        raise ValueError(
            f"Invalid attendance status. Must be one of: {', '.join(sorted(VALID_ATTENDANCE_STATUSES))}"
        )
    return v


# ---------------------------------------------------------------------------
# AttendanceRecord
# ---------------------------------------------------------------------------


class AttendanceRecordCreate(BaseModel):
    student_id: int
    academic_year_id: int
    class_id: int
    section_id: int
    attendance_date: str
    status: str
    notes: Optional[str] = None

    @field_validator("attendance_date")
    @classmethod
    def date_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Attendance date is required")
        return stripped

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        return validate_status(v)


class DailyAttendanceItem(BaseModel):
    student_id: int
    status: str
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        return validate_status(v)


class DailyAttendanceCreate(BaseModel):
    section_id: int
    attendance_date: str
    records: list[DailyAttendanceItem]

    @field_validator("attendance_date")
    @classmethod
    def date_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Date is required")
        return stripped

    @field_validator("records")
    @classmethod
    def records_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("Attendance records must be a non-empty array")
        return v


class AttendanceRecordUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_status(v)


class AttendanceRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    academic_year_id: int
    class_id: int
    section_id: int
    attendance_date: str
    status: str
    notes: Optional[str] = None
    recorded_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# Summary schemas
# ---------------------------------------------------------------------------


class StudentAttendanceSummary(BaseModel):
    student_id: int
    start_date: str
    end_date: str
    total: int
    present: int
    absent: int
    late: int
    excused: int
    percentage: float


class SectionAttendanceSummary(BaseModel):
    section_id: int
    attendance_date: str
    total_students: int
    total_marked: int
    present: int
    absent: int
    late: int
    excused: int
    present_percentage: float


# ---------------------------------------------------------------------------
# Paginated response
# ---------------------------------------------------------------------------

AttendanceRecordPage = Page[AttendanceRecordResponse]