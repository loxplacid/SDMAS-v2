"""Outbox handler registration and event-class rehydration map.

The outbox stores events in the canonical serialized envelope.  On delivery
the worker rehydrates a typed event object from the stored ``event_type``
and ``payload`` — this module owns that map and the handler wiring.

Two kinds of events are delivered through the outbox:

* **Legacy notification events** (``app.domains.notifications.events``) —
  dispatched today by the fee / batch services.  Their ``event_type`` is
  the class name (they predate the standard envelope).
* **Standard domain events** (``app.domains.events.events``) — rollover
  events carry a dotted ``event_type`` from the catalog.

The handlers are the *same* functions used by the in-process dispatchers;
because durable events are delivered only through the outbox (never also
in-process), there is a single delivery path and no double side-effects.
"""

from __future__ import annotations

import logging

from app.domains.events.catalog import all_event_definitions
from app.domains.events.handlers import (
    handle_rollover_completed_notification,
    handle_rollover_failed_notification,
)
from app.domains.notifications.events import (
    BatchOperationCompletedEvent,
    FeeDueCreatedEvent,
    PaymentReceivedEvent,
)
from app.domains.notifications.handlers import (
    handle_batch_operation_completed,
    handle_fee_due_created,
    handle_payment_received,
)

logger = logging.getLogger(__name__)


def _build_event_class_map() -> dict[str, type]:
    """event_type string → event class for outbox rehydration.

    Standard catalog events are keyed by their dotted ``event_type``;
    legacy notification events are keyed by class name (what
    ``serialize_event`` / ``event_type_of`` produced at publish time).
    """
    mapping: dict[str, type] = {}
    for definition in all_event_definitions():
        mapping[definition.event_type] = definition.event_class
    for cls in (
        FeeDueCreatedEvent,
        PaymentReceivedEvent,
        BatchOperationCompletedEvent,
    ):
        mapping[cls.__name__] = cls
    return mapping


EVENT_CLASS_MAP: dict[str, type] = _build_event_class_map()


def register_outbox_handlers(dispatcher: Any) -> None:
    """Register the durable-event handlers with the given outbox dispatcher.

    Call once from the worker process startup::

        from app.domains.events.outbox_handlers import register_outbox_handlers
        register_outbox_handlers(outbox_dispatcher)
    """
    dispatcher.register("FeeDueCreatedEvent", handle_fee_due_created)
    dispatcher.register("PaymentReceivedEvent", handle_payment_received)
    dispatcher.register("BatchOperationCompletedEvent", handle_batch_operation_completed)
    dispatcher.register(
        "academic_year.rollover_completed", handle_rollover_completed_notification
    )
    dispatcher.register(
        "academic_year.rollover_failed", handle_rollover_failed_notification
    )
    logger.info(
        "Registered %d outbox event handler(s) covering %d event type(s)",
        dispatcher.handler_count, len(EVENT_CLASS_MAP),
    )
