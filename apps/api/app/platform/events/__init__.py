"""Canonical event envelope (platform contract).

The canonical envelope is the stable, versioned, deterministic serialization
of any domain event in SDMAS.  It is the *platform* representation that
domains, the outbox, the worker, and audit consumers can rely on, layered on
top of the existing ``app.domains.events`` foundation without replacing it.

Public API
----------
- ``CanonicalEnvelope`` — the immutable envelope dataclass.
- ``envelope_from_event`` — build a canonical envelope from any event object
  (standard ``DomainEvent`` subclasses, legacy notification events, or a
  plain dict with the envelope fields).
- ``to_canonical_dict`` / ``from_canonical_dict`` — deterministic JSON-safe
  conversion.
- ``validate_envelope`` — structural + integrity validation.
- ``compute_integrity`` — SHA-256 integrity metadata over the canonical body.
"""

from __future__ import annotations

from app.platform.events.envelope import (
    CANONICAL_VERSION,
    CanonicalEnvelope,
    compute_integrity,
    envelope_from_event,
    from_canonical_dict,
    to_canonical_dict,
    validate_envelope,
)

__all__ = [
    "CANONICAL_VERSION",
    "CanonicalEnvelope",
    "compute_integrity",
    "envelope_from_event",
    "from_canonical_dict",
    "to_canonical_dict",
    "validate_envelope",
]
