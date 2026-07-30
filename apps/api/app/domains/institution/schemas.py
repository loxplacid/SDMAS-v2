from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


# ---------------------------------------------------------------------------
# Institution
# ---------------------------------------------------------------------------


class InstitutionCreate(BaseModel):
    name: str
    code: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()

    @field_validator("code")
    @classmethod
    def code_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Code cannot be empty")
        return v.strip().upper()


class InstitutionUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    status: Optional[str] = None


class InstitutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    code: str
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# Campus
# ---------------------------------------------------------------------------


class CampusCreate(BaseModel):
    institution_id: int
    name: str
    code: str
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

    @field_validator("name", "code")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Value cannot be empty")
        return v.strip()


class CampusUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None


class CampusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    institution_id: int
    name: str
    code: str
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# School
# ---------------------------------------------------------------------------


class SchoolCreate(BaseModel):
    campus_id: int
    name: str
    code: str
    description: Optional[str] = None


class SchoolUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class SchoolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    campus_id: int
    name: str
    code: str
    description: Optional[str] = None
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# Department
# ---------------------------------------------------------------------------


class DepartmentCreate(BaseModel):
    school_id: int
    name: str
    code: str
    description: Optional[str] = None


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    school_id: int
    name: str
    code: str
    description: Optional[str] = None
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# Program
# ---------------------------------------------------------------------------


class ProgramCreate(BaseModel):
    department_id: int
    name: str
    code: str
    duration_years: int = 4
    description: Optional[str] = None


class ProgramUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    duration_years: Optional[int] = None
    description: Optional[str] = None
    status: Optional[str] = None


class ProgramResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    department_id: int
    name: str
    code: str
    duration_years: int
    description: Optional[str] = None
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# Branch
# ---------------------------------------------------------------------------


class BranchCreate(BaseModel):
    program_id: int
    name: str
    code: str
    description: Optional[str] = None


class BranchUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class BranchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    program_id: int
    name: str
    code: str
    description: Optional[str] = None
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# Semester
# ---------------------------------------------------------------------------


class SemesterCreate(BaseModel):
    program_id: int
    name: str
    code: str
    semester_number: int
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class SemesterUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    semester_number: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[str] = None


class SemesterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    program_id: int
    name: str
    code: str
    semester_number: int
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
