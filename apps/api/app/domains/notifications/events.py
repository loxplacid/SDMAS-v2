"""Domain events for the notification system.

Events are lightweight data classes that carry the context needed by
notification handlers. They are dispatched in-process via the
``EventDispatcher``, which can later be swapped for a Redis/RabbitMQ/Kafka
backplane without changing the event definitions.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base event
# ---------------------------------------------------------------------------


class DomainEvent(ABC):
    """Base class for all domain events.

    This is intentionally **not** a dataclass — Python's dataclass
    inheritance model cannot handle a parent field with a default
    value followed by child fields without defaults.  Each concrete
    subclass is individually decorated with ``@dataclass`` and
    defines ``tenant_id`` as its last optional field so that
    callers can always pass it as a keyword argument.
    """


# ---------------------------------------------------------------------------
# Concrete event types
# ---------------------------------------------------------------------------


@dataclass
class FeeDueCreatedEvent(DomainEvent):
    """Fired when fee dues are created for a student."""

    student_id: int
    academic_year_id: int
    due_ids: list[int] = field(default_factory=list)
    total_amount: float = 0.0
    due_count: int = 0
    tenant_id: int | None = None
    """Optional tenant (campus) scope for multi-tenant routing."""


@dataclass
class PaymentReceivedEvent(DomainEvent):
    """Fired when a payment is recorded against a fee due."""

    student_id: int
    fee_due_id: int
    payment_id: int
    amount: float
    payment_method: str
    receipt_number: str | None = None
    new_due_status: str = ""
    tenant_id: int | None = None
    """Optional tenant (campus) scope for multi-tenant routing."""


@dataclass
class LowAttendanceEvent(DomainEvent):
    """Fired when a student's attendance drops below a threshold."""

    student_id: int
    academic_year_id: int
    section_id: int | None = None
    attendance_percentage: float = 0.0
    threshold: float = 75.0
    total_absences: int = 0
    tenant_id: int | None = None
    """Optional tenant (campus) scope for multi-tenant routing."""


@dataclass
class AcademicYearRolloverEvent(DomainEvent):
    """Fired when an academic year rollover completes."""

    previous_year_id: int
    new_year_id: int
    new_year_name: str
    students_rolled: int = 0
    classes_migrated: int = 0
    tenant_id: int | None = None
    """Optional tenant (campus) scope for multi-tenant routing."""


@dataclass
class BatchOperationCompletedEvent(DomainEvent):
    """Fired when a bulk/batch operation finishes."""

    operation_type: str
    total_processed: int
    success_count: int
    error_count: int = 0
    summary: str = ""
    tenant_id: int | None = None
    """Optional tenant (campus) scope for multi-tenant routing."""


@dataclass
class ImportantAdminEvent(DomainEvent):
    """Fired for significant administrative events (user actions, security)."""

    event_type: str
    title: str
    message: str
    target_user_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    tenant_id: int | None = None
    """Optional tenant (campus) scope for multi-tenant routing."""


# ---------------------------------------------------------------------------
# Event dispatcher
# ---------------------------------------------------------------------------

EventHandler = Callable[..., Coroutine[Any, Any, None]]
"""Signature for an async event handler: ``async def handler(event, **kwargs)``.

Handlers receive the event as the first positional argument and may
receive a ``session`` keyword argument when the dispatcher was
configured with a session factory (recommended for production).
"""


class EventDispatcher:
    """In-process async event dispatcher.

    Handlers are registered for specific event types and fired via
    :meth:`dispatch`.  When a ``session`` is provided to :meth:`dispatch`,
    it is forwarded to every handler as a keyword argument.

    Usage::

        dispatcher = EventDispatcher()
        dispatcher.register(FeeDueCreatedEvent, my_handler)
        await dispatcher.dispatch(FeeDueCreatedEvent(student_id=1, ...))
    """

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = {}
        self._session_factory = session_factory

    def set_session_factory(
        self, factory: Callable[[], AsyncSession]
    ) -> None:
        """Set or replace the session factory used for handler dispatch."""
        self._session_factory = factory

    def register(
        self,
        event_type: type[DomainEvent],
        handler: EventHandler,
    ) -> None:
        """Register a handler for a specific event type.

        Multiple handlers can be registered for the same event type;
        they are called in registration order.
        """
        self._handlers.setdefault(event_type, []).append(handler)
        logger.debug(
            "Registered handler %s for event %s",
            handler.__name__,
            event_type.__name__,
        )

    def unregister(
        self,
        event_type: type[DomainEvent],
        handler: EventHandler,
    ) -> None:
        """Remove a previously registered handler."""
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)
            logger.debug(
                "Unregistered handler %s for event %s",
                handler.__name__,
                event_type.__name__,
            )

    async def dispatch(
        self,
        event: DomainEvent,
        session: AsyncSession | None = None,
    ) -> None:
        """Dispatch an event to all registered handlers.

        Handlers run sequentially in registration order. If a handler
        raises, the remaining handlers still run — one failing handler
        never blocks others. All exceptions are logged as warnings.

        When a ``session`` is provided, it is passed to handlers as a
        keyword argument.  Otherwise, if a ``session_factory`` was
        configured, a new session is created for the dispatch.
        """
        handlers = self._handlers.get(type(event), [])
        if not handlers:
            logger.debug(
                "No handlers registered for %s — skipping",
                type(event).__name__,
            )
            return

        kwargs: dict[str, Any] = {}
        if session is not None:
            kwargs["session"] = session
        elif self._session_factory is not None:
            kwargs["session"] = self._session_factory()

        for handler in handlers:
            try:
                await handler(event, **kwargs)
            except Exception:
                logger.warning(
                    "Handler %s failed for event %s (non-fatal)",
                    handler.__name__,
                    type(event).__name__,
                    exc_info=True,
                )

    def dispatch_async(
        self,
        event: DomainEvent,
        session: AsyncSession | None = None,
    ) -> asyncio.Task[None]:
        """Fire-and-forget dispatch: wrap :meth:`dispatch` in an asyncio task.

        Use this from synchronous or fire-and-forget contexts where you
        don't want to await the result.
        """
        return asyncio.create_task(self.dispatch(event, session=session))

    @property
    def handler_count(self) -> int:
        return sum(len(h) for h in self._handlers.values())

    def clear(self) -> None:
        """Remove all registered handlers (useful in tests)."""
        self._handlers.clear()
