"""Standard domain event classes for the SDMAS event catalog.

These events carry the standard envelope (see ``events.base``) plus their
business fields.  They complement the legacy notification events in
``app.domains.notifications.events`` — the catalog in ``events.catalog``
maps both together by event type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domains.events.base import DomainEvent


# ---------------------------------------------------------------------------
# Student lifecycle
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class StudentCreatedEvent(DomainEvent):
    """A student record was created."""

    EVENT_TYPE = "student.created"
    ENTITY_TYPE = "student"

    student_id: int
    student_number: str
    full_name: str
    email: str | None = None


@dataclass(kw_only=True)
class StudentUpdatedEvent(DomainEvent):
    """A student record was updated."""

    EVENT_TYPE = "student.updated"
    ENTITY_TYPE = "student"

    student_id: int
    changes: dict[str, Any] = field(default_factory=dict)


@dataclass(kw_only=True)
class StudentStatusChangedEvent(DomainEvent):
    """A student's status changed (e.g. active -> inactive)."""

    EVENT_TYPE = "student.status_changed"
    ENTITY_TYPE = "student"

    student_id: int
    from_status: str
    to_status: str


@dataclass(kw_only=True)
class StudentEnrolledEvent(DomainEvent):
    """A student was enrolled into a class/section for an academic year."""

    EVENT_TYPE = "student.enrolled"
    ENTITY_TYPE = "enrollment"

    student_id: int
    class_id: int
    section_id: int | None = None
    academic_year_id: int | None = None


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class AttendanceRecordedEvent(DomainEvent):
    """A single attendance record was created."""

    EVENT_TYPE = "attendance.recorded"
    ENTITY_TYPE = "attendance"

    record_id: int
    student_id: int
    section_id: int | None = None
    attendance_date: str = ""
    status: str = ""


@dataclass(kw_only=True)
class AttendanceThresholdBreachedEvent(DomainEvent):
    """A student's attendance dropped below the configured threshold."""

    EVENT_TYPE = "attendance.threshold_breached"
    ENTITY_TYPE = "student"

    student_id: int
    academic_year_id: int | None = None
    section_id: int | None = None
    attendance_percentage: float = 0.0
    threshold: float = 75.0
    total_absences: int = 0


# ---------------------------------------------------------------------------
# Fees & payments
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class FeeDueCreatedEvent(DomainEvent):
    """Fee dues were created for a student."""

    EVENT_TYPE = "fee.due_created"
    ENTITY_TYPE = "fee_due"

    student_id: int
    academic_year_id: int | None = None
    due_ids: list[int] = field(default_factory=list)
    total_amount: float = 0.0
    due_count: int = 0


@dataclass(kw_only=True)
class PaymentRecordedEvent(DomainEvent):
    """A payment was recorded against a fee due."""

    EVENT_TYPE = "payment.recorded"
    ENTITY_TYPE = "payment"

    student_id: int
    fee_due_id: int
    payment_id: int
    amount: float
    payment_method: str
    receipt_number: str | None = None
    new_due_status: str = ""


@dataclass(kw_only=True)
class PaymentOverdueEvent(DomainEvent):
    """A fee due has become overdue."""

    EVENT_TYPE = "payment.overdue"
    ENTITY_TYPE = "fee_due"

    due_id: int
    student_id: int
    amount: float = 0.0
    due_date: str | None = None


# ---------------------------------------------------------------------------
# Admissions
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class AdmissionSubmittedEvent(DomainEvent):
    """An admission application was submitted."""

    EVENT_TYPE = "admission.submitted"
    ENTITY_TYPE = "admission"

    application_id: int
    applicant_name: str


@dataclass(kw_only=True)
class AdmissionApprovedEvent(DomainEvent):
    """An admission application was approved."""

    EVENT_TYPE = "admission.approved"
    ENTITY_TYPE = "admission"

    application_id: int
    applicant_name: str


@dataclass(kw_only=True)
class AdmissionRejectedEvent(DomainEvent):
    """An admission application was rejected."""

    EVENT_TYPE = "admission.rejected"
    ENTITY_TYPE = "admission"

    application_id: int
    applicant_name: str


# ---------------------------------------------------------------------------
# Leave
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class LeaveSubmittedEvent(DomainEvent):
    """A leave request was submitted."""

    EVENT_TYPE = "leave.submitted"
    ENTITY_TYPE = "leave"

    leave_id: int
    user_id: int
    start_date: str | None = None
    end_date: str | None = None


@dataclass(kw_only=True)
class LeaveApprovedEvent(DomainEvent):
    """A leave request was approved."""

    EVENT_TYPE = "leave.approved"
    ENTITY_TYPE = "leave"

    leave_id: int
    user_id: int


@dataclass(kw_only=True)
class LeaveRejectedEvent(DomainEvent):
    """A leave request was rejected."""

    EVENT_TYPE = "leave.rejected"
    ENTITY_TYPE = "leave"

    leave_id: int
    user_id: int


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class DocumentUploadedEvent(DomainEvent):
    """A document was uploaded."""

    EVENT_TYPE = "document.uploaded"
    ENTITY_TYPE = "document"

    document_id: int
    student_id: int | None = None
    category: str | None = None


@dataclass(kw_only=True)
class DocumentVerifiedEvent(DomainEvent):
    """A document verification status changed."""

    EVENT_TYPE = "document.verified"
    ENTITY_TYPE = "document"

    document_id: int
    student_id: int | None = None
    status: str | None = None


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class WorkflowSubmittedEvent(DomainEvent):
    """A workflow instance was submitted/started."""

    EVENT_TYPE = "workflow.submitted"
    ENTITY_TYPE = "workflow"

    instance_id: int
    workflow_id: int
    entity_type: str
    entity_id: int | None = None
    created_by: int | None = None


@dataclass(kw_only=True)
class WorkflowApprovedEvent(DomainEvent):
    """A workflow instance was approved at a step."""

    EVENT_TYPE = "workflow.approved"
    ENTITY_TYPE = "workflow"

    instance_id: int
    workflow_id: int
    entity_type: str
    entity_id: int | None = None
    step_name: str = ""
    status: str = ""
    actor_id: int | None = None
    created_by: int | None = None
    comment: str | None = None


@dataclass(kw_only=True)
class WorkflowRejectedEvent(DomainEvent):
    """A workflow instance was rejected."""

    EVENT_TYPE = "workflow.rejected"
    ENTITY_TYPE = "workflow"

    instance_id: int
    workflow_id: int
    entity_type: str
    entity_id: int | None = None
    step_name: str = ""
    status: str = ""
    actor_id: int | None = None
    created_by: int | None = None
    comment: str | None = None


@dataclass(kw_only=True)
class WorkflowCancelledEvent(DomainEvent):
    """A workflow instance was cancelled (withdrawn before completion)."""

    EVENT_TYPE = "workflow.cancelled"
    ENTITY_TYPE = "workflow"

    instance_id: int
    workflow_id: int
    entity_type: str
    entity_id: int | None = None
    step_name: str = ""
    status: str = ""
    actor_id: int | None = None
    created_by: int | None = None
    comment: str | None = None


# ---------------------------------------------------------------------------
# Academic year rollover
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class AcademicYearRolloverStartedEvent(DomainEvent):
    """An academic year rollover began."""

    EVENT_TYPE = "academic_year.rollover_started"
    ENTITY_TYPE = "academic_year"

    previous_year_id: int
    new_year_name: str


@dataclass(kw_only=True)
class AcademicYearRolloverCompletedEvent(DomainEvent):
    """An academic year rollover completed successfully."""

    EVENT_TYPE = "academic_year.rollover_completed"
    ENTITY_TYPE = "academic_year"

    previous_year_id: int
    new_year_id: int
    new_year_name: str
    students_rolled: int = 0
    classes_migrated: int = 0


@dataclass(kw_only=True)
class AcademicYearRolloverFailedEvent(DomainEvent):
    """An academic year rollover failed."""

    EVENT_TYPE = "academic_year.rollover_failed"
    ENTITY_TYPE = "academic_year"

    previous_year_id: int
    new_year_name: str
    error: str = ""
