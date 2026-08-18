"""Tamper-evident audit chain — ORM models.

Two tables implement the chained integrity layer over ``audit_logs``:

- ``audit_chain_entries`` — one per audit event: the link (``prev_hash``),
  the event payload hash, the current hash, and an HMAC signature
- ``audit_chain_checkpoints`` — periodic signed state hashes covering the
  chain up to a point (so even a deleted tail is detectable)

Chains are **per campus**: ``chain_index`` is sequential within a campus
chain and every link binds the campus id, so a tamper in one tenant can
never break another tenant's chain.  Platform-scoped audit events
(``campus_id`` NULL) form their own chain.

Tenancy: both tables carry ``campus_id`` (direct tenant scoping —
auto-classified ``TENANT_DIRECT``).
"""

from __future__ import annotations

import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class AuditChainEntry(Base):
    """One link in a campus's audit chain, covering one audit event."""

    __tablename__ = "audit_chain_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    audit_log_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("audit_logs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Sequential within the campus chain (0, 1, 2, ...).
    chain_index: Mapped[int] = mapped_column(Integer, nullable=False)
    #: The previous entry's current hash ("" for the first entry).
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Canonical SHA-256 of the audit event's content.
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    #: ``chain_hash(prev_hash, payload_hash, campus_id, chain_index)``.
    current_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    #: HMAC-SHA256(current_hash) with the server secret.
    signature: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        # One chain entry per audit event (idempotent append).
        UniqueConstraint("audit_log_id", name="uq_audit_chain_entry_audit_log"),
        Index("ix_audit_chain_campus_index", "campus_id", "chain_index"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditChainEntry id={self.id} campus={self.campus_id} "
            f"#{self.chain_index} audit={self.audit_log_id}>"
        )


class AuditChainCheckpoint(Base):
    """A signed state hash over the chain up to ``up_to_chain_index``."""

    __tablename__ = "audit_chain_checkpoints"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    #: The chain is covered up to and including this index.
    up_to_chain_index: Mapped[int] = mapped_column(Integer, nullable=False)
    #: SHA-256 over the ordered current hashes up to that index.
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    #: HMAC-SHA256(state_hash | campus | up_to_chain_index).
    signature: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        Index("ix_audit_chain_checkpoint_campus_index", "campus_id", "up_to_chain_index"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditChainCheckpoint id={self.id} campus={self.campus_id} "
            f"up_to=#{self.up_to_chain_index}>"
        )
