from __future__ import annotations

import datetime
import uuid
from datetime import timezone

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


def _new_event_id() -> str:
    return uuid.uuid4().hex


class AuditLog(Base):
    """Immutable record of a security-sensitive operation.

    Every row captures the canonical audit event structure:

    * ``event_id``         — stable event identifier (UUID hex)
    * ``tenant_id``        — top-level institution (``None`` for platform)
    * ``campus_id``        — concrete campus scope
    * ``actor_type``       — explicit actor category (user/platform/system/
      worker/webhook); never a bare ``0``
    * ``actor_id``         — stable actor identifier
    * ``user_id``/``username`` — denormalized legacy columns kept for
      compatibility with existing queries (migrate to ``actor_*``)
    * ``action``           — semantic action (CREATE, UPDATE, VERIFY, …)
    * ``resource_type``/``resource_id`` — what was acted upon
    * ``request_id``/``correlation_id`` — end-to-end trace ids
    * ``ip_address``/``user_agent`` — network origin
    * ``before_state``/``after_state`` — structured JSON snapshots
    * ``result``/``failure_reason`` — outcome (SUCCESS/FAILURE)
    * ``details``/``metadata`` — free-form JSON payloads

    Rows are append-only; no ``UPDATE``/``DELETE`` should ever target the
    audit table from application code.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(
        String(32), nullable=False, default=_new_event_id, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )
    username: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    actor_type: Mapped[str | None] = mapped_column(
        String(20), nullable=True, index=True
    )
    actor_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    resource_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    tenant_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )
    campus_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )
    request_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    correlation_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    before_state: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    after_state: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    result: Mapped[str | None] = mapped_column(
        String(20), nullable=True, index=True
    )
    failure_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    details: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    # ``metadata`` is a reserved name in SQLAlchemy's Declarative API, so
    # the Python attribute is ``metadata_json`` mapped to the DB column
    # ``metadata`` (see migration 035_harden_audit_logs).
    metadata_json: Mapped[str | None] = mapped_column(
        "metadata", Text, nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        index=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "event_id", name="uq_audit_logs_event_id"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog event={self.event_id} actor={self.actor_type}:"
            f"{self.actor_id or self.username} action={self.action} "
            f"resource={self.resource_type}[{self.resource_id}]>"
        )
