"""Explicit actor model for the audit trail.

Every security-sensitive action in SDMAS must be attributable to a
trustworthy actor.  This module defines the canonical, typed set of
actors so that a human action is never silently mislabelled as a
system action (and vice-versa).

The taxonomy matches how the system is operated today:

* ``USER``     — an authenticated human user (the normal case).
* ``PLATFORM`` — an authenticated user holding an explicit platform
  permission (cross-tenant operator).  Still a human, but scoped to
  platform-level operations.
* ``SYSTEM``   — code running inside the application (startup seeding,
  migrations, scheduled maintenance) that is not attributable to a
  logged-in user.
* ``WORKER``   — the background job worker executing queued work on
  behalf of a user or the system.
* ``WEBHOOK``  — an external integration (payment provider, etc.) that
  invokes the API through a signature-verified webhook.

No actor may be represented by a bare ``0`` or a synthetic "system user"
row that pretends to be a person.  Use :func:`system_actor` /
:func:`worker_actor` / :func:`webhook_actor` when no human is present.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Optional

#: Sentinel used to indicate "actor unknown" (only for legacy rows).
#: New audit entries MUST always carry an explicit actor type.
UNKNOWN = "unknown"


class ActorType(str, enum.Enum):
    USER = "user"
    PLATFORM = "platform"
    SYSTEM = "system"
    WORKER = "worker"
    WEBHOOK = "webhook"


@dataclass(frozen=True, slots=True)
class AuditActor:
    """The canonical, explicit actor for an audit event.

    Attributes:
        actor_type: One of :class:`ActorType`.
        actor_id: Stable identifier of the actor (user id, worker id,
            integration name, or ``None`` for anonymous system actions).
        actor_label: Human-readable label (username, worker name,
            provider name).
        metadata: Optional free-form key/value context about the actor
            (e.g. ``{"provider": "razorpay"}`` for webhooks).
    """

    actor_type: ActorType
    actor_id: Optional[str] = None
    actor_label: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Factories ─────────────────────────────────────────────────────

    @classmethod
    def user(cls, user_id: int, username: Optional[str] = None) -> "AuditActor":
        """An authenticated human user.

        ``user_id`` must be a positive real user id — a bare ``0`` (or
        ``None``) is never a valid actor and is rejected loudly rather
        than silently fabricating a fake user.
        """
        if not user_id or user_id <= 0:
            raise ValueError("A USER actor requires a positive real user id")
        return cls(
            actor_type=ActorType.USER,
            actor_id=str(user_id),
            actor_label=username or str(user_id),
        )

    @classmethod
    def platform(cls, user_id: int, username: Optional[str] = None) -> "AuditActor":
        """An authenticated user with explicit platform (cross-tenant) access."""
        if not user_id or user_id <= 0:
            raise ValueError("A PLATFORM actor requires a positive real user id")
        return cls(
            actor_type=ActorType.PLATFORM,
            actor_id=str(user_id),
            actor_label=username or str(user_id),
        )

    @classmethod
    def system(cls, reason: str = "system") -> "AuditActor":
        """Application code running outside any user session.

        ``reason`` names what triggered the system action (e.g.
        ``"migration"``, ``"startup_seed"``) for traceability.
        """
        return cls(
            actor_type=ActorType.SYSTEM,
            actor_id=None,
            actor_label=reason,
        )

    @classmethod
    def worker(cls, worker_id: Optional[str] = None) -> "AuditActor":
        """The background job worker."""
        return cls(
            actor_type=ActorType.WORKER,
            actor_id=worker_id,
            actor_label="job-worker",
        )

    @classmethod
    def webhook(cls, provider: str) -> "AuditActor":
        """An external integration verified by signature."""
        return cls(
            actor_type=ActorType.WEBHOOK,
            actor_id=provider,
            actor_label=provider,
            metadata={"provider": provider},
        )

    # ── Helpers ───────────────────────────────────────────────────────

    @property
    def is_human(self) -> bool:
        return self.actor_type in (ActorType.USER, ActorType.PLATFORM)

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor_type": self.actor_type.value,
            "actor_id": self.actor_id,
            "actor_label": self.actor_label,
        }


def actor_for_user(user: Any) -> AuditActor:
    """Build an actor from a ``User`` ORM object or similar."""
    user_id = getattr(user, "id", None)
    username = getattr(user, "username", None)
    if user_id is None:
        raise ValueError("Cannot build an actor from a user without an id")
    return AuditActor.user(user_id, username)
