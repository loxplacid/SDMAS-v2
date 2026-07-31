"""Event-driven notification system for SDMAS.

This module has been upgraded from a basic CRUD notification system
to a full event-driven architecture supporting:

- Domain events (FeeDueCreated, PaymentReceived, LowAttendance, etc.)
- In-process async event dispatcher (broker-free, swappable later)
- Notification templates per event type
- Per-user notification preferences (opt-in/out per event type + channel)
- Multiple delivery channels (in-app, push, email placeholder, SMS placeholder)
- Automatic event emission from fee, attendance, and other services
"""

from app.domains.notifications.events import (
    AcademicYearRolloverEvent,
    BatchOperationCompletedEvent,
    DomainEvent,
    EventDispatcher,
    FeeDueCreatedEvent,
    ImportantAdminEvent,
    LowAttendanceEvent,
    PaymentReceivedEvent,
)


# Global dispatcher instance wired up during application startup.
# Services pass their own database session to dispatch(), so the
# dispatcher itself does not need a session factory — this makes it
# straightforward to use in both production and test contexts.
dispatcher: EventDispatcher = EventDispatcher()
