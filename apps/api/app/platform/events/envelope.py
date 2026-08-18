"""Canonical event envelope.

The canonical envelope is the platform-level contract for every event that
crosses a process boundary (in-process dispatch, transactional outbox,
worker delivery, audit).  It is layered on top of the existing
``app.domains.events`` foundation — ``DomainEvent`` subclasses are mapped
into the envelope, and legacy notification events are mapped too — without
changing their existing serialization behavior.

Envelope fields
---------------
- ``event_id``        — unique event identifier (UUID hex)
- ``tenant_id``       — tenant scope (in SDMAS the campus is the tenant;
                        maps from ``school_id`` / ``tenant_id``)
- ``campus_id``       — campus scope (same value as ``tenant_id`` in SDMAS;
                        kept as a distinct field for multi-campus future)
- ``actor_id``        — acting user id (maps from ``actor_user_id``)
- ``entity_type``     — domain entity (``student``, ``fee_due``, ...)
- ``entity_id``       — primary key of the affected entity
- ``event_type``      — dotted event type (``student.created``)
- ``event_version``   — schema version of this event type (default 1)
- ``timestamp``       — ISO-8601 UTC occurrence time (maps from ``occurred_at``)
- ``correlation_id``  — end-to-end trace id (same across a causal chain)
- ``causation_id``    — id of the event that *caused* this one (parent)
- ``source``          — producer label (``api``, ``worker``, ``scheduler``, ``system``)
- ``payload``         — business payload (JSON-compatible)
- ``integrity``       — integrity metadata (algorithm + digest over the
                        canonical body), computed at serialization time

Guarantees
----------
- **Deterministic serialization** — ``to_canonical_dict`` emits the envelope
  body in a fixed field order; ``canonical_body_bytes`` serializes the
  payload with sorted keys, so the same event always produces the same bytes
  (used for the integrity digest).
- **Backward compatibility** — reading an event never mutates it and never
  requires the new fields; legacy events are mapped with sensible defaults
  (``event_version=1``, empty ``causation_id``, ``source`` derived from the
  event or ``system``).
- **Validation** — ``validate_envelope`` checks required fields, types, the
  event version, and recomputes the integrity digest.
- **Idempotency/traceability** — ``event_id`` is unique per event (the
  outbox enforces it at the DB level); ``correlation_id`` + ``causation_id``
  make every event traceable to its root and to its parent.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from typing import Any

CANONICAL_VERSION = 1

# Canonical envelope field order — deterministic serialization.
ENVELOPE_FIELDS = (
    "event_id",
    "tenant_id",
    "campus_id",
    "actor_id",
    "entity_type",
    "entity_id",
    "event_type",
    "event_version",
    "timestamp",
    "correlation_id",
    "causation_id",
    "source",
    "payload",
)

# Candidate business fields used to derive ``entity_id`` automatically when
# an event does not carry an explicit ``entity_id``.
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


def now_utc() -> datetime:
    """Current UTC timestamp (naive, for deterministic ISO serialization)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_event_id() -> str:
    """Generate a new unique event id (UUID hex)."""
    return uuid.uuid4().hex


class CanonicalEnvelope:
    """Immutable canonical event envelope.

    Constructed via :func:`envelope_from_event` (preferred) or directly.
    Attributes are read-only by convention; ``frozen``-style mutation is not
    needed because envelopes are serialization values, not domain objects.
    """

    __slots__ = tuple(ENVELOPE_FIELDS)

    def __init__(
        self,
        *,
        event_id: str,
        event_type: str,
        entity_type: str = "",
        entity_id: int | str | None = None,
        tenant_id: int | None = None,
        campus_id: int | None = None,
        actor_id: int | None = None,
        event_version: int = 1,
        timestamp: datetime | str | None = None,
        correlation_id: str = "",
        causation_id: str = "",
        source: str = "system",
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.event_id = event_id
        self.event_type = event_type
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.tenant_id = tenant_id
        self.campus_id = campus_id if campus_id is not None else tenant_id
        self.actor_id = actor_id
        self.event_version = int(event_version)
        self.timestamp = timestamp
        self.correlation_id = correlation_id
        self.causation_id = causation_id
        self.source = source
        self.payload = dict(payload or {})

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return the envelope body (without integrity metadata)."""
        return {
            "event_id": self.event_id,
            "tenant_id": self.tenant_id,
            "campus_id": self.campus_id,
            "actor_id": self.actor_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "event_type": self.event_type,
            "event_version": self.event_version,
            "timestamp": _iso(self.timestamp or now_utc()),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "source": self.source,
            "payload": self.payload,
        }

    def canonical_body_bytes(self) -> bytes:
        """Deterministic serialization of the envelope body.

        The payload is serialized with sorted keys and compact separators so
        identical logical events always produce identical bytes.
        """
        body = self.to_dict()
        payload_json = json.dumps(
            body["payload"],
            sort_keys=True,
            separators=(",", ":"),
            default=_json_default,
        )
        # Rebuild with the canonical payload string to keep field order stable.
        canonical: dict[str, Any] = {k: v for k, v in body.items() if k != "payload"}
        canonical["payload"] = payload_json
        return json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def integrity(self) -> dict[str, str]:
        """Compute integrity metadata over the canonical body."""
        digest = hashlib.sha256(self.canonical_body_bytes()).hexdigest()
        return {"algorithm": "sha256", "version": str(CANONICAL_VERSION), "digest": digest}

    def to_full_dict(self) -> dict[str, Any]:
        """Return the envelope body plus integrity metadata."""
        body = self.to_dict()
        body["integrity"] = self.integrity()
        return body

    def __repr__(self) -> str:
        return (
            f"CanonicalEnvelope(event_id={self.event_id!r}, "
            f"event_type={self.event_type!r}, version={self.event_version}, "
            f"entity={self.entity_type}:{self.entity_id!r})"
        )


# ---------------------------------------------------------------------------
# Reading events
# ---------------------------------------------------------------------------


def _event_field(event: Any, *names: str, default: Any = None) -> Any:
    """Read the first present attribute from an event object (or dict)."""
    for name in names:
        if isinstance(event, dict):
            if name in event:
                return event[name]
        elif hasattr(event, name):
            return getattr(event, name)
    return default


def _iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value) if value is not None else ""


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    if isinstance(value, (bytes, bytearray)):
        return value.hex()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def envelope_from_event(event: Any) -> CanonicalEnvelope:
    """Build a canonical envelope from any SDMAS event.

    Accepts standard ``DomainEvent`` subclasses, legacy notification events,
    and plain dicts that carry at least ``event_id`` + ``event_type``.
    Missing fields fall back to sensible defaults so *every* event in the
    system can be canonicalized without modification.
    """
    event_id = _event_field(event, "event_id") or new_event_id()
    event_type = (
        _event_field(event, "event_type")
        or _event_field(event, "EVENT_TYPE")
        or type(event).__name__
    )

    entity_type = _event_field(event, "entity_type") or _event_field(event, "ENTITY_TYPE") or ""
    entity_id = _event_field(event, "entity_id")
    if entity_id is None and not isinstance(event, dict):
        for key in _ENTITY_ID_CANDIDATES:
            if hasattr(event, key):
                entity_id = getattr(event, key)
                break

    tenant_id = _event_field(event, "tenant_id", "school_id", "campus_id")
    campus_id = _event_field(event, "campus_id", "school_id", "tenant_id")
    actor_id = _event_field(event, "actor_id", "actor_user_id", "user_id")

    event_version = _event_field(event, "event_version", default=None)
    if event_version is None:
        event_version = _event_field(type(event), "EVENT_VERSION", default=1)
    try:
        event_version = int(event_version or 1)
    except (TypeError, ValueError):
        event_version = 1

    timestamp = _event_field(event, "timestamp", "occurred_at")
    correlation_id = _event_field(event, "correlation_id") or ""
    causation_id = _event_field(event, "causation_id") or ""
    source = _event_field(event, "source") or "system"

    payload: dict[str, Any] = {}
    if isinstance(event, dict):
        payload = {k: v for k, v in event.items() if k not in ENVELOPE_FIELDS}
    elif dataclasses.is_dataclass(event):
        for f in dataclasses.fields(event):  # type: ignore[arg-type]
            if f.name in ENVELOPE_FIELDS:
                continue
            value = getattr(event, f.name)
            if isinstance(value, (datetime, date)):
                value = value.isoformat()
            payload[f.name] = value

    return CanonicalEnvelope(
        event_id=event_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        tenant_id=tenant_id,
        campus_id=campus_id,
        actor_id=actor_id,
        event_version=event_version,
        timestamp=timestamp,
        correlation_id=correlation_id,
        causation_id=causation_id,
        source=source,
        payload=payload,
    )


def to_canonical_dict(event: Any) -> dict[str, Any]:
    """Serialize an event to the canonical JSON-safe dict (with integrity)."""
    return envelope_from_event(event).to_full_dict()


def from_canonical_dict(data: dict[str, Any]) -> CanonicalEnvelope:
    """Rebuild an envelope from a canonical dict (ignoring stored integrity)."""
    return CanonicalEnvelope(
        event_id=data.get("event_id") or new_event_id(),
        event_type=data.get("event_type") or "",
        entity_type=data.get("entity_type") or "",
        entity_id=data.get("entity_id"),
        tenant_id=data.get("tenant_id"),
        campus_id=data.get("campus_id"),
        actor_id=data.get("actor_id"),
        event_version=int(data.get("event_version") or 1),
        timestamp=data.get("timestamp"),
        correlation_id=data.get("correlation_id") or "",
        causation_id=data.get("causation_id") or "",
        source=data.get("source") or "system",
        payload=data.get("payload") or {},
    )


def compute_integrity(body: dict[str, Any]) -> dict[str, str]:
    """Compute integrity metadata for a canonical body dict."""
    envelope = from_canonical_dict(body)
    return envelope.integrity()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_envelope(data: dict[str, Any]) -> list[str]:
    """Validate a canonical envelope dict.

    Returns a list of human-readable problems; an empty list means valid.
    Checks required fields, types, the event version, and — when integrity
    metadata is present — that the stored digest matches a recomputation.
    """
    errors: list[str] = []

    event_id = data.get("event_id")
    if not event_id:
        errors.append("event_id is required and must be non-empty")

    event_type = data.get("event_type")
    if not event_type:
        errors.append("event_type is required and must be non-empty")

    version = data.get("event_version")
    if version is None:
        errors.append("event_version is required")
    else:
        try:
            if int(version) < 1:
                errors.append("event_version must be >= 1")
        except (TypeError, ValueError):
            errors.append("event_version must be an integer")

    for field in ("tenant_id", "campus_id", "actor_id", "entity_id"):
        value = data.get(field)
        if value is not None and not isinstance(value, (int, str)):
            errors.append(f"{field} must be an int or string, got {type(value).__name__}")

    timestamp = data.get("timestamp")
    if timestamp:
        try:
            parsed = (
                timestamp
                if isinstance(timestamp, datetime)
                else datetime.fromisoformat(str(timestamp))
            )
            if parsed.tzinfo is not None and str(parsed.tzinfo) not in ("UTC", "+00:00"):
                errors.append("timestamp must be UTC")
        except ValueError:
            errors.append(f"timestamp is not a valid ISO-8601 value: {timestamp!r}")

    payload = data.get("payload")
    if payload is not None and not isinstance(payload, dict):
        errors.append("payload must be a JSON object")

    integrity = data.get("integrity")
    if integrity:
        if not isinstance(integrity, dict) or not integrity.get("digest"):
            errors.append("integrity must be an object with a 'digest'")
        else:
            try:
                envelope = from_canonical_dict(data)
                expected = envelope.integrity()["digest"]
                if integrity["digest"] != expected:
                    errors.append("integrity digest does not match the envelope body")
            except Exception as exc:  # pragma: no cover - defensive
                errors.append(f"integrity verification failed: {exc}")

    return errors


# The envelope body fields (without integrity) — for consumers that need the
# canonical key set.
CANONICAL_BODY_FIELDS: tuple[str, ...] = ENVELOPE_FIELDS
