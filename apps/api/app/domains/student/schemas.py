from __future__ import annotations

import datetime
import re
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.pagination import Page

EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
VALID_STATUSES = {"active", "inactive", "graduated"}


class StudentCreate(BaseModel):
    first_name: str
    last_name: str
    student_number: str
    email: Optional[str] = None
    date_of_birth: Optional[datetime.date] = None

    @field_validator("first_name", "last_name", "student_number")
    @classmethod
    def trim_and_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Value cannot be empty or whitespace only")
        return stripped

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Email cannot be empty")
        v = v.strip()
        if not EMAIL_REGEX.match(v):
            raise ValueError("Invalid email format")
        return v


class StudentUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None
    date_of_birth: Optional[datetime.date] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def trim_and_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        stripped = v.strip()
        if not stripped:
            raise ValueError("Value cannot be empty or whitespace only")
        return stripped

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Email cannot be empty")
        v = v.strip()
        if not EMAIL_REGEX.match(v):
            raise ValueError("Invalid email format")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in VALID_STATUSES:
            raise ValueError(f"Invalid status value, must be one of {VALID_STATUSES}")
        return v


class StudentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    student_number: str
    email: Optional[str] = None
    date_of_birth: Optional[datetime.date] = None
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


StudentPage = Page[StudentResponse]