from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class Guardian(Base):
    """Links a parent user to a student, establishing a guardian relationship.

    This model provides a formal, authorized parent-child link used by the
    ``parent`` domain for authorization and data scoping. The legacy raw-SQL
    ``guardians`` table (which stored name/contact) is separate — this is a
    different table with a distinct name to avoid migration conflicts.
    """

    __tablename__ = "guardian_links"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "student_id", name="uq_guardian_user_student"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relationship: Mapped[str] = mapped_column(
        String(50), nullable=False, default="parent"
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    campus_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("campuses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"<Guardian id={self.id} user_id={self.user_id} "
            f"student_id={self.student_id} relationship={self.relationship}>"
        )
