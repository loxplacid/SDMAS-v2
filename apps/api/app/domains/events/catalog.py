"""Central domain event catalog for SDMAS.

The catalog is the single source of truth for every domain event in the
system: it maps canonical event-type strings to the event class, the entity
it belongs to, a human description, and the handler names that react to it.

It covers both the standard events defined in ``events.events`` and the
legacy notification events in ``app.domains.notifications.events``, so any
consumer can look up an event by type without importing domain internals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domains.events import events as standard_events
from app.domains.events.base import DomainEvent, event_type_of, serialize_event
from app.domains.notifications.events import (
    AcademicYearRolloverEvent,
    BatchOperationCompletedEvent,
    FeeDueCreatedEvent as LegacyFeeDueCreatedEvent,
    ImportantAdminEvent,
    LowAttendanceEvent,
    PaymentReceivedEvent,
)

# Re-exported standard event classes (used by handlers/tests).
StudentCreatedEvent = standard_events.StudentCreatedEvent
StudentUpdatedEvent = standard_events.StudentUpdatedEvent
StudentStatusChangedEvent = standard_events.StudentStatusChangedEvent
StudentEnrolledEvent = standard_events.StudentEnrolledEvent
AttendanceRecordedEvent = standard_events.AttendanceRecordedEvent
AttendanceThresholdBreachedEvent = standard_events.AttendanceThresholdBreachedEvent
PaymentOverdueEvent = standard_events.PaymentOverdueEvent
AdmissionSubmittedEvent = standard_events.AdmissionSubmittedEvent
AdmissionApprovedEvent = standard_events.AdmissionApprovedEvent
AdmissionRejectedEvent = standard_events.AdmissionRejectedEvent
LeaveSubmittedEvent = standard_events.LeaveSubmittedEvent
LeaveApprovedEvent = standard_events.LeaveApprovedEvent
LeaveRejectedEvent = standard_events.LeaveRejectedEvent
DocumentUploadedEvent = standard_events.DocumentUploadedEvent
DocumentVerifiedEvent = standard_events.DocumentVerifiedEvent
WorkflowSubmittedEvent = standard_events.WorkflowSubmittedEvent
WorkflowApprovedEvent = standard_events.WorkflowApprovedEvent
WorkflowRejectedEvent = standard_events.WorkflowRejectedEvent
AcademicYearRolloverStartedEvent = standard_events.AcademicYearRolloverStartedEvent
AcademicYearRolloverCompletedEvent = standard_events.AcademicYearRolloverCompletedEvent
AcademicYearRolloverFailedEvent = standard_events.AcademicYearRolloverFailedEvent


@dataclass(frozen=True)
class EventDefinition:
    """Metadata describing a single domain event type."""

    event_type: str
    entity_type: str
    description: str
    event_class: type[Any]
    handlers: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Catalog registry
# ---------------------------------------------------------------------------

EVENT_CATALOG: dict[str, EventDefinition] = {}


def register_event(
    event_type: str,
    entity_type: str,
    description: str,
    event_class: type[Any],
    handlers: tuple[str, ...] = (),
) -> EventDefinition:
    """Register (or replace) an event definition in the catalog."""
    definition = EventDefinition(
        event_type=event_type,
        entity_type=entity_type,
        description=description,
        event_class=event_class,
        handlers=handlers,
    )
    EVENT_CATALOG[event_type] = definition
    return definition


def get_event_definition(event_type: str) -> EventDefinition | None:
    """Look up an event definition by its canonical event_type string."""
    return EVENT_CATALOG.get(event_type)


def get_definition_for_event(event: Any) -> EventDefinition | None:
    """Look up the definition for a concrete event instance."""
    return EVENT_CATALOG.get(event_type_of(event))


def all_event_definitions() -> list[EventDefinition]:
    """Return all registered event definitions, sorted by event type."""
    return [EVENT_CATALOG[t] for t in sorted(EVENT_CATALOG)]


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

register_event(
    "student.created",
    "student",
    "A student record was created.",
    StudentCreatedEvent,
    handlers=("handle_student_created_audit",),
)
register_event(
    "student.updated",
    "student",
    "A student record was updated.",
    StudentUpdatedEvent,
)
register_event(
    "student.status_changed",
    "student",
    "A student's status changed (active/inactive).",
    StudentStatusChangedEvent,
)
register_event(
    "student.enrolled",
    "enrollment",
    "A student was enrolled into a class/section.",
    StudentEnrolledEvent,
)
register_event(
    "attendance.recorded",
    "attendance",
    "A single attendance record was created.",
    AttendanceRecordedEvent,
)
register_event(
    "attendance.threshold_breached",
    "student",
    "Attendance dropped below the threshold — notification + risk.",
    AttendanceThresholdBreachedEvent,
    handlers=("handle_attendance_threshold_risk",),
)
register_event(
    "fee.due_created",
    "fee_due",
    "Fee dues were created for a student.",
    LegacyFeeDueCreatedEvent,
    handlers=("handle_fee_due_created_notification",),
)
register_event(
    "payment.recorded",
    "payment",
    "A payment was recorded — receipt/notification.",
    PaymentReceivedEvent,
    handlers=("handle_payment_recorded_notification",),
)
register_event(
    "payment.overdue",
    "fee_due",
    "A fee due became overdue.",
    PaymentOverdueEvent,
)
register_event(
    "admission.submitted",
    "admission",
    "An admission application was submitted.",
    AdmissionSubmittedEvent,
)
register_event(
    "admission.approved",
    "admission",
    "An admission application was approved — workflow/lifecycle.",
    AdmissionApprovedEvent,
    handlers=("handle_admission_approved_lifecycle",),
)
register_event(
    "admission.rejected",
    "admission",
    "An admission application was rejected.",
    AdmissionRejectedEvent,
)
register_event(
    "leave.submitted",
    "leave",
    "A leave request was submitted.",
    LeaveSubmittedEvent,
)
register_event(
    "leave.approved",
    "leave",
    "A leave request was approved.",
    LeaveApprovedEvent,
)
register_event(
    "leave.rejected",
    "leave",
    "A leave request was rejected.",
    LeaveRejectedEvent,
)
register_event(
    "document.uploaded",
    "document",
    "A document was uploaded.",
    DocumentUploadedEvent,
)
register_event(
    "document.verified",
    "document",
    "A document verification status changed.",
    DocumentVerifiedEvent,
)
register_event(
    "workflow.submitted",
    "workflow",
    "A workflow instance was submitted/started.",
    WorkflowSubmittedEvent,
)
register_event(
    "workflow.approved",
    "workflow",
    "A workflow instance was approved.",
    WorkflowApprovedEvent,
    handlers=("handle_workflow_approved_notification",),
)
register_event(
    "workflow.rejected",
    "workflow",
    "A workflow instance was rejected.",
    WorkflowRejectedEvent,
)
register_event(
    "academic_year.rollover_started",
    "academic_year",
    "An academic year rollover began.",
    AcademicYearRolloverStartedEvent,
)
register_event(
    "academic_year.rollover_completed",
    "academic_year",
    "An academic year rollover completed — notification + audit.",
    AcademicYearRolloverCompletedEvent,
    handlers=("handle_rollover_completed_notification",),
)
register_event(
    "academic_year.rollover_failed",
    "academic_year",
    "An academic year rollover failed.",
    AcademicYearRolloverFailedEvent,
)
register_event(
    "batch.operation_completed",
    "batch",
    "A bulk/batch operation completed.",
    BatchOperationCompletedEvent,
)
register_event(
    "admin.important",
    "system",
    "Important administrative event (broadcast).",
    ImportantAdminEvent,
)
register_event(
    "academic_year.rollover_completed_legacy",
    "academic_year",
    "Legacy rollover notification event.",
    AcademicYearRolloverEvent,
)


__all__ = [
    "EventDefinition",
    "EVENT_CATALOG",
    "register_event",
    "get_event_definition",
    "get_definition_for_event",
    "all_event_definitions",
    "serialize_event",
    "StudentCreatedEvent",
    "StudentUpdatedEvent",
    "StudentStatusChangedEvent",
    "StudentEnrolledEvent",
    "AttendanceRecordedEvent",
    "AttendanceThresholdBreachedEvent",
    "PaymentOverdueEvent",
    "AdmissionSubmittedEvent",
    "AdmissionApprovedEvent",
    "AdmissionRejectedEvent",
    "LeaveSubmittedEvent",
    "LeaveApprovedEvent",
    "LeaveRejectedEvent",
    "DocumentUploadedEvent",
    "DocumentVerifiedEvent",
    "WorkflowSubmittedEvent",
    "WorkflowApprovedEvent",
    "WorkflowRejectedEvent",
    "AcademicYearRolloverStartedEvent",
    "AcademicYearRolloverCompletedEvent",
    "AcademicYearRolloverFailedEvent",
]
