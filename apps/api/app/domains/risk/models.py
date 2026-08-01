"""Risk & Attention Engine — persistence models.

Deterministic, rule-based risk findings are *persisted* so that:
  - reads are cheap (no per-request aggregation),
  - every finding is an immutable, auditable snapshot (detected_at,
    score, reason, evidence),
  - resolution is an explicit, auditable action (nobody can silently
    change a result).

Two tables:

- ``risk_rule_configs`` — school-level configuration. A row keyed by
  (campus_id, rule_code); ``campus_id`` may be ``NULL`` for the global
  default row. Effective config = global default overlaid by the
  campus row.
- ``risk_findings`` — one row per detected risk per entity. Status is
  ``open`` until resolved or acknowledged. A finding is re-evaluated on
  recompute: if the rule no longer fires, the row is closed with reason
  ``rule_no_longer_applies`` (preserving history instead of deleting).
"""

from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
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

RISK_CATEGORIES = (
    "attendance",
    "finance",
    "academic",
    "documents",
    "admissions",
    "operational",
)

RISK_SEVERITIES = ("critical", "high", "medium", "low")

RISK_STATUS_OPEN = "open"
RISK_STATUS_ACKNOWLEDGED = "acknowledged"
RISK_STATUS_RESOLVED = "resolved"
RISK_VALID_STATUSES = {
    RISK_STATUS_OPEN,
    RISK_STATUS_ACKNOWLEDGED,
    RISK_STATUS_RESOLVED,
}

# Entity types a finding may point at.
RISK_ENTITY_STUDENT = "student"
RISK_ENTITY_ADMISSION = "admission_application"
RISK_ENTITY_OPERATIONAL = "operational"


class RiskRuleConfig(Base):
    """School-level configuration for a single rule.

    ``campus_id`` ``NULL`` = global default (seeded once). A campus row
    with the same ``rule_code`` overrides the global defaults.
    """

    __tablename__ = "risk_rule_configs"
    __table_args__ = (
        UniqueConstraint(
            "campus_id", "rule_code", name="uq_risk_rule_config_campus_rule"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="CASCADE"), nullable=True, index=True
    )
    rule_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Thresholds specific to the rule (e.g. {"percentage": 75, "window_days": 60}).
    thresholds: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Optional per-severity overrides, e.g. {"critical_threshold": 90}.
    severity_overrides: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
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
            f"<RiskRuleConfig campus={self.campus_id} "
            f"rule={self.rule_code} enabled={self.enabled}>"
        )


class RiskFinding(Base):
    """A single deterministic risk finding for one entity (usually a student).

    Persisted so the Command Center, Student 360 and the Risk Center can
    read a consistent snapshot without recomputing on every request.
    """

    __tablename__ = "risk_findings"
    __table_args__ = (
        UniqueConstraint(
            "campus_id",
            "entity_type",
            "entity_id",
            "rule_code",
            "status",
            name="uq_risk_finding_entity_rule",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="CASCADE"), nullable=True, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # Denormalised for fast student-scoped queries (Student 360).
    student_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=True, index=True
    )
    rule_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    # Deterministic snapshot of the rule inputs, for explainability + audit.
    evidence: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RISK_STATUS_OPEN, index=True
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
            f"<RiskFinding id={self.id} rule={self.rule_code} "
            f"entity={self.entity_type}:{self.entity_id} "
            f"severity={self.severity} status={self.status}>"
        )
