from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.pagination import Page
from app.domains.academic.schemas import validate_name_not_empty, validate_optional_status

VALID_ROOM_TYPES = {"classroom", "laboratory", "auditorium", "conference", "office", "gym", "library", "workshop"}
VALID_SLOT_TYPES = {"regular", "break", "assembly", "lab", "remedial", "club"}
VALID_SUBSTITUTION_STATUSES = {"pending", "approved", "declined", "cancelled"}
VALID_EXAM_STATUSES = {"scheduled", "in_progress", "completed", "cancelled", "postponed"}

DAYS_OF_WEEK = [
    (0, "Monday"), (1, "Tuesday"), (2, "Wednesday"),
    (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday"),
]


def validate_time_format(v: str) -> str:
    if not v or len(v) != 5 or v[2] != ":":
        raise ValueError("Time must be in HH:MM format")
    try:
        h, m = v.split(":")
        h_int, m_int = int(h), int(m)
        if not (0 <= h_int <= 23 and 0 <= m_int <= 59):
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError("Time must be in HH:MM format with valid hours (0-23) and minutes (0-59)")
    return v


# ── Room ────────────────────────────────────────────────────────────────

class RoomCreate(BaseModel):
    name: str
    code: str
    building: Optional[str] = None
    floor: Optional[str] = None
    capacity: int = 30
    room_type: str = "classroom"

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        return validate_name_not_empty(v)

    @field_validator("code")
    @classmethod
    def code_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Room code cannot be empty")
        return stripped.upper()

    @field_validator("capacity")
    @classmethod
    def capacity_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Capacity must be at least 1")
        return v

    @field_validator("room_type")
    @classmethod
    def validate_room_type(cls, v: str) -> str:
        if v not in VALID_ROOM_TYPES:
            raise ValueError(f"Invalid room type. Must be one of: {', '.join(sorted(VALID_ROOM_TYPES))}")
        return v


class RoomUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[str] = None
    capacity: Optional[int] = None
    room_type: Optional[str] = None
    status: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return v
        return validate_name_not_empty(v)

    @field_validator("code")
    @classmethod
    def code_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return v
        stripped = v.strip()
        if not stripped:
            raise ValueError("Room code cannot be empty")
        return stripped.upper()

    @field_validator("capacity")
    @classmethod
    def capacity_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is None: return v
        if v < 1:
            raise ValueError("Capacity must be at least 1")
        return v

    @field_validator("room_type")
    @classmethod
    def validate_room_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return v
        if v not in VALID_ROOM_TYPES:
            raise ValueError(f"Invalid room type. Must be one of: {', '.join(sorted(VALID_ROOM_TYPES))}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        return validate_optional_status(v)


class RoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    code: str
    building: Optional[str] = None
    floor: Optional[str] = None
    capacity: int
    room_type: str
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ── TimeSlot ────────────────────────────────────────────────────────────

class TimeSlotCreate(BaseModel):
    name: str
    day_of_week: int
    start_time: str
    end_time: str
    slot_type: str = "regular"

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        return validate_name_not_empty(v)

    @field_validator("day_of_week")
    @classmethod
    def validate_day(cls, v: int) -> int:
        if v < 0 or v > 6:
            raise ValueError("day_of_week must be 0 (Monday) through 6 (Sunday)")
        return v

    @field_validator("start_time")
    @classmethod
    def start_time_valid(cls, v: str) -> str:
        return validate_time_format(v)

    @field_validator("end_time")
    @classmethod
    def end_time_valid(cls, v: str) -> str:
        return validate_time_format(v)

    @field_validator("slot_type")
    @classmethod
    def validate_slot_type(cls, v: str) -> str:
        if v not in VALID_SLOT_TYPES:
            raise ValueError(f"Invalid slot type. Must be one of: {', '.join(sorted(VALID_SLOT_TYPES))}")
        return v


class TimeSlotUpdate(BaseModel):
    name: Optional[str] = None
    day_of_week: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    slot_type: Optional[str] = None
    status: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return v
        return validate_name_not_empty(v)

    @field_validator("day_of_week")
    @classmethod
    def validate_day(cls, v: Optional[int]) -> Optional[int]:
        if v is None: return v
        if v < 0 or v > 6:
            raise ValueError("day_of_week must be 0 (Monday) through 6 (Sunday)")
        return v

    @field_validator("start_time", "end_time")
    @classmethod
    def time_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return v
        return validate_time_format(v)

    @field_validator("slot_type")
    @classmethod
    def validate_slot_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return v
        if v not in VALID_SLOT_TYPES:
            raise ValueError(f"Invalid slot type. Must be one of: {', '.join(sorted(VALID_SLOT_TYPES))}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        return validate_optional_status(v)


class TimeSlotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    day_of_week: int
    start_time: str
    end_time: str
    slot_type: str
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ── TimetableEntry ─────────────────────────────────────────────────────

class TimetableEntryCreate(BaseModel):
    academic_year_id: int
    term_id: Optional[int] = None
    class_id: int
    section_id: Optional[int] = None
    subject_id: int
    teacher_id: int
    room_id: Optional[int] = None
    time_slot_id: int
    day_of_week: int

    @field_validator("day_of_week")
    @classmethod
    def validate_day(cls, v: int) -> int:
        if v < 0 or v > 6:
            raise ValueError("day_of_week must be 0 (Monday) through 6 (Sunday)")
        return v


class TimetableEntryUpdate(BaseModel):
    teacher_id: Optional[int] = None
    room_id: Optional[int] = None
    time_slot_id: Optional[int] = None
    day_of_week: Optional[int] = None
    status: Optional[str] = None

    @field_validator("day_of_week")
    @classmethod
    def validate_day(cls, v: Optional[int]) -> Optional[int]:
        if v is None: return v
        if v < 0 or v > 6:
            raise ValueError("day_of_week must be 0 (Monday) through 6 (Sunday)")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        return validate_optional_status(v)


class TimetableEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    academic_year_id: int
    term_id: Optional[int] = None
    class_id: int
    section_id: Optional[int] = None
    subject_id: int
    teacher_id: int
    room_id: Optional[int] = None
    time_slot_id: int
    day_of_week: int
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


class TimetableEntryDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    day_of_week: int
    status: str
    subject_name: Optional[str] = None
    teacher_name: Optional[str] = None
    room_name: Optional[str] = None
    class_name: Optional[str] = None
    section_name: Optional[str] = None
    time_slot_name: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


# ── Substitution ────────────────────────────────────────────────────────

class SubstitutionCreate(BaseModel):
    timetable_entry_id: int
    original_teacher_id: int
    substitute_teacher_id: int
    substitution_date: str
    reason: Optional[str] = None

    @field_validator("substitution_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            datetime.date.fromisoformat(v)
        except (ValueError, TypeError):
            raise ValueError("substitution_date must be in YYYY-MM-DD format")
        return v


class SubstitutionUpdate(BaseModel):
    substitute_teacher_id: Optional[int] = None
    status: Optional[str] = None
    reason: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return v
        if v not in VALID_SUBSTITUTION_STATUSES:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(VALID_SUBSTITUTION_STATUSES)}")
        return v


class SubstitutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    timetable_entry_id: int
    original_teacher_id: int
    substitute_teacher_id: int
    substitution_date: str
    reason: Optional[str] = None
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ── ExamSchedule ───────────────────────────────────────────────────────

class ExamScheduleCreate(BaseModel):
    academic_year_id: int
    term_id: Optional[int] = None
    class_id: int
    section_id: Optional[int] = None
    subject_id: int
    exam_date: str
    start_time: str
    end_time: str
    room_id: Optional[int] = None
    invigilator_id: Optional[int] = None
    max_marks: int = 100
    pass_marks: Optional[int] = None

    @field_validator("exam_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            datetime.date.fromisoformat(v)
        except (ValueError, TypeError):
            raise ValueError("exam_date must be in YYYY-MM-DD format")
        return v

    @field_validator("start_time", "end_time")
    @classmethod
    def time_valid(cls, v: str) -> str:
        return validate_time_format(v)

    @field_validator("max_marks")
    @classmethod
    def max_marks_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_marks must be at least 1")
        return v


class ExamScheduleUpdate(BaseModel):
    exam_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    room_id: Optional[int] = None
    invigilator_id: Optional[int] = None
    status: Optional[str] = None

    @field_validator("exam_date")
    @classmethod
    def validate_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return v
        try:
            datetime.date.fromisoformat(v)
        except (ValueError, TypeError):
            raise ValueError("exam_date must be in YYYY-MM-DD format")
        return v

    @field_validator("start_time", "end_time")
    @classmethod
    def time_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return v
        return validate_time_format(v)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return v
        if v not in VALID_EXAM_STATUSES:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(VALID_EXAM_STATUSES)}")
        return v


class ExamScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    academic_year_id: int
    term_id: Optional[int] = None
    class_id: int
    section_id: Optional[int] = None
    subject_id: int
    exam_date: str
    start_time: str
    end_time: str
    room_id: Optional[int] = None
    invigilator_id: Optional[int] = None
    max_marks: int
    pass_marks: Optional[int] = None
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ── GradingStructure ────────────────────────────────────────────────────

class GradingStructureCreate(BaseModel):
    academic_year_id: int
    class_id: Optional[int] = None
    subject_id: Optional[int] = None
    name: str
    min_percentage: float
    max_percentage: float
    grade_point: float = 0.0
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        return validate_name_not_empty(v)

    @field_validator("min_percentage", "max_percentage")
    @classmethod
    def percentage_range(cls, v: float) -> float:
        if v < 0 or v > 100:
            raise ValueError("Percentage must be between 0 and 100")
        return v

    @field_validator("max_percentage")
    @classmethod
    def max_gt_min(cls, v: float, info) -> float:
        min_val = info.data.get("min_percentage")
        if min_val is not None and v <= min_val:
            raise ValueError("max_percentage must be greater than min_percentage")
        return v

    @field_validator("grade_point")
    @classmethod
    def grade_point_range(cls, v: float) -> float:
        if v < 0 or v > 5.0:
            raise ValueError("grade_point must be between 0 and 5.0")
        return v


class GradingStructureUpdate(BaseModel):
    name: Optional[str] = None
    min_percentage: Optional[float] = None
    max_percentage: Optional[float] = None
    grade_point: Optional[float] = None
    description: Optional[str] = None
    status: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return v
        return validate_name_not_empty(v)

    @field_validator("min_percentage", "max_percentage")
    @classmethod
    def percentage_range(cls, v: Optional[float]) -> Optional[float]:
        if v is None: return v
        if v < 0 or v > 100:
            raise ValueError("Percentage must be between 0 and 100")
        return v

    @field_validator("grade_point")
    @classmethod
    def grade_point_range(cls, v: Optional[float]) -> Optional[float]:
        if v is None: return v
        if v < 0 or v > 5.0:
            raise ValueError("grade_point must be between 0 and 5.0")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        return validate_optional_status(v)


class GradingStructureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    academic_year_id: int
    class_id: Optional[int] = None
    subject_id: Optional[int] = None
    name: str
    min_percentage: float
    max_percentage: float
    grade_point: float
    description: Optional[str] = None
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ── GradeRecord ─────────────────────────────────────────────────────────

class GradeRecordCreate(BaseModel):
    enrollment_id: int
    subject_id: int
    grading_structure_id: Optional[int] = None
    marks_obtained: Optional[float] = None
    max_marks: int = 100
    grade: Optional[str] = None
    grade_point: float = 0.0
    term_id: Optional[int] = None
    remarks: Optional[str] = None

    @field_validator("max_marks")
    @classmethod
    def max_marks_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_marks must be at least 1")
        return v

    @field_validator("grade_point")
    @classmethod
    def grade_point_range(cls, v: float) -> float:
        if v < 0 or v > 5.0:
            raise ValueError("grade_point must be between 0 and 5.0")
        return v


class GradeRecordUpdate(BaseModel):
    marks_obtained: Optional[float] = None
    grading_structure_id: Optional[int] = None
    grade: Optional[str] = None
    grade_point: Optional[float] = None
    remarks: Optional[str] = None
    status: Optional[str] = None

    @field_validator("grade_point")
    @classmethod
    def grade_point_range(cls, v: Optional[float]) -> Optional[float]:
        if v is None: return v
        if v < 0 or v > 5.0:
            raise ValueError("grade_point must be between 0 and 5.0")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        return validate_optional_status(v)


class GradeRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    enrollment_id: int
    subject_id: int
    grading_structure_id: Optional[int] = None
    marks_obtained: Optional[float] = None
    max_marks: int
    grade: Optional[str] = None
    grade_point: float
    term_id: Optional[int] = None
    remarks: Optional[str] = None
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ── Curriculum ──────────────────────────────────────────────────────────

class CurriculumCreate(BaseModel):
    academic_year_id: int
    class_id: int
    subject_id: int
    term_id: Optional[int] = None
    topics: Optional[str] = None
    objectives: Optional[str] = None
    total_hours: Optional[int] = None
    syllabus: Optional[str] = None
    textbook: Optional[str] = None

    @field_validator("total_hours")
    @classmethod
    def hours_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError("total_hours must be at least 1")
        return v


class CurriculumUpdate(BaseModel):
    topics: Optional[str] = None
    objectives: Optional[str] = None
    total_hours: Optional[int] = None
    syllabus: Optional[str] = None
    textbook: Optional[str] = None
    status: Optional[str] = None

    @field_validator("total_hours")
    @classmethod
    def hours_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError("total_hours must be at least 1")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        return validate_optional_status(v)


class CurriculumResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    academic_year_id: int
    class_id: int
    subject_id: int
    term_id: Optional[int] = None
    topics: Optional[str] = None
    objectives: Optional[str] = None
    total_hours: Optional[int] = None
    syllabus: Optional[str] = None
    textbook: Optional[str] = None
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ── Conflict Detection ──────────────────────────────────────────────────

class ConflictInfo(BaseModel):
    type: str
    description: str
    entity_ids: dict[str, int]


class TimetableCheckResult(BaseModel):
    has_conflicts: bool
    conflicts: list[ConflictInfo] = []


# ── Timetable View ──────────────────────────────────────────────────────

class TimetableDayView(BaseModel):
    day_of_week: int
    day_name: str
    entries: list[TimetableEntryDetail] = []


class TimetableWeekView(BaseModel):
    class_name: Optional[str] = None
    section_name: Optional[str] = None
    teacher_name: Optional[str] = None
    room_name: Optional[str] = None
    days: list[TimetableDayView] = []


# ── Paginated responses ─────────────────────────────────────────────────

RoomPage = Page[RoomResponse]
TimeSlotPage = Page[TimeSlotResponse]
TimetableEntryPage = Page[TimetableEntryResponse]
SubstitutionPage = Page[SubstitutionResponse]
ExamSchedulePage = Page[ExamScheduleResponse]
GradingStructurePage = Page[GradingStructureResponse]
GradeRecordPage = Page[GradeRecordResponse]
CurriculumPage = Page[CurriculumResponse]
