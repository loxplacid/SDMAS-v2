"""Notification message templates.

Each event type maps to one or more templates that define the title,
message, and optional notification type for the in-app notification.
Templates use Python ``str.format()`` syntax and receive context from
the event dataclass.
"""

from __future__ import annotations

from typing import Any

from app.domains.notifications.events import (
    AcademicYearRolloverEvent,
    BatchOperationCompletedEvent,
    FeeDueCreatedEvent,
    ImportantAdminEvent,
    LowAttendanceEvent,
    PaymentReceivedEvent,
)


# ---------------------------------------------------------------------------
# Template definition
# ---------------------------------------------------------------------------

NotificationTemplate = dict[str, str]
"""A dict with keys ``type``, ``title``, ``message``.

``title`` and ``message`` may contain ``{field_name}`` placeholders that are
filled from the event's dataclass fields via ``str.format(**dataclass_dict)``.
"""


def _render(event: Any, template: NotificationTemplate) -> NotificationTemplate:
    """Render a template by formatting placeholders with event fields."""
    data = {
        k: str(v) if not isinstance(v, (int, float)) else v
        for k, v in event.__dict__.items()
        if not k.startswith("_")
    }
    return {
        "type": template["type"],
        "title": template["title"].format(**data),
        "message": template["message"].format(**data),
    }


# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------

TEMPLATES: dict[type, list[NotificationTemplate]] = {
    FeeDueCreatedEvent: [
        {
            "type": "fee",
            "title": "Fee Dues Created",
            "message": (
                "{due_count} fee due(s) totalling {total_amount} have "
                "been created for student #{student_id} in academic year "
                "{academic_year_id}."
            ),
        },
    ],
    PaymentReceivedEvent: [
        {
            "type": "payment",
            "title": "Payment Received",
            "message": (
                "A payment of {amount} via {payment_method} has been "
                "recorded against due #{fee_due_id}. The due is now "
                "{new_due_status}."
            ),
        },
    ],
    LowAttendanceEvent: [
        {
            "type": "attendance",
            "title": "Low Attendance Alert",
            "message": (
                "Student #{student_id} has {total_absences} absence(s) "
                "with {attendance_percentage}% attendance, below the "
                "{threshold}% threshold."
            ),
        },
    ],
    AcademicYearRolloverEvent: [
        {
            "type": "system",
            "title": "Academic Year Rollover Complete",
            "message": (
                "Rollover from year #{previous_year_id} to "
                "**{new_year_name}** (year #{new_year_id}) completed. "
                "{students_rolled} student(s) rolled, "
                "{classes_migrated} class(es) migrated."
            ),
        },
    ],
    BatchOperationCompletedEvent: [
        {
            "type": "system",
            "title": "Batch Operation Complete",
            "message": (
                "{operation_type} finished: {success_count}/{total_processed} "
                "succeeded ({error_count} errors). {summary}"
            ),
        },
    ],
    ImportantAdminEvent: [
        {
            "type": "admin",
            "title": "{title}",
            "message": "{message}",
        },
    ],
}


def get_templates(event_type: type) -> list[NotificationTemplate]:
    """Return the template list for a given event type (may be empty)."""
    return TEMPLATES.get(event_type, [])


def render_all(event: Any) -> list[NotificationTemplate]:
    """Render all templates registered for the event's type.

    Returns a list of fully-resolved ``(type, title, message)`` dicts.
    """
    return [_render(event, t) for t in get_templates(type(event))]
