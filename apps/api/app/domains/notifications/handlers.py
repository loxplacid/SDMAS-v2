"""Event handlers that translate domain events into notifications.

Handlers are registered with the ``EventDispatcher`` during application
startup. Each handler:

1. Receives a typed domain event
2. Resolves the target user(s) (event-dependent)
3. Checks the user's notification preferences
4. Renders templates for the event
5. Dispatches to enabled channels

All handlers accept a ``session`` keyword argument injected by the
``EventDispatcher`` when it was configured with a session factory.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.notifications import dispatcher as global_dispatcher
from app.domains.notifications.channels import (
    ChannelMessage,
    get_channel,
)
from app.domains.notifications.preferences import ALL_CHANNELS
from app.domains.notifications.events import (
    AcademicYearRolloverEvent,
    BatchOperationCompletedEvent,
    DomainEvent,
    FeeDueCreatedEvent,
    ImportantAdminEvent,
    LowAttendanceEvent,
    PaymentReceivedEvent,
)
from app.domains.notifications.preferences import (
    NotificationPreferenceService,
)
from app.domains.notifications.templates import render_all

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: dispatch a rendered template through a user's enabled channels
# ---------------------------------------------------------------------------


async def _dispatch_to_user(
    session: AsyncSession,
    user_id: int,
    event: DomainEvent,
    rendered_templates: list[dict[str, str]],
    event_data: dict[str, Any] | None = None,
) -> None:
    """Send rendered notifications to a specific user via their enabled channels."""
    pref_service = NotificationPreferenceService(session)

    for tpl in rendered_templates:
        event_type = tpl["type"]

        for channel_name in ALL_CHANNELS:
            if not await pref_service.is_enabled(user_id, event_type, channel_name):
                continue

            msg = ChannelMessage(
                user_id=user_id,
                event_type=event_type,
                title=tpl["title"],
                message=tpl["message"],
                data=event_data or {},
                tenant_id=getattr(event, "tenant_id", None),
            )

            try:
                channel = get_channel(channel_name, session)
                await channel.deliver(msg)
            except Exception:
                logger.warning(
                    "Channel %s failed for user %d, event %s (non-fatal)",
                    channel_name,
                    user_id,
                    type(event).__name__,
                    exc_info=True,
                )


# ---------------------------------------------------------------------------
# Individual handlers
# ---------------------------------------------------------------------------


async def handle_fee_due_created(
    event: FeeDueCreatedEvent,
    *,
    session: AsyncSession,
    **kwargs: Any,
) -> None:
    """Notify the student (and parent/guardian) about new fee dues."""
    rendered = render_all(event)

    # Notify the student directly
    await _dispatch_to_user(
        session, event.student_id, event, rendered,
        event_data={"due_ids": event.due_ids, "total_amount": event.total_amount},
    )


async def handle_payment_received(
    event: PaymentReceivedEvent,
    *,
    session: AsyncSession,
    **kwargs: Any,
) -> None:
    """Notify the student about a recorded payment."""
    rendered = render_all(event)
    await _dispatch_to_user(
        session, event.student_id, event, rendered,
        event_data={
            "payment_id": event.payment_id,
            "amount": event.amount,
            "receipt": event.receipt_number,
        },
    )


async def handle_low_attendance(
    event: LowAttendanceEvent,
    *,
    session: AsyncSession,
    **kwargs: Any,
) -> None:
    """Alert the student and potentially the parent/guardian."""
    rendered = render_all(event)
    await _dispatch_to_user(
        session, event.student_id, event, rendered,
        event_data={"attendance_pct": event.attendance_percentage},
    )


async def handle_academic_year_rollover(
    event: AcademicYearRolloverEvent,
    *,
    session: AsyncSession,
    **kwargs: Any,
) -> None:
    """Notify admin users about the rollover result.

    This handler re-dispatches through ``ImportantAdminEvent`` so the
    normal admin notification pipeline handles delivery.
    """
    rendered = render_all(event)

    logger.info(
        "Rollover complete: %s (year %d \u2192 %d), %d students, %d classes",
        event.new_year_name,
        event.previous_year_id,
        event.new_year_id,
        event.students_rolled,
        event.classes_migrated,
    )

    # Notify through ImportantAdminEvent for system-wide broadcast
    admin_event = ImportantAdminEvent(
        tenant_id=event.tenant_id,
        event_type="rollover",
        title="Academic Year Rollover Complete",
        message=rendered[0]["message"] if rendered else "Rollover completed.",
        metadata={
            "previous_year_id": event.previous_year_id,
            "new_year_id": event.new_year_id,
            "students_rolled": event.students_rolled,
        },
    )
    await global_dispatcher.dispatch(admin_event, session=session)


async def handle_batch_operation_completed(
    event: BatchOperationCompletedEvent,
    *,
    session: AsyncSession,
    **kwargs: Any,
) -> None:
    """Notify about batch operation results."""
    rendered = render_all(event)
    logger.info(
        "Batch %s: %d/%d succeeded (%d errors)",
        event.operation_type,
        event.success_count,
        event.total_processed,
        event.error_count,
    )

    if rendered:
        logger.info(
            "[BATCH NOTIFICATION] %s \u2014 %s",
            rendered[0]["title"],
            rendered[0]["message"],
        )


async def handle_important_admin(
    event: ImportantAdminEvent,
    *,
    session: AsyncSession,
    **kwargs: Any,
) -> None:
    """Broadcast critical admin events to the target user.

    In production, this would resolve a list of admin/staff user IDs
    from the database for fan-out broadcast.
    """
    rendered = render_all(event)

    if event.target_user_id is not None:
        await _dispatch_to_user(
            session, event.target_user_id, event, rendered,
            event_data=event.metadata,
        )


# ---------------------------------------------------------------------------
# Handler registration helper
# ---------------------------------------------------------------------------


def register_all_handlers(dispatcher: Any) -> None:
    """Register all notification event handlers with the dispatcher.

    Call this during application startup::

        from app.domains.notifications.handlers import register_all_handlers
        register_all_handlers(dispatcher)
    """
    dispatcher.register(FeeDueCreatedEvent, handle_fee_due_created)
    dispatcher.register(PaymentReceivedEvent, handle_payment_received)
    dispatcher.register(LowAttendanceEvent, handle_low_attendance)
    dispatcher.register(AcademicYearRolloverEvent, handle_academic_year_rollover)
    dispatcher.register(BatchOperationCompletedEvent, handle_batch_operation_completed)
    dispatcher.register(ImportantAdminEvent, handle_important_admin)

    logger.info(
        "Registered %d notification event handler(s)",
        dispatcher.handler_count,
    )
