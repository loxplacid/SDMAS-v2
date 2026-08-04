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
# Deduplication key derivation
# ---------------------------------------------------------------------------


def _event_dedup_key(event: DomainEvent) -> str | None:
    """Return a deterministic dedup key for a domain event.

    Keys are stable per business occurrence so the same event published
    twice (retry, duplicate dispatch, restart replay) produces at most one
    in-app notification per user. Events without a meaningful identity
    return None (no dedup, e.g. generic admin broadcasts).
    """
    if isinstance(event, FeeDueCreatedEvent):
        return f"fee_due:{event.student_id}:{event.academic_year_id}"
    if isinstance(event, PaymentReceivedEvent):
        return f"payment:{event.payment_id}"
    if isinstance(event, LowAttendanceEvent):
        return f"low_attendance:{event.student_id}:{event.academic_year_id}"
    if isinstance(event, AcademicYearRolloverEvent):
        return f"rollover:{event.new_year_id}"
    if isinstance(event, BatchOperationCompletedEvent):
        # Callers must supply a per-run key (batch_service uses a uuid per
        # run). Returning a type-only fallback here would wrongly suppress
        # every later notification of the same operation type.
        return event.event_key
    if isinstance(event, ImportantAdminEvent):
        return None  # broadcast; dedup handled by caller when needed
    return None


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
    dedup_key = _event_dedup_key(event)

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
                event_key=dedup_key,
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
    """Notify the initiating staff user about batch operation results."""
    rendered = render_all(event)
    logger.info(
        "Batch %s: %d/%d succeeded (%d errors)",
        event.operation_type,
        event.success_count,
        event.total_processed,
        event.error_count,
    )

    target_user_id = event.target_user_id
    if target_user_id is None:
        logger.debug("Batch %s has no target user — skipping notification", event.operation_type)
        return

    await _dispatch_to_user(
        session,
        target_user_id,
        event,
        rendered,
        event_data={
            "operation_type": event.operation_type,
            "total_processed": event.total_processed,
            "success_count": event.success_count,
            "error_count": event.error_count,
            "summary": event.summary,
        },
    )


async def handle_important_admin(
    event: ImportantAdminEvent,
    *,
    session: AsyncSession,
    **kwargs: Any,
) -> None:
    """Broadcast critical admin events to the target user or, when no target
    is specified, fan out to every active admin/staff user (system-wide)."""
    rendered = render_all(event)

    if event.target_user_id is not None:
        await _dispatch_to_user(
            session, event.target_user_id, event, rendered,
            event_data=event.metadata,
        )
        return

    # Fan-out broadcast to admin/staff users.
    from sqlalchemy import select
    from app.domains.auth.models import User

    try:
        stmt = select(User.id).where(
            User.role.in_(("admin", "staff")),
            User.is_active.is_(True),
        )
        if getattr(event, "tenant_id", None) is not None:
            stmt = stmt.where(User.campus_id == event.tenant_id)
        result = await session.execute(stmt)
        admin_ids = [row[0] for row in result.all()]
    except Exception:
        logger.warning("Could not resolve admin users for broadcast (non-fatal)", exc_info=True)
        return

    for admin_id in admin_ids:
        await _dispatch_to_user(
            session, admin_id, event, rendered,
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
