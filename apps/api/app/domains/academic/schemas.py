from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.pagination import Page

VALID_ACADEMIC_STATUSES = {"active", "inactive"}


def validate_name_not_empty(v: str) -> str:
    stripped = v.strip()
    if not stripped:
        raise ValueError("Value cannot be empty or whitespace only")
    return stripped


def validate_optional_status(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    if v not in VALID_ACADEMIC_STATUSES:
        raise ValueError(f"Invalid status, must be one of {VALID_ACADEMIC_STATUSES}")
    return v


# ---------------------------------------------------------------------------
# AcademicYear
# ---------------------------------------------------------------------------


class AcademicYearCreate(BaseModel):
    name: str
    start_date: datetime.date
    end_date: datetime.date

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        return validate_name_not_empty(v)

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v: datetime.date, info) -> datetime.date:
        start = info.data.get("start_date")
        if start is not None and v <= start:
            raise ValueError("end_date must be after start_date")
        return v


class AcademicYearUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[datetime.date] = None
    end_date: Optional[datetime.date] = None
    status: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_name_not_empty(v)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        return validate_optional_status(v)


class AcademicYearResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    start_date: datetime.date
    end_date: datetime.date
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# Class
# ---------------------------------------------------------------------------


class ClassCreate(BaseModel):
    name: str
    academic_year_id: int

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        return validate_name_not_empty(v)


class ClassUpdate(BaseModel):
    name: Optional[str] = None
    academic_year_id: Optional[int] = None
    status: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_name_not_empty(v)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        return validate_optional_status(v)


class ClassResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    academic_year_id: int
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# Section
# ---------------------------------------------------------------------------


class SectionCreate(BaseModel):
    name: str
    class_id: int

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        return validate_name_not_empty(v)


class SectionUpdate(BaseModel):
    name: Optional[str] = None
    class_id: Optional[int] = None
    status: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_name_not_empty(v)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        return validate_optional_status(v)


class SectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    class_id: int
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------


class EnrollmentCreate(BaseModel):
    student_id: int
    academic_year_id: int
    class_id: Optional[int] = None
    section_id: Optional[int] = None


class EnrollmentUpdate(BaseModel):
    class_id: Optional[int] = None
    section_id: Optional[int] = None
    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        return validate_optional_status(v)


class EnrollmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    academic_year_id: int
    class_id: Optional[int] = None
    section_id: Optional[int] = None
    status: str
    enrolled_at: datetime.datetime
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# Paginated responses
# ---------------------------------------------------------------------------

AcademicYearPage = Page[AcademicYearResponse]
ClassPage = Page[ClassResponse]
SectionPage = Page[SectionResponse]
EnrollmentPage = Page[EnrollmentResponse]


# ---------------------------------------------------------------------------
# Term
# ---------------------------------------------------------------------------


class TermCreate(BaseModel):
    name: str
    start_date: str
    end_date: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        return validate_name_not_empty(v)


class TermUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_name_not_empty(v)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        return validate_optional_status(v)


class TermResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    academic_year_id: int
    name: str
    start_date: str
    end_date: str
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# Subject
# ---------------------------------------------------------------------------


class SubjectCreate(BaseModel):
    name: str
    code: str
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        return validate_name_not_empty(v)

    @field_validator("code")
    @classmethod
    def code_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Subject code cannot be empty")
        return stripped.upper()


class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_name_not_empty(v)

    @field_validator("code")
    @classmethod
    def code_uppercase(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        stripped = v.strip()
        if not stripped:
            raise ValueError("Subject code cannot be empty")
        return stripped.upper()

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        return validate_optional_status(v)


class SubjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: Optional[str] = None
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# Teacher
# ---------------------------------------------------------------------------


class TeacherCreate(BaseModel):
    first_name: str
    last_name: str
    employee_number: str
    email: Optional[str] = None

    @field_validator("first_name")
    @classmethod
    def first_name_not_empty(cls, v: str) -> str:
        return validate_name_not_empty(v)

    @field_validator("last_name")
    @classmethod
    def last_name_not_empty(cls, v: str) -> str:
        return validate_name_not_empty(v)

    @field_validator("employee_number")
    @classmethod
    def emp_number_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Employee number cannot be empty")
        return stripped


class TeacherUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None

    @field_validator("first_name")
    @classmethod
    def first_name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_name_not_empty(v)

    @field_validator("last_name")
    @classmethod
    def last_name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_name_not_empty(v)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        return validate_optional_status(v)


class TeacherResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    employee_number: str
    email: Optional[str] = None
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# TeacherAssignment
# ---------------------------------------------------------------------------


class TeacherAssignmentCreate(BaseModel):
    teacher_id: int
    class_id: int
    subject_id: Optional[int] = None


class TeacherAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    teacher_id: int
    class_id: int
    subject_id: Optional[int] = None
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# Paginated responses
# ---------------------------------------------------------------------------

TermPage = Page[TermResponse]
SubjectPage = Page[SubjectResponse]
TeacherPage = Page[TeacherResponse]
TeacherAssignmentPage = Page[TeacherAssignmentResponse]