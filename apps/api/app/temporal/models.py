"""Engine-level ORM models for The Archive (M1).

``txn_log`` is the append-only transaction ledger: one row per close-open
write, carrying the ChangeEnvelope (old/new state, actor, reason) and the
tenancy scope. It is created by the ``create_temporal_txn_log`` migration
and, in tests, by ``Base.metadata.create_all``.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, Text, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class _JSON(TypeDecorator):
    """Portable JSON — JSONB on PostgreSQL, JSON on every other dialect."""

    impl = JSONB

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB as _PG_JSONB

            return dialect.type_descriptor(_PG_JSONB())
        from sqlalchemy import JSON as _SA_JSON

        return dialect.type_descriptor(_SA_JSON())

    def process_bind_param(self, value: Any, dialect) -> str | None:
        if value is not None:
            return json.dumps(value, default=_json_default)
        return None

    def process_result_value(self, value: Any, dialect) -> Any:
        if isinstance(value, str):
            return json.loads(value)
        return value


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
    change: Mapped[dict[str, Any] | None] = mapped_column(_JSON(), nullable=True)

    __table_args__ = (
        Index("ix_txn_log_entity", "entity_type", "entity_id", "txn_ts"),
        Index("ix_txn_log_ts", "txn_ts"),
        Index("ix_txn_log_actor", "actor_id"),
        Index("ix_txn_log_tenant", "tenant_id", "campus_id"),
    )
