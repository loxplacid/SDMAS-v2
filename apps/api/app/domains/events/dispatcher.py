"""Domain event dispatcher.

Extends the existing in-process ``EventDispatcher`` (from the notifications
domain) with the standard envelope behavior required by the domain event
foundation:

- **Envelope stamping** — assigns ``event_id`` / ``occurred_at`` when
  missing, and fills ``actor_user_id`` / ``school_id`` / ``correlation_id``
  from the current event context (see ``events.context``).
- **Correlation propagation** — sets the event context around each dispatch
  so nested events emitted by handlers inherit the same correlation id,
  actor, and tenant.
- **Duplicate protection** — tracks recently dispatched ``event_id`` values
  so the same event instance cannot produce duplicate side effects (e.g. a
  retried payment or a re-emitted notification).
- **Error isolation** — inherited from the base dispatcher: one failing
  handler never blocks the remaining handlers.

The dispatcher is intentionally in-process and broker-free; it can later be
swapped for a Redis/RabbitMQ backplane without changing the event model.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.events.base import (
    DomainEvent,
    new_correlation_id,
    new_event_id,
    now_utc,
)
from app.domains.events.context import event_context
from app.domains.notifications.events import EventDispatcher

logger = logging.getLogger(__name__)


class DomainEventDispatcher(EventDispatcher):
    """In-process async dispatcher with standard envelope + dedup support."""

    def __init__(
        self,
        session_factory: Any = None,
        *,
        dedup_window_seconds: int = 300,
    ) -> None:
        super().__init__(session_factory=session_factory)
        self._dedup_window = dedup_window_seconds
        self._seen_event_ids: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Envelope stamping
    # ------------------------------------------------------------------

    def _stamp(self, event: DomainEvent) -> None:
        """Fill envelope fields that are missing from the event.

        Note: correlation_id is deliberately NOT assigned here — it is filled
        by :meth:`_apply_context` from the current event context (or a fresh
        value), so nested events emitted inside a dispatch inherit the parent
        correlation id.
        """
        if not getattr(event, "event_id", None):
            event.event_id = new_event_id()
        if getattr(event, "occurred_at", None) is None:
            event.occurred_at = now_utc()

    def _apply_context(self, event: DomainEvent) -> None:
        """Fill actor/school/correlation from the current event context."""
        from app.domains.events.context import (
            get_actor_user_id,
            get_correlation_id,
            get_school_id,
        )

        if getattr(event, "actor_user_id", None) is None:
            event.actor_user_id = get_actor_user_id()
        if getattr(event, "school_id", None) is None:
            event.school_id = get_school_id()
        if not getattr(event, "correlation_id", None):
            event.correlation_id = get_correlation_id() or new_correlation_id()

    def _is_duplicate(self, event_id: str) -> bool:
        now = time.time()
        seen_at = self._seen_event_ids.get(event_id)
        if seen_at is not None and (now - seen_at) < self._dedup_window:
            return True
        # Prune stale entries occasionally.
        if len(self._seen_event_ids) > 10_000:
            cutoff = now - self._dedup_window
            self._seen_event_ids = {
                eid: ts for eid, ts in self._seen_event_ids.items() if ts >= cutoff
            }
        self._seen_event_ids[event_id] = now
        return False

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def dispatch(  # type: ignore[override]
        self,
        event: DomainEvent,
        session: AsyncSession | None = None,
        **context: Any,
    ) -> None:
        """Stamp the envelope and dispatch to all registered handlers.

        ``context`` may carry ``correlation_id`` / ``actor_user_id`` /
        ``school_id`` overrides that take precedence over contextvars.

        Handlers run sequentially in registration order; a failing handler is
        logged and never blocks the remaining handlers.
        """
        self._stamp(event)
        self._apply_context(event)

        # Explicit per-dispatch context overrides win.
        correlation_id = context.get("correlation_id")
        actor_user_id = context.get("actor_user_id")
        school_id = context.get("school_id")
        if correlation_id:
            event.correlation_id = correlation_id
        if actor_user_id is not None:
            event.actor_user_id = actor_user_id
        if school_id is not None:
            event.school_id = school_id

        # Dedup: skip if this exact event was already dispatched recently.
        event_id = getattr(event, "event_id", None)
        if event_id and self._is_duplicate(event_id):
            logger.debug("Duplicate domain event %s skipped", event_id)
            return

        # Propagate correlation/actor/tenant context to handlers (and any
        # events they emit) for the duration of this dispatch.
        with event_context(
            correlation_id=event.correlation_id,
            actor_user_id=event.actor_user_id,
            school_id=event.school_id,
        ):
            await super().dispatch(event, session=session)  # type: ignore[arg-type]

    async def publish(
        self,
        event: DomainEvent,
        session: AsyncSession | None = None,
        **context: Any,
    ) -> None:
        """Convenience alias for :meth:`dispatch`."""
        await self.dispatch(event, session=session, **context)

    def reset_dedup(self) -> None:
        """Clear the dedup tracker (useful in tests)."""
        self._seen_event_ids.clear()
