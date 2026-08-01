"""Correlation, actor, and tenant context propagation for domain events.

Uses ``contextvars`` so that events dispatched deep inside a request (or a
nested handler) automatically inherit:

- the incoming ``correlation_id`` (end-to-end trace across handlers/events)
- the ``actor_user_id`` who triggered the business operation
- the ``school_id`` (tenant) that scopes the operation

Handlers and nested dispatches observe the same context, which keeps events
deterministic and traceable without threading parameters through call sites.
"""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Iterator

_correlation_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "events_correlation_id", default=None
)
_actor_var: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "events_actor_user_id", default=None
)
_school_var: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "events_school_id", default=None
)


def get_correlation_id() -> str | None:
    """Return the current correlation id (or None when unset)."""
    return _correlation_var.get()


def get_actor_user_id() -> int | None:
    """Return the current actor user id (or None when unset)."""
    return _actor_var.get()


def get_school_id() -> int | None:
    """Return the current school/tenant id (or None when unset)."""
    return _school_var.get()


@contextmanager
def event_context(
    *,
    correlation_id: str | None = None,
    actor_user_id: int | None = None,
    school_id: int | None = None,
) -> Iterator[None]:
    """Context manager that sets event context for the enclosed block.

    Any value passed as ``None`` leaves the current context unchanged, so
    nested dispatches can extend context without clobbering it.

    Usage::

        with event_context(correlation_id="abc", actor_user_id=7, school_id=3):
            await dispatcher.dispatch(event, session=session)
    """
    tokens: list = []
    if correlation_id is not None:
        tokens.append((_correlation_var, _correlation_var.set(correlation_id)))
    if actor_user_id is not None:
        tokens.append((_actor_var, _actor_var.set(actor_user_id)))
    if school_id is not None:
        tokens.append((_school_var, _school_var.set(school_id)))
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)
