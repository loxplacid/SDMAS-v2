from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base
from app.infrastructure.types import JSONType


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True, default="pending")
    params: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True, default=None)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100, index=True)
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
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True, default=None)
    identity_key: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, default=None
    )
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True, default=None)
    campus_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True, default=None)

    __table_args__ = (UniqueConstraint("identity_key", name="uq_jobs_identity_key"),)

    def __repr__(self) -> str:
        return (
            f"<Job id={self.id} type={self.job_type} status={self.status} retry={self.retry_count}>"
        )
