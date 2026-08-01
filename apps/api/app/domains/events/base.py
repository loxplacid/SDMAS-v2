"""Standard domain event envelope for SDMAS.

Every domain event in the system carries a canonical envelope:

- ``event_id``         — unique event identifier (UUID hex)
- ``event_type``       — dotted event type (e.g. ``student.created``)
- ``entity_type``      — domain entity (e.g. ``student``, ``fee_due``)
- ``entity_id``        — primary key of the affected entity
- ``school_id``        — tenant (campus) scope; ``None`` means unscoped
- ``actor_user_id``    — user who triggered the event
- ``occurred_at``      — UTC timestamp
- ``correlation_id``   — request/trace correlation id propagated to handlers
- ``payload``          — serializable business payload

Events are deterministic and serializable: :func:`serialize_event` produces
a plain JSON-compatible dict, and standard events can be reconstructed via
the event catalog.
"""

from __future__ import annotations

import dataclasses
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, ClassVar


def now_utc() -> datetime:
    """Return the current UTC timestamp (naive, for ISO serialization)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_event_id() -> str:
    """Generate a new unique event id (UUID hex)."""
    return uuid.uuid4().hex


def new_correlation_id() -> str:
    """Generate a new correlation id (UUID hex)."""
    return uuid.uuid4().hex


# Fields that belong to the envelope rather than the business payload.
ENVELOPE_FIELDS = frozenset(
    {
        "event_id",
        "event_type",
        "entity_type",
        "entity_id",
        "school_id",
        "actor_user_id",
        "occurred_at",
        "correlation_id",
        "payload",
    }
)

# Candidate business fields used to derive ``entity_id`` automatically.
_ENTITY_ID_CANDIDATES = (
    "student_id",
    "application_id",
    "instance_id",
    "new_year_id",
    "previous_year_id",
    "due_id",
    "record_id",
    "document_id",
    "leave_id",
)


@dataclass(kw_only=True)
class DomainEvent:
    """Standard envelope base for all SDMAS domain events.

    Subclasses add their business fields and declare ``EVENT_TYPE`` /
    ``ENTITY_TYPE`` class attributes so the envelope is self-describing.
    All fields are keyword-only so field ordering is irrelevant.
    """

    event_id: str = field(default_factory=new_event_id)
    event_type: str = ""
    entity_type: str = ""
    entity_id: int | str | None = None
    school_id: int | None = None
    actor_user_id: int | None = None
    occurred_at: datetime = field(default_factory=now_utc)
    correlation_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    # Class-level metadata (not dataclass fields).
    EVENT_TYPE: ClassVar[str] = ""
    ENTITY_TYPE: ClassVar[str] = ""

    def __post_init__(self) -> None:
        if not self.event_type:
            self.event_type = type(self).EVENT_TYPE or type(self).__name__
        if not self.entity_type:
            self.entity_type = type(self).ENTITY_TYPE or ""
        if self.entity_id is None:
            for key in _ENTITY_ID_CANDIDATES:
                if hasattr(self, key):
                    self.entity_id = getattr(self, key)
                    break

    def to_dict(self) -> dict[str, Any]:
        """Serialize this event to the canonical envelope dict."""
        return serialize_event(self)


def event_type_of(event: Any) -> str:
    """Resolve the event_type string for any event object."""
    et = getattr(event, "event_type", None)
    if et:
        return str(et)
    return getattr(type(event), "EVENT_TYPE", "") or type(event).__name__


def _iso(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def serialize_event(event: Any) -> dict[str, Any]:
    """Serialize any event (standard envelope or legacy notification event)
    into the canonical, JSON-compatible envelope dict.

    Business fields are collected into ``payload``; the envelope fields are
    read directly (with sensible defaults for events that predate the
    standard envelope).
    """
    payload: dict[str, Any] = {}
    if dataclasses.is_dataclass(event):
        for f in dataclasses.fields(event):  # type: ignore[arg-type]
            if f.name in ENVELOPE_FIELDS:
                continue
            value = getattr(event, f.name)
            if isinstance(value, (datetime, date)):
                value = value.isoformat()
            payload[f.name] = value

    occurred = getattr(event, "occurred_at", None) or now_utc()
    return {
        "event_id": getattr(event, "event_id", None) or "",
        "event_type": event_type_of(event),
        "entity_type": getattr(event, "entity_type", None)
        or getattr(type(event), "ENTITY_TYPE", ""),
        "entity_id": getattr(event, "entity_id", None),
        "school_id": getattr(event, "school_id", None),
        "actor_user_id": getattr(event, "actor_user_id", None),
        "occurred_at": _iso(occurred),
        "correlation_id": getattr(event, "correlation_id", None) or "",
        "payload": payload,
    }
