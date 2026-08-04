"""Initial domain event handlers for SDMAS.

Each handler receives a typed event plus the ``session`` keyword argument
injected by the dispatcher. Handlers follow the same conventions as the
notification handlers:

- They never mutate the business entity that produced the event.
- They are best-effort: exceptions are logged and isolated by the
  dispatcher, so a notification/audit failure can never corrupt the
  underlying operation.
- Notifications are produced by re-dispatching the existing notification
  events through ``notification_dispatcher`` (single source of truth for
  channels/preferences), which keeps notification logic from being
  duplicated here.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.audit.constants import (
    APPROVE,
    CREATE,
    RISK,
    ACADEMIC,
    ADMISSION,
    ATTENDANCE,
    STUDENT,
)
from app.domains.audit.repository import AuditLogRepository
from app.domains.audit.service import AuditService
from app.domains.events.base import serialize_event
from app.domains.events.events import (
    AcademicYearRolloverCompletedEvent,
    AcademicYearRolloverFailedEvent,
    AdmissionApprovedEvent,
    AttendanceThresholdBreachedEvent,
    StudentCreatedEvent,
    WorkflowApprovedEvent,
)
from app.domains.notifications import dispatcher as notification_dispatcher
from app.domains.notifications.events import ImportantAdminEvent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _record_audit(
    session: AsyncSession,
    *,
    action: str,
    resource_type: str,
    resource_id: str | None,
    event: Any,
    details: dict[str, Any] | None = None,
) -> None:
    """Write an audit entry derived from a domain event (best-effort)."""
    try:
        svc = AuditService(session)
        entry_details = dict(details or {})
        entry_details["event_id"] = getattr(event, "event_id", None)
        entry_details["correlation_id"] = getattr(event, "correlation_id", None)
        await svc.record(
            user_id=getattr(event, "actor_user_id", None),
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=entry_details,
            campus_id=getattr(event, "school_id", None),
        )
        await session.flush()
    except Exception:
        logger.warning(
            "Failed to record audit entry for %s (non-fatal)",
            getattr(event, "event_type", type(event).__name__),
            exc_info=True,
        )


async def _dispatch_admin_notification(
    session: AsyncSession,
    *,
    event_type: str,
    title: str,
    message: str,
    metadata: dict[str, Any],
    tenant_id: int | None,
    target_user_id: int | None = None,
) -> None:
    """Best-effort bridge to the existing admin notification pipeline."""
    try:
        admin_event = ImportantAdminEvent(
            tenant_id=tenant_id,
            event_type=event_type,
            title=title,
            message=message,
            metadata=metadata,
            target_user_id=target_user_id,
        )
        await notification_dispatcher.dispatch(admin_event, session=session)
    except Exception:
        logger.warning("Failed to dispatch admin notification (non-fatal)", exc_info=True)


# ---------------------------------------------------------------------------
# Student lifecycle handlers
# ---------------------------------------------------------------------------


async def handle_student_created_audit(
    event: StudentCreatedEvent,
    *,
    session: AsyncSession,
    **kwargs: Any,
) -> None:
    """Audit integration: StudentCreated -> audit event (idempotent).

    The student service already records a CREATE audit entry synchronously
    (source of truth), so this handler only fills the gap when that entry is
    missing — it never produces a duplicate side effect.
    """
    repo = AuditLogRepository(session)
    _, existing_count = await repo.list(
        action=CREATE,
        resource_type=STUDENT,
        resource_id=str(event.student_id),
    )
    if existing_count:
        return
    await _record_audit(
        session,
        action=CREATE,
        resource_type=STUDENT,
        resource_id=str(event.student_id),
        event=event,
        details={
            "student_number": event.student_number,
            "full_name": event.full_name,
            "payload": serialize_event(event)["payload"],
        },
    )


# ---------------------------------------------------------------------------
# Attendance handlers
# ---------------------------------------------------------------------------


async def handle_attendance_threshold_risk(
    event: AttendanceThresholdBreachedEvent,
    *,
    session: AsyncSession,
    **kwargs: Any,
) -> None:
    """Risk integration: AttendanceThresholdBreached -> audit + risk entry.

    The notification side is handled by the existing LowAttendanceEvent
    handler in the notifications domain (registered via
    ``register_all_handlers``); this handler records the risk in the audit
    trail so risk is never lost if notification channels are down.
    """
    await _record_audit(
        session,
        action=RISK,
        resource_type=ATTENDANCE,
        resource_id=str(event.student_id),
        event=event,
        details={
            "attendance_percentage": event.attendance_percentage,
            "threshold": event.threshold,
            "total_absences": event.total_absences,
        },
    )


# ---------------------------------------------------------------------------
# Admission handlers
# ---------------------------------------------------------------------------


async def handle_admission_approved_lifecycle(
    event: AdmissionApprovedEvent,
    *,
    session: AsyncSession,
    **kwargs: Any,
) -> None:
    """Lifecycle integration: AdmissionApproved -> workflow/lifecycle event.

    Records the approval in the audit trail and notifies admins through the
    existing admin notification pipeline.
    """
    await _record_audit(
        session,
        action=APPROVE,
        resource_type=ADMISSION,
        resource_id=str(event.application_id),
        event=event,
        details={"applicant_name": event.applicant_name},
    )
    await _dispatch_admin_notification(
        session,
        event_type="admission_approved",
        title="Admission Approved",
        message=f"Admission application for {event.applicant_name} was approved.",
        metadata=serialize_event(event)["payload"],
        tenant_id=getattr(event, "school_id", None),
    )


# ---------------------------------------------------------------------------
# Workflow handlers
# ---------------------------------------------------------------------------


async def handle_workflow_approved_notification(
    event: WorkflowApprovedEvent,
    *,
    session: AsyncSession,
    **kwargs: Any,
) -> None:
    """Notification integration: WorkflowApproved -> notification event.

    The submitter (``created_by``) is notified that their request was
    approved; when no submitter is recorded the acting user is used.
    """
    await _dispatch_admin_notification(
        session,
        event_type=f"workflow_{event.event_type.split('.')[-1]}",
        title=f"Workflow approved: {event.entity_type}#{event.entity_id}",
        message=(
            f"Workflow instance {event.instance_id} was approved "
            f"at step '{event.step_name or '?'}'."
            f"{(' — ' + event.comment) if event.comment else ''}"
        ),
        metadata=serialize_event(event)["payload"],
        tenant_id=getattr(event, "school_id", None),
        target_user_id=event.created_by or event.actor_id,
    )


# ---------------------------------------------------------------------------
# Rollover handlers
# ---------------------------------------------------------------------------


async def handle_rollover_completed_notification(
    event: AcademicYearRolloverCompletedEvent,
    *,
    session: AsyncSession,
    **kwargs: Any,
) -> None:
    """Notification + audit integration: rollover completed."""
    await _record_audit(
        session,
        action=CREATE,
        resource_type=ACADEMIC,
        resource_id=str(event.new_year_id),
        event=event,
        details={
            "previous_year_id": event.previous_year_id,
            "new_year_name": event.new_year_name,
            "students_rolled": event.students_rolled,
            "classes_migrated": event.classes_migrated,
        },
    )
    await _dispatch_admin_notification(
        session,
        event_type="rollover_completed",
        title="Academic Year Rollover Complete",
        message=(
            f"Rollover to '{event.new_year_name}' completed: "
            f"{event.students_rolled} students, {event.classes_migrated} classes."
        ),
        metadata=serialize_event(event)["payload"],
        tenant_id=getattr(event, "school_id", None),
    )


async def handle_rollover_failed_notification(
    event: AcademicYearRolloverFailedEvent,
    *,
    session: AsyncSession,
    **kwargs: Any,
) -> None:
    """Notification + audit integration: rollover failed.

    Alerts admins so a failed academic year rollover is never silent.
    The error text is truncated and contained in metadata (no stack trace).
    """
    await _record_audit(
        session,
        action=CREATE,
        resource_type=ACADEMIC,
        resource_id=str(event.previous_year_id),
        event=event,
        details={
            "new_year_name": event.new_year_name,
            "error": event.error[:500],
        },
    )
    await _dispatch_admin_notification(
        session,
        event_type="rollover_failed",
        title="Academic Year Rollover Failed",
        message=(
            f"Rollover to '{event.new_year_name}' failed. "
            f"Check the audit trail for details."
        ),
        metadata={
            "previous_year_id": event.previous_year_id,
            "new_year_name": event.new_year_name,
            "error": event.error[:500],
        },
        tenant_id=getattr(event, "school_id", None),
    )


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------


def register_domain_event_handlers(dispatcher: Any) -> None:
    """Register all domain event handlers with the given dispatcher.

    Call during application startup alongside the notification handler
    registration::

        from app.domains.events.handlers import register_domain_event_handlers
        register_domain_event_handlers(dispatcher)
    """
    dispatcher.register(StudentCreatedEvent, handle_student_created_audit)
    dispatcher.register(AttendanceThresholdBreachedEvent, handle_attendance_threshold_risk)
    dispatcher.register(AdmissionApprovedEvent, handle_admission_approved_lifecycle)
    dispatcher.register(WorkflowApprovedEvent, handle_workflow_approved_notification)
    dispatcher.register(
        AcademicYearRolloverCompletedEvent, handle_rollover_completed_notification
    )
    dispatcher.register(
        AcademicYearRolloverFailedEvent, handle_rollover_failed_notification
    )
    logger.info(
        "Registered %d domain event handler(s)",
        dispatcher.handler_count,
    )
