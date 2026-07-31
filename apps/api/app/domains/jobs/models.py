from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Integer, String, Text, TypeDecorator, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


# Works with both PostgreSQL (JSONB) and SQLite (Text-based JSON)
class _JSON(TypeDecorator):
    impl = JSONB

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB as _PG_JSONB
            return dialect.type_descriptor(_PG_JSONB())
        from sqlalchemy import JSON as _SA_JSON
        return dialect.type_descriptor(_SA_JSON())

    def process_bind_param(self, value: Any, dialect) -> str | None:
        import json
        if value is not None:
            return json.dumps(value)
        return None

    def process_result_value(self, value: Any, dialect) -> Any:
        import json
        if isinstance(value, str):
            return json.loads(value)
        return value


JSONType = _JSON


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True, default="pending"
    )
    params: Mapped[dict[str, Any] | None] = mapped_column(
        JSONType, nullable=True, default=None
    )
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100, index=True
    )
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    scheduled_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True, default=None
    )
    started_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    result: Mapped[dict[str, Any] | None] = mapped_column(
        JSONType, nullable=True, default=None
    )
    identity_key: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, default=None
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True, default=None
    )
    campus_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True, default=None
    )

    __table_args__ = (
        UniqueConstraint("identity_key", name="uq_jobs_identity_key"),
    )

    def __repr__(self) -> str:
        return (
            f"<Job id={self.id} type={self.job_type} "
            f"status={self.status} retry={self.retry_count}>"
        )
