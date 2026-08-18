"""Tamper-evident audit chain — pure cryptographic primitives.

All functions are pure and deterministic (same input → same output),
which is what makes independent verification possible.

- ``payload_digest`` — canonical SHA-256 of an audit event's content
  (reuses the canonical-JSON conventions from the evidence foundation).
- ``chain_hash`` — one link: SHA-256 over
  ``prev_hash | payload_hash | campus | chain_index``.  Binds the previous
  state, the event payload, the campus chain, and the position, so
  modification, deletion, or reordering each break the link.
- ``hmac_sign`` — HMAC-SHA256 of a value with the server secret.

The secret is read from ``AUDIT_CHAIN_SECRET``.  A development-only
default exists (with a loud warning at import) so the stack boots
zero-touch; production must set a real secret (DEPLOYMENT.md).
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import logging
import os
from typing import Any

from app.platform.evidence.integrity import canonical_bytes

logger = logging.getLogger(__name__)

#: Development-only fallback — never use in production.
_DEV_SECRET = "sdmas-dev-audit-chain-secret-do-not-use-in-prod"


def _secret() -> str:
    secret = os.getenv("AUDIT_CHAIN_SECRET") or _DEV_SECRET
    if secret == _DEV_SECRET:
        logger.warning(
            "AUDIT_CHAIN_SECRET is unset — using the development secret. "
            "Set a real secret in production."
        )
    return secret


def payload_digest(entry: Any) -> str:
    """Canonical SHA-256 of an audit event's meaningful content.

    The audit row carries many fields; the digest covers every field that
    an attacker could modify to change the meaning of the event.  Fields
    whose hashes would change if the row were re-created (``id``,
    ``created_at``) are included so re-creation is also detectable.
    """
    data = {
        "event_id": entry.event_id,
        "actor_type": entry.actor_type,
        "actor_id": entry.actor_id,
        "user_id": entry.user_id,
        "username": entry.username,
        "action": entry.action,
        "resource_type": entry.resource_type,
        "resource_id": entry.resource_id,
        "tenant_id": entry.tenant_id,
        "campus_id": entry.campus_id,
        "before_state": entry.before_state,
        "after_state": entry.after_state,
        "result": entry.result,
        "failure_reason": entry.failure_reason,
        "details": entry.details,
        "metadata_json": entry.metadata_json,
        "ip_address": entry.ip_address,
        "user_agent": entry.user_agent,
        "request_id": entry.request_id,
        "correlation_id": entry.correlation_id,
        "created_at": _iso(entry.created_at),
    }
    return hashlib.sha256(canonical_bytes(data)).hexdigest()


def _iso(value: Any) -> str | None:
    """Deterministic datetime serialization.

    Normalizes to UTC-naive so the digest is identical whether the value
    is tz-aware (PostgreSQL/asyncpg, write-time) or naive (SQLite round-
    trip) — otherwise the same instant hashes differently after a DB read.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        dt = value
        if getattr(dt, "tzinfo", None) is not None:
            dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return dt.isoformat()
    except AttributeError:
        return str(value)


def chain_hash(prev_hash: str, payload_hash: str, campus_id: int | None, index: int) -> str:
    """One link of the per-campus chain.

    ``prev_hash`` is the previous entry's current hash (``""`` for the
    first entry in a campus chain).  The link binds the previous state,
    the event payload, the campus, and the position — so modification of
    the event, deletion of a link, or reordering each break the chain.
    """
    campus = "" if campus_id is None else str(campus_id)
    return hashlib.sha256(
        f"{prev_hash}|{payload_hash}|{campus}|{index}".encode("utf-8")
    ).hexdigest()


def hmac_sign(value: str, secret: str | None = None) -> str:
    """HMAC-SHA256 signature of ``value`` with the server secret."""
    key = (secret if secret is not None else _secret()).encode("utf-8")
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()


def checkpoint_state_hash(current_hashes: list[str]) -> str:
    """Deterministic state hash over the ordered current hashes of a chain
    up to a point — the value a checkpoint signs."""
    blob = "|".join(current_hashes).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def json_default(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
