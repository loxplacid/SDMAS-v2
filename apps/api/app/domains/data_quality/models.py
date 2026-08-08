"""Data Quality Center — persistence models.

Deterministic data-quality checks are *persisted* exactly like risk
findings so that:
  - reads are cheap (no per-request re-scan),
  - every finding is an immutable, auditable snapshot,
  - resolution/ignoring is an explicit, audited lifecycle action.

One table: ``data_quality_findings``. Status is ``open`` until resolved
or ignored. On re-run, findings whose check no longer fires are closed
as ``resolved`` with reason ``rule_no_longer_applies`` (history is
preserved, never deleted).
"""

from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Deterministic check categories (map to the Data Quality Center tabs).
DQ_CATEGORIES = (
    "duplicates",
    "missing_fields",
    "invalid_format",
    "impossible_dates",
    "inconsistent_references",
)

DQ_SEVERITIES = ("critical", "high", "medium", "low")

DQ_STATUS_OPEN = "open"
DQ_STATUS_RESOLVED = "resolved"
DQ_STATUS_IGNORED = "ignored"
DQ_VALID_STATUSES = {DQ_STATUS_OPEN, DQ_STATUS_RESOLVED, DQ_STATUS_IGNORED}

# Entity types a finding may point at.
DQ_ENTITY_STUDENT = "student"
DQ_ENTITY_ATTENDANCE = "attendance_record"
DQ_ENTITY_FEE_DUE = "fee_due"
DQ_ENTITY_PAYMENT = "payment"
DQ_ENTITY_ENROLLMENT = "enrollment"


class DataQualityFinding(Base):
    """A single deterministic data-quality finding for one entity.

    ``check_code`` is the stable identity of the check that produced it
    (e.g. ``duplicate_students``, ``student_invalid_email``). ``field``
    names the offending column/attribute where applicable.
    """

    __tablename__ = "data_quality_findings"
    __table_args__ = (
        UniqueConstraint(
            "campus_id",
            "check_code",
            "entity_type",
            "entity_id",
            "field",
            name="uq_data_quality_finding_entity_check",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="CASCADE"), nullable=True, index=True
    )
    check_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # Denormalised for fast student-scoped queries.
    student_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=True, index=True
    )
    field: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # Deterministic snapshot of the check inputs, for explainability + audit.
    evidence: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DQ_STATUS_OPEN, index=True
    )
    detected_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    last_verified_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    resolved_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
            f"<DataQualityFinding id={self.id} check={self.check_code} "
            f"entity={self.entity_type}:{self.entity_id} "
            f"severity={self.severity} status={self.status}>"
        )
