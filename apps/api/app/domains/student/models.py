from __future__ import annotations

import datetime
from datetime import timezone

from sqlalchemy import DateTime, Integer, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


# ---------------------------------------------------------------------------
# Student lifecycle state machine
# ---------------------------------------------------------------------------

# The canonical student lifecycle, aligned with the existing admission
# workflow (inquiry -> ... -> student_created) and enrollment schema:
#   prospective -> admitted -> enrolled -> active -> transferred/withdrawn
#   active -> graduated -> alumni
#
# ``inactive`` is retained as a legacy status for backward compatibility
# with the original deactivate/reactivate flow.

STUDENT_STATUS_PROSPECTIVE = "prospective"
STUDENT_STATUS_ADMITTED = "admitted"
STUDENT_STATUS_ENROLLED = "enrolled"
STUDENT_STATUS_ACTIVE = "active"
STUDENT_STATUS_TRANSFERRED = "transferred"
STUDENT_STATUS_WITHDRAWN = "withdrawn"
STUDENT_STATUS_GRADUATED = "graduated"
STUDENT_STATUS_ALUMNI = "alumni"
STUDENT_STATUS_INACTIVE = "inactive"

# Ordered lifecycle for display/filtering purposes.
STUDENT_LIFECYCLE_ORDER: tuple[str, ...] = (
    STUDENT_STATUS_PROSPECTIVE,
    STUDENT_STATUS_ADMITTED,
    STUDENT_STATUS_ENROLLED,
    STUDENT_STATUS_ACTIVE,
    STUDENT_STATUS_TRANSFERRED,
    STUDENT_STATUS_WITHDRAWN,
    STUDENT_STATUS_GRADUATED,
    STUDENT_STATUS_ALUMNI,
)

# All statuses a student can ever hold (lifecycle + legacy inactive).
STUDENT_STATUSES: frozenset[str] = frozenset(
    (*STUDENT_LIFECYCLE_ORDER, STUDENT_STATUS_INACTIVE)
)

# Deterministic, auditable transition map.  Each key lists the statuses
# that may be reached from it.  Transitions not listed here are rejected.
ALLOWED_LIFECYCLE_TRANSITIONS: dict[str, set[str]] = {
    STUDENT_STATUS_PROSPECTIVE: {STUDENT_STATUS_ADMITTED, STUDENT_STATUS_WITHDRAWN},
    STUDENT_STATUS_ADMITTED: {STUDENT_STATUS_ENROLLED, STUDENT_STATUS_WITHDRAWN},
    STUDENT_STATUS_ENROLLED: {STUDENT_STATUS_ACTIVE, STUDENT_STATUS_TRANSFERRED, STUDENT_STATUS_WITHDRAWN},
    STUDENT_STATUS_ACTIVE: {
        STUDENT_STATUS_ENROLLED,
        STUDENT_STATUS_TRANSFERRED,
        STUDENT_STATUS_WITHDRAWN,
        STUDENT_STATUS_GRADUATED,
        STUDENT_STATUS_INACTIVE,  # legacy deactivate
    },
    STUDENT_STATUS_TRANSFERRED: {STUDENT_STATUS_WITHDRAWN},
    STUDENT_STATUS_WITHDRAWN: set(),
    STUDENT_STATUS_GRADUATED: {STUDENT_STATUS_ALUMNI},
    STUDENT_STATUS_ALUMNI: set(),
    STUDENT_STATUS_INACTIVE: {STUDENT_STATUS_ACTIVE},  # legacy reactivate
}


class StudentLifecycleEvent(Base):
    """Immutable audit trail of a student lifecycle transition.

    Every ``transition`` call persists one row here before updating
    ``Student.status``, so the full lifecycle history of a student is
    always reconstructable and tenant-scoped (``campus_id``).
    """

    __tablename__ = "student_lifecycle_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_status: Mapped[str] = mapped_column(String(20), nullable=False)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"<StudentLifecycleEvent id={self.id} "
            f"student={self.student_id} {self.from_status}->{self.to_status}>"
        )


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    student_number: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True
    )
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_of_birth: Mapped[datetime.date | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Student id={self.id} number={self.student_number} name={self.first_name} {self.last_name}>"