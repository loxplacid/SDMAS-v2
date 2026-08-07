"""Bitemporal time context for The Archive (M1).

A request carries either *no* time context (current state — the normal,
zero-overhead path) or an ``as_of`` instant (transaction time: "what the
system knew then") and/or a ``valid`` instant ("what was true in the world
then"). The temporal rewriter (M2) consumes this; M1 defines the context and
its request-scoped carrier.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

__all__ = ["TimeContext", "time_context", "set_time_context"]


@dataclass(frozen=True)
class TimeContext:
    """Bitemporal query context.

    Attributes:
        as_of: transaction-time instant. When set, reads resolve the state
            of the system as it was *known* at that instant.
        valid: valid-time instant. When set, reads resolve the state that
            was *true in the world* at that instant.
        actor_id: identity recorded on writes made under this context
            (used by the TxnManager for the txn_log).
        reason: human reason attached to writes under this context
            (required for non-trivial mutations).
    """

    as_of: Optional[datetime] = None
    valid: Optional[datetime] = None
    actor_id: Optional[int] = None
    reason: Optional[str] = None

    @property
    def is_temporal(self) -> bool:
        """True when reads under this context must consult history."""
        return self.as_of is not None or self.valid is not None

    @property
    def as_of_utc(self) -> Optional[datetime]:
        """The as_of instant normalized to an aware UTC datetime."""
        if self.as_of is None:
            return None
        dt = self.as_of
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @property
    def valid_utc(self) -> Optional[datetime]:
        """The valid instant normalized to an aware UTC datetime."""
        if self.valid is None:
            return None
        dt = self.valid
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        bits = []
        if self.as_of is not None:
            bits.append(f"as_of={self.as_of.isoformat()}")
        if self.valid is not None:
            bits.append(f"valid={self.valid.isoformat()}")
        return f"TimeContext({', '.join(bits) or 'current'})"


# ---------------------------------------------------------------------------
# Request-scoped carrier (contextvars — no thread/async leaks)
# ---------------------------------------------------------------------------

_time_context_var: contextvars.ContextVar[TimeContext] = contextvars.ContextVar(
    "sdmas_time_context", default=TimeContext()
)


def time_context() -> TimeContext:
    """Return the time context active in the current request/async task."""
    return _time_context_var.get()


def set_time_context(context: TimeContext) -> None:
    """Set the time context for the current request/async task.

    The rewriter (M2) and the TxnManager read this. Callers should restore
    the previous value (``contextvars.Token``) at the end of the request.
    """
    _time_context_var.set(context)


def now_utc() -> datetime:
    """Canonical clock for the temporal engine (aware UTC, microsecond)."""
    return datetime.now(timezone.utc)
