from __future__ import annotations

import datetime
from datetime import timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class AuditLog(Base):
    """Immutable record of a mutating operation for compliance auditing.

    Every row captures *who* did *what* to *which resource*, when, and
    from where.  ``details`` stores a JSON snapshot of the before/after
    state so that changes can be reconstructed even if the resource is
    later deleted.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )
    username: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    action: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )
    resource_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    details: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    campus_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} user={self.username} "
            f"action={self.action} resource={self.resource_type}"
            f"[{self.resource_id}]>"
        )
