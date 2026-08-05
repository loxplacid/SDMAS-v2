"""Utility helpers for audit logging across domain services.

Provides:
- ``get_request_metadata`` — extract IP, user agent, and campus from a
  FastAPI ``Request`` for use in domain-level audit calls.
- ``build_diff`` — compute a before/after dict from two SQLAlchemy model
  instances for capturing state changes.
- ``safe_details`` — strip sensitive fields (passwords, tokens) from
  detail dicts before storing in the audit log.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request

from app.core.security.client_ip import get_client_ip
from app.domains.auth.security import decode_token

logger = logging.getLogger(__name__)

# Fields that must NEVER appear in audit log details
_SENSITIVE_FIELDS = frozenset({
    "password",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "api_key",
    "authorization",
})


def get_request_metadata(request: Request | None) -> dict[str, Any]:
    """Extract actor, tenant, and request metadata from a FastAPI request.

    Returns a dict suitable for spreading into ``AuditService.record()``:

    .. code-block:: python

        await audit_svc.record(
            action=LOGIN,
            resource_type=USER,
            **get_request_metadata(request),
        )

    When ``request`` is ``None`` (e.g. background job or CLI operation),
    returns sensible defaults with ``ip_address=None`` and
    ``user_agent="system"``.
    """
    if request is None:
        return {
            "ip_address": None,
            "user_agent": "system",
            "campus_id": None,
        }

    metadata: dict[str, Any] = {
        "ip_address": get_client_ip(request),
        "user_agent": request.headers.get("user-agent") or "unknown",
        "campus_id": None,
    }

    # Try tenant context (set by TenantContextMiddleware)
    tenant = getattr(request.state, "tenant", None)
    if tenant is not None:
        metadata["campus_id"] = tenant.campus_id

    # Try JWT token for campus fallback
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            payload = decode_token(auth_header.removeprefix("Bearer "))
            if metadata["campus_id"] is None:
                metadata["campus_id"] = payload.get("campus_id")
        except (ValueError, KeyError, TypeError):
            pass

    return metadata


def build_diff(
    before: Any | None,
    after: Any | None,
    *,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
) -> dict[str, Any]:
    """Compare two model instances and return a dict of changed fields.

    Args:
        before: The model instance *before* the change (or ``None`` for
            creates).
        after: The model instance *after* the change (or ``None`` for
            deletes).
        include: If set, only these field names are compared.
        exclude: If set, these field names are skipped.

    Returns:
        A dict with ``before`` and ``after`` keys, each containing a
        dict of field names to values (or ``None`` if the instance was
        ``None``).

    Example output::

        {
            "before": {"status": "active", "email": "old@..."},
            "after":  {"status": "inactive", "email": "new@..."},
        }
    """
    if before is None and after is None:
        return {}

    result: dict[str, Any] = {"before": {}, "after": {}}

    # Determine which fields to inspect
    source = after if after is not None else before
    if hasattr(source, "__table__"):
        all_columns = {c.name for c in source.__table__.columns}
    elif hasattr(source, "__fields__"):
        all_columns = set(source.__fields__.keys())
    else:
        all_columns = set(dir(source))

    # Exclude internal / relationship fields
    always_exclude = {
        "metadata",
        "registry",
        "sa_instance_state",
        "_sa_instance_state",
    }
    cols = all_columns - always_exclude

    if include is not None:
        cols = cols & include
    if exclude is not None:
        cols = cols - exclude

    for col in sorted(cols):
        val_before = _safe_getattr(before, col) if before is not None else None
        val_after = _safe_getattr(after, col) if after is not None else None

        # Skip attributes that couldn't be accessed (NotImplemented sentinel)
        if val_before is NotImplemented or val_after is NotImplemented:
            continue

        # Skip SQLAlchemy relationship objects and functions
        if callable(val_before) or callable(val_after):
            continue

        if val_before != val_after:
            result["before"][col] = _serializable(val_before)
            result["after"][col] = _serializable(val_after)

    # Prune empty sides
    if not result["before"]:
        del result["before"]
    if not result["after"]:
        del result["after"]

    return result


def safe_details(details: dict[str, Any] | None) -> dict[str, Any] | None:
    """Strip sensitive fields from a details dict before storing.

    Returns a new dict with sensitive keys removed, or ``None`` if the
    input was ``None``.
    """
    if details is None:
        return None
    return {
        k: v
        for k, v in details.items()
        if k.lower() not in _SENSITIVE_FIELDS
        and not any(s in k.lower() for s in _SENSITIVE_FIELDS)
    }


# ── Internal helpers ──────────────────────────────────────────────────────


def _safe_getattr(obj: Any, name: str) -> Any:
    """Get an attribute without triggering SQLAlchemy lazy loads."""
    try:
        # Handle plain dicts (e.g. column-value snapshots from services)
        if isinstance(obj, dict):
            return obj.get(name, NotImplemented)
        # Check if it's a SQLAlchemy instrumented attribute
        # that is not yet loaded — skip to avoid side effects
        attr = obj.__mapper__.c if hasattr(obj, "__mapper__") else None
        if attr is not None and name not in attr:
            return NotImplemented
        return getattr(obj, name)
    except Exception:
        return NotImplemented


def _serializable(val: Any) -> Any:
    """Convert a value to a JSON-serializable form."""
    if val is None:
        return None
    if isinstance(val, (str, int, float, bool)):
        return val
    if isinstance(val, (list, tuple)):
        return [_serializable(v) for v in val]
    if hasattr(val, "isoformat"):  # datetime
        return val.isoformat()
    return str(val)
