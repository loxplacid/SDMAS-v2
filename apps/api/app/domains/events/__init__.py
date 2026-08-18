"""Domain event foundation for SDMAS.

A lightweight, reliable in-process event system that lets existing domains
communicate without coupling every service to every other service.

Public API:

- ``DomainEvent`` / ``serialize_event`` — standard event envelope.
- ``EVENT_CATALOG`` / ``get_event_definition`` — central event catalog.
- ``event_bus`` — the global in-process ``DomainEventDispatcher``.
- ``publish_event`` — emit an event with optional context overrides.
- ``event_context`` — set correlation/actor/tenant context for a block.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.events.base import (
    DomainEvent,
    new_correlation_id,
    new_event_id,
    now_utc,
    serialize_event,
)
from app.domains.events.catalog import (
    EVENT_CATALOG,
    EventDefinition,
    all_event_definitions,
    get_definition_for_event,
    get_event_definition,
)
from app.domains.events.context import event_context, get_causation_id
from app.domains.events.dispatcher import DomainEventDispatcher

# Global in-process event bus. Services publish domain events through this
# instance; handlers (audit, risk, notification, lifecycle) are registered
# during application startup.
event_bus: DomainEventDispatcher = DomainEventDispatcher()


async def publish_event(
    event: DomainEvent,
    session: AsyncSession | None = None,
    **context: Any,
) -> None:
    """Publish a domain event on the global event bus.

    ``context`` may carry ``correlation_id`` / ``actor_user_id`` /
    ``school_id`` overrides; otherwise these are derived from the current
    event context (see ``events.context``).
    """
    await event_bus.publish(event, session=session, **context)


__all__ = [
    "DomainEvent",
    "DomainEventDispatcher",
    "EVENT_CATALOG",
    "EventDefinition",
    "event_bus",
    "event_context",
    "get_causation_id",
    "publish_event",
    "serialize_event",
    "get_event_definition",
    "get_definition_for_event",
    "all_event_definitions",
    "new_event_id",
    "new_correlation_id",
    "now_utc",
]
