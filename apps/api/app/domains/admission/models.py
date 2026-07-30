from __future__ import annotations

import datetime
from datetime import timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


# ---------------------------------------------------------------------------
# Status Constants — Workflow State Machine
# ---------------------------------------------------------------------------

# The canonical admission workflow:
# inquiry -> application_submitted -> documents_uploaded -> verified
#   -> interview_scheduled -> interview_completed -> merit_listed
#   -> seat_allocated -> fee_paid -> enrolled -> student_created
# Any state can transition to: rejected

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

# Ordered list of forward-progress states (excludes rejected)
ADMISSION_STATUS_FLOW = [
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
]

ADMISSION_VALID_STATUSES = set(ADMISSION_STATUS_FLOW) | {ADMISSION_STATUS_REJECTED}

DOCUMENT_VERIFICATION_PENDING = "pending"
DOCUMENT_VERIFICATION_VERIFIED = "verified"
DOCUMENT_VERIFICATION_REJECTED = "rejected"
VALID_DOCUMENT_VERIFICATION_STATUSES = {
    DOCUMENT_VERIFICATION_PENDING,
    DOCUMENT_VERIFICATION_VERIFIED,
    DOCUMENT_VERIFICATION_REJECTED,
}

INTERVIEW_STATUS_SCHEDULED = "scheduled"
INTERVIEW_STATUS_COMPLETED = "completed"
INTERVIEW_STATUS_CANCELLED = "cancelled"
VALID_INTERVIEW_STATUSES = {
    INTERVIEW_STATUS_SCHEDULED,
    INTERVIEW_STATUS_COMPLETED,
    INTERVIEW_STATUS_CANCELLED,
}

MERIT_STATUS_ACTIVE = "active"
MERIT_STATUS_ALLOCATED = "allocated"
MERIT_STATUS_EXPIRED = "expired"
VALID_MERIT_STATUSES = {
    MERIT_STATUS_ACTIVE,
    MERIT_STATUS_ALLOCATED,
    MERIT_STATUS_EXPIRED,
}

ALLOCATION_STATUS_ALLOCATED = "allocated"
ALLOCATION_STATUS_FEE_PAID = "fee_paid"
ALLOCATION_STATUS_CONFIRMED = "confirmed"
ALLOCATION_STATUS_EXPIRED = "expired"
VALID_ALLOCATION_STATUSES = {
    ALLOCATION_STATUS_ALLOCATED,
    ALLOCATION_STATUS_FEE_PAID,
    ALLOCATION_STATUS_CONFIRMED,
    ALLOCATION_STATUS_EXPIRED,
}


# ---------------------------------------------------------------------------
# AdmissionApplication
# ---------------------------------------------------------------------------


class AdmissionApplication(Base):
    __tablename__ = "admission_applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
    )
    academic_year_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("academic_years.id", ondelete="SET NULL"), nullable=True
    )
    program_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("programs.id", ondelete="SET NULL"), nullable=True
    )
    branch_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )
    semester_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("semesters.id", ondelete="SET NULL"), nullable=True
    )

    # Personal details
    applicant_name: Mapped[str] = mapped_column(String(200), nullable=False)
    date_of_birth: Mapped[datetime.date | None] = mapped_column(nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Application details
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    previous_education: Mapped[str | None] = mapped_column(Text, nullable=True)
    entrance_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Workflow state
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=ADMISSION_STATUS_INQUIRY
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    applied_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    enrolled_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    # Relationships
    documents: Mapped[list[AdmissionDocument]] = relationship(
        "AdmissionDocument", back_populates="application",
        cascade="all, delete-orphan", lazy="selectin"
    )
    interviews: Mapped[list[AdmissionInterview]] = relationship(
        "AdmissionInterview", back_populates="application",
        cascade="all, delete-orphan", lazy="selectin"
    )
    merit_entries: Mapped[list[AdmissionMeritEntry]] = relationship(
        "AdmissionMeritEntry", back_populates="application",
        cascade="all, delete-orphan", lazy="selectin"
    )
    seat_allocations: Mapped[list[AdmissionSeatAllocation]] = relationship(
        "AdmissionSeatAllocation", back_populates="application",
        cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<AdmissionApplication id={self.id} name={self.applicant_name} status={self.status}>"


# ---------------------------------------------------------------------------
# AdmissionDocument
# ---------------------------------------------------------------------------


class AdmissionDocument(Base):
    __tablename__ = "admission_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("admission_applications.id", ondelete="CASCADE"),
        nullable=False
    )
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    verification_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DOCUMENT_VERIFICATION_PENDING
    )
    verified_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )

    application: Mapped[AdmissionApplication] = relationship(
        "AdmissionApplication", back_populates="documents"
    )

    def __repr__(self) -> str:
        return f"<AdmissionDocument id={self.id} type={self.document_type}>"


# ---------------------------------------------------------------------------
# AdmissionInterview
# ---------------------------------------------------------------------------


class AdmissionInterview(Base):
    __tablename__ = "admission_interviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("admission_applications.id", ondelete="CASCADE"),
        nullable=False
    )
    scheduled_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    interview_mode: Mapped[str | None] = mapped_column(String(50), nullable=True)
    panel_members: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=INTERVIEW_STATUS_SCHEDULED
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )

    application: Mapped[AdmissionApplication] = relationship(
        "AdmissionApplication", back_populates="interviews"
    )

    def __repr__(self) -> str:
        return f"<AdmissionInterview id={self.id} status={self.status}>"


# ---------------------------------------------------------------------------
# AdmissionMeritEntry
# ---------------------------------------------------------------------------


class AdmissionMeritEntry(Base):
    __tablename__ = "admission_merit_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("admission_applications.id", ondelete="CASCADE"),
        nullable=False
    )
    program_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("programs.id", ondelete="CASCADE"), nullable=False
    )
    academic_year_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False
    )
    total_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=MERIT_STATUS_ACTIVE
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )

    application: Mapped[AdmissionApplication] = relationship(
        "AdmissionApplication", back_populates="merit_entries"
    )

    def __repr__(self) -> str:
        return f"<AdmissionMeritEntry id={self.id} rank={self.rank} score={self.total_score}>"


# ---------------------------------------------------------------------------
# AdmissionSeatAllocation
# ---------------------------------------------------------------------------


class AdmissionSeatAllocation(Base):
    __tablename__ = "admission_seat_allocations"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("admission_applications.id", ondelete="CASCADE"),
        nullable=False
    )
    merit_entry_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("admission_merit_entries.id", ondelete="SET NULL"),
        nullable=True
    )
    program_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("programs.id", ondelete="CASCADE"), nullable=False
    )
    branch_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )
    fee_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    allocated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    paid_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    enrolled_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ALLOCATION_STATUS_ALLOCATED
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )

    application: Mapped[AdmissionApplication] = relationship(
        "AdmissionApplication", back_populates="seat_allocations"
    )

    def __repr__(self) -> str:
        return f"<AdmissionSeatAllocation id={self.id} status={self.status}>"
