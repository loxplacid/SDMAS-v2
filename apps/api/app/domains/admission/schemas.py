from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.pagination import Page


# ---------------------------------------------------------------------------
# Status constants mirroring models
# ---------------------------------------------------------------------------

ADMISSION_STATUS_INQUIRY = "inquiry"
ADMISSION_STATUS_APPLICATION_SUBMITTED = "application_submitted"
ADMISSION_STATUS_DOCUMENTS_UPLOADED = "documents_uploaded"
ADMISSION_STATUS_VERIFIED = "verified"
ADMISSION_STATUS_INTERVIEW_SCHEDULED = "interview_scheduled"
ADMISSION_STATUS_INTERVIEW_COMPLETED = "interview_completed"
ADMISSION_STATUS_MERIT_LISTED = "merit_listed"
ADMISSION_STATUS_SEAT_ALLOCATED = "seat_allocated"
ADMISSION_STATUS_FEE_PAID = "fee_paid"
ADMISSION_STATUS_ENROLLED = "enrolled"
ADMISSION_STATUS_STUDENT_CREATED = "student_created"
ADMISSION_STATUS_REJECTED = "rejected"

ADMISSION_VALID_STATUSES = {
    ADMISSION_STATUS_INQUIRY,
    ADMISSION_STATUS_APPLICATION_SUBMITTED,
    ADMISSION_STATUS_DOCUMENTS_UPLOADED,
    ADMISSION_STATUS_VERIFIED,
    ADMISSION_STATUS_INTERVIEW_SCHEDULED,
    ADMISSION_STATUS_INTERVIEW_COMPLETED,
    ADMISSION_STATUS_MERIT_LISTED,
    ADMISSION_STATUS_SEAT_ALLOCATED,
    ADMISSION_STATUS_FEE_PAID,
    ADMISSION_STATUS_ENROLLED,
    ADMISSION_STATUS_STUDENT_CREATED,
    ADMISSION_STATUS_REJECTED,
}

VALID_DOC_VERIFICATION_STATUSES = {"pending", "verified", "rejected"}
VALID_INTERVIEW_STATUSES = {"scheduled", "completed", "cancelled"}
VALID_MERIT_STATUSES = {"active", "allocated", "expired"}
VALID_ALLOCATION_STATUSES = {"allocated", "fee_paid", "confirmed", "expired"}

VALID_SOURCES = {"website", "walk_in", "referral", "advertisement", "other"}


# ---------------------------------------------------------------------------
# AdmissionApplication
# ---------------------------------------------------------------------------


class AdmissionApplicationCreate(BaseModel):
    applicant_name: str
    date_of_birth: Optional[datetime.date] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    campus_id: Optional[int] = None
    academic_year_id: Optional[int] = None
    program_id: Optional[int] = None
    branch_id: Optional[int] = None
    semester_id: Optional[int] = None
    source: Optional[str] = None
    previous_education: Optional[str] = None
    entrance_score: Optional[float] = None

    @field_validator("applicant_name")
    @classmethod
    def trim_and_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Applicant name cannot be empty")
        return stripped

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in VALID_SOURCES:
            raise ValueError(f"Invalid source. Must be one of {VALID_SOURCES}")
        return v


class AdmissionApplicationUpdate(BaseModel):
    applicant_name: Optional[str] = None
    date_of_birth: Optional[datetime.date] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    academic_year_id: Optional[int] = None
    program_id: Optional[int] = None
    branch_id: Optional[int] = None
    semester_id: Optional[int] = None
    source: Optional[str] = None
    previous_education: Optional[str] = None
    entrance_score: Optional[float] = None
    remarks: Optional[str] = None


class AdmissionApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    academic_year_id: Optional[int] = None
    program_id: Optional[int] = None
    branch_id: Optional[int] = None
    semester_id: Optional[int] = None
    applicant_name: str
    date_of_birth: Optional[datetime.date] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    source: Optional[str] = None
    previous_education: Optional[str] = None
    entrance_score: Optional[float] = None
    status: str
    remarks: Optional[str] = None
    applied_at: Optional[datetime.datetime] = None
    enrolled_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


AdmissionApplicationPage = Page[AdmissionApplicationResponse]


# ---------------------------------------------------------------------------
# Status Transition
# ---------------------------------------------------------------------------


class AdmissionStatusTransition(BaseModel):
    new_status: str
    remarks: Optional[str] = None

    @field_validator("new_status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in ADMISSION_VALID_STATUSES:
            raise ValueError(f"Invalid status. Must be one of {ADMISSION_VALID_STATUSES}")
        return v


# ---------------------------------------------------------------------------
# AdmissionDocument
# ---------------------------------------------------------------------------


class AdmissionDocumentCreate(BaseModel):
    document_type: str
    file_name: str
    file_url: Optional[str] = None

    @field_validator("document_type")
    @classmethod
    def trim_and_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Document type cannot be empty")
        return stripped


class AdmissionDocumentUpdate(BaseModel):
    verification_status: Optional[str] = None
    remarks: Optional[str] = None

    @field_validator("verification_status")
    @classmethod
    def validate_verification(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in VALID_DOC_VERIFICATION_STATUSES:
            raise ValueError(f"Invalid status. Must be one of {VALID_DOC_VERIFICATION_STATUSES}")
        return v


class AdmissionDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    document_type: str
    file_name: str
    file_url: Optional[str] = None
    verification_status: str
    verified_by: Optional[int] = None
    verified_at: Optional[datetime.datetime] = None
    remarks: Optional[str] = None
    created_at: datetime.datetime


AdmissionDocumentPage = Page[AdmissionDocumentResponse]


# ---------------------------------------------------------------------------
# AdmissionInterview
# ---------------------------------------------------------------------------


class AdmissionInterviewCreate(BaseModel):
    scheduled_date: Optional[str] = None
    interview_mode: Optional[str] = None
    panel_members: Optional[str] = None


class AdmissionInterviewUpdate(BaseModel):
    scheduled_date: Optional[str] = None
    interview_mode: Optional[str] = None
    panel_members: Optional[str] = None
    score: Optional[float] = None
    remarks: Optional[str] = None
    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in VALID_INTERVIEW_STATUSES:
            raise ValueError(f"Invalid status. Must be one of {VALID_INTERVIEW_STATUSES}")
        return v


class AdmissionInterviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    scheduled_date: Optional[str] = None
    interview_mode: Optional[str] = None
    panel_members: Optional[str] = None
    score: Optional[float] = None
    remarks: Optional[str] = None
    status: str
    created_at: datetime.datetime


AdmissionInterviewPage = Page[AdmissionInterviewResponse]


# ---------------------------------------------------------------------------
# AdmissionMeritEntry
# ---------------------------------------------------------------------------


class AdmissionMeritEntryCreate(BaseModel):
    application_id: int
    program_id: int
    academic_year_id: int
    total_score: float
    rank: int
    category: Optional[str] = None


class AdmissionMeritEntryUpdate(BaseModel):
    total_score: Optional[float] = None
    rank: Optional[int] = None
    category: Optional[str] = None
    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in VALID_MERIT_STATUSES:
            raise ValueError(f"Invalid status. Must be one of {VALID_MERIT_STATUSES}")
        return v


class AdmissionMeritEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    program_id: int
    academic_year_id: int
    total_score: float
    rank: int
    category: Optional[str] = None
    status: str
    created_at: datetime.datetime


AdmissionMeritEntryPage = Page[AdmissionMeritEntryResponse]


# ---------------------------------------------------------------------------
# AdmissionSeatAllocation
# ---------------------------------------------------------------------------


class AdmissionSeatAllocationCreate(BaseModel):
    application_id: int
    merit_entry_id: Optional[int] = None
    program_id: int
    branch_id: Optional[int] = None
    fee_amount: int


class AdmissionSeatAllocationUpdate(BaseModel):
    fee_amount: Optional[int] = None
    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in VALID_ALLOCATION_STATUSES:
            raise ValueError(f"Invalid status. Must be one of {VALID_ALLOCATION_STATUSES}")
        return v


class AdmissionSeatAllocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    merit_entry_id: Optional[int] = None
    program_id: int
    branch_id: Optional[int] = None
    fee_amount: int
    allocated_at: Optional[datetime.datetime] = None
    paid_at: Optional[datetime.datetime] = None
    enrolled_at: Optional[datetime.datetime] = None
    status: str
    created_at: datetime.datetime


AdmissionSeatAllocationPage = Page[AdmissionSeatAllocationResponse]
