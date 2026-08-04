from __future__ import annotations

import datetime
import re
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.pagination import Page
from app.domains.student.models import (
    STUDENT_LIFECYCLE_ORDER,
    STUDENT_STATUSES,
)

EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
# Full lifecycle set (prospective -> ... -> alumni) plus the legacy
# ``inactive`` status for backward compatibility.
VALID_STATUSES = STUDENT_STATUSES

# Statuses settable through the generic ``PATCH /students/{id}`` endpoint.
# Lifecycle transitions must go through the dedicated, audited
# ``POST /students/{id}/lifecycle/transitions`` endpoint so every change
# records a ``StudentLifecycleEvent``; the legacy values are kept here for
# backward compatibility (deactivate/reactivate flows).  ``graduated`` is
# deliberately excluded — graduation is a terminal lifecycle state and must
# always be recorded as an audited lifecycle transition.
LEGACY_UPDATE_STATUSES = frozenset({"active", "inactive"})


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
        if v not in LEGACY_UPDATE_STATUSES:
            raise ValueError(
                f"Invalid status value, must be one of {sorted(LEGACY_UPDATE_STATUSES)}. "
                "Lifecycle transitions must use POST /students/{id}/lifecycle/transitions."
            )
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


# ---------------------------------------------------------------------------
# Lifecycle schemas
# ---------------------------------------------------------------------------


class LifecycleEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    from_status: str
    to_status: str
    reason: Optional[str] = None
    actor_id: Optional[int] = None
    created_at: datetime.datetime


class LifecycleStateOut(BaseModel):
    student_id: int
    current_status: str
    allowed_transitions: List[str]
    lifecycle_order: List[str] = list(STUDENT_LIFECYCLE_ORDER)
    recent_events: List[LifecycleEventOut] = []


class LifecycleTransitionIn(BaseModel):
    to_status: str
    reason: Optional[str] = None

    @field_validator("to_status")
    @classmethod
    def validate_to_status(cls, v: str) -> str:
        if v not in STUDENT_STATUSES:
            raise ValueError(
                f"Invalid status value, must be one of {sorted(STUDENT_STATUSES)}"
            )
        return v


LifecycleEventPage = Page[LifecycleEventOut]