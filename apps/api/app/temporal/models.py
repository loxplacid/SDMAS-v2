"""Engine-level ORM models for The Archive (M1).

``txn_log`` is the append-only transaction ledger: one row per close-open
write, carrying the ChangeEnvelope (old/new state, actor, reason) and the
tenancy scope. It is created by the ``create_temporal_txn_log`` migration
and, in tests, by ``Base.metadata.create_all``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base
from app.infrastructure.types import JSONType


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class TxnLog(Base):
    """Append-only transaction ledger (close-open write log).

    One row per temporal write: ``action`` (create/update/delete/…),
    ``entity_type``/``entity_id`` (what changed), the ``change`` envelope
    (old state, new state, actor, reason, txn instant), and the tenancy
    scope. Rows are immutable; ``undo``/``redo`` append new rows rather
    than mutating history.
    """

    __tablename__ = "txn_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    txn_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    campus_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    change: Mapped[dict[str, Any] | None] = mapped_column(
        JSONType(json_default=_json_default), nullable=True
    )

    __table_args__ = (
        Index("ix_txn_log_entity", "entity_type", "entity_id", "txn_ts"),
        Index("ix_txn_log_ts", "txn_ts"),
        Index("ix_txn_log_actor", "actor_id"),
        Index("ix_txn_log_tenant", "tenant_id", "campus_id"),
    )
