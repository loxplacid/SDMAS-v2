"""Universal Exception Management — persistence models.

A :class:`SystemException` is the canonical, tenant-scoped representation for
all system-detected issues that require tracking, investigation, and
potentially human action.

Design rationale:

1. **One model for all sources**: data-quality findings, financial anomalies,
   risk signals, migration errors, compliance violations, and manual reports
   all become ``SystemException`` records.  This gives operators a single
   place to see *everything* requiring attention.

2. **Optional Case link**: When human action is needed, a ``Case`` can be
   created and linked.  The exception remains the source of truth for the
   *issue*; the case tracks the *human workflow* to resolve it.

3. **Optional Workflow link**: For structured resolution processes, an
   ``WorkflowInstance`` can be attached.

4. **Backward compatibility**: Existing domains (data_quality, risk, finance,
   migration) can create exceptions *without* changing their current
   lifecycle.  The exception is an additional, normalized layer.

5. **Immutable event timeline**: Every state change is recorded in
   ``SystemExceptionEvent``, providing a complete audit trail.

Lifecycle: ``open → acknowledged → in_progress → resolved → closed``

The ``due_at`` field is calculated from severity-based SLA defaults
(configurable per campus via ``ExceptionSLAConfig``).
"""

from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base
from app.infrastructure.types import JSONType

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Exception type taxonomy — maps to the originating domain.
EXCEPTION_TYPE_DATA_QUALITY = "data_quality"
EXCEPTION_TYPE_FINANCIAL = "financial"
EXCEPTION_TYPE_RISK = "risk"
EXCEPTION_TYPE_MIGRATION = "migration"
EXCEPTION_TYPE_COMPLIANCE = "compliance"
EXCEPTION_TYPE_OPERATIONAL = "operational"
EXCEPTION_TYPE_MANUAL = "manual"

EXCEPTION_TYPES = frozenset(
    {
        EXCEPTION_TYPE_DATA_QUALITY,
        EXCEPTION_TYPE_FINANCIAL,
        EXCEPTION_TYPE_RISK,
        EXCEPTION_TYPE_MIGRATION,
        EXCEPTION_TYPE_COMPLIANCE,
        EXCEPTION_TYPE_OPERATIONAL,
        EXCEPTION_TYPE_MANUAL,
    }
)

#: Severity levels.
EXCEPTION_SEVERITY_INFO = "info"
EXCEPTION_SEVERITY_LOW = "low"
EXCEPTION_SEVERITY_MEDIUM = "medium"
EXCEPTION_SEVERITY_HIGH = "high"
EXCEPTION_SEVERITY_CRITICAL = "critical"

EXCEPTION_SEVERITIES = frozenset(
    {
        EXCEPTION_SEVERITY_INFO,
        EXCEPTION_SEVERITY_LOW,
        EXCEPTION_SEVERITY_MEDIUM,
        EXCEPTION_SEVERITY_HIGH,
        EXCEPTION_SEVERITY_CRITICAL,
    }
)

#: Lifecycle statuses.
EXCEPTION_STATUS_OPEN = "open"
EXCEPTION_STATUS_ACKNOWLEDGED = "acknowledged"
EXCEPTION_STATUS_IN_PROGRESS = "in_progress"
EXCEPTION_STATUS_RESOLVED = "resolved"
EXCEPTION_STATUS_CLOSED = "closed"

EXCEPTION_VALID_STATUSES = frozenset(
    {
        EXCEPTION_STATUS_OPEN,
        EXCEPTION_STATUS_ACKNOWLEDGED,
        EXCEPTION_STATUS_IN_PROGRESS,
        EXCEPTION_STATUS_RESOLVED,
        EXCEPTION_STATUS_CLOSED,
    }
)

#: Terminal statuses — excluded from open/overdue counts.
EXCEPTION_TERMINAL_STATUSES = frozenset({EXCEPTION_STATUS_RESOLVED, EXCEPTION_STATUS_CLOSED})

#: Whitelisted lifecycle transitions.
EXCEPTION_TRANSITIONS: dict[str, set[str]] = {
    EXCEPTION_STATUS_OPEN: {
        EXCEPTION_STATUS_ACKNOWLEDGED,
        EXCEPTION_STATUS_IN_PROGRESS,
        EXCEPTION_STATUS_RESOLVED,
    },
    EXCEPTION_STATUS_ACKNOWLEDGED: {
        EXCEPTION_STATUS_IN_PROGRESS,
        EXCEPTION_STATUS_RESOLVED,
        EXCEPTION_STATUS_OPEN,
    },
    EXCEPTION_STATUS_IN_PROGRESS: {
        EXCEPTION_STATUS_RESOLVED,
        EXCEPTION_STATUS_OPEN,
    },
    EXCEPTION_STATUS_RESOLVED: {
        EXCEPTION_STATUS_CLOSED,
        EXCEPTION_STATUS_OPEN,
    },
    EXCEPTION_STATUS_CLOSED: {
        EXCEPTION_STATUS_OPEN,  # Reopen
    },
}

#: Immutable event types recorded on the exception timeline.
EXCEPTION_EVENT_CREATED = "EXCEPTION_CREATED"
EXCEPTION_EVENT_STATUS_CHANGED = "STATUS_CHANGED"
EXCEPTION_EVENT_ASSIGNED = "ASSIGNED"
EXCEPTION_EVENT_REASSIGNED = "REASSIGNED"
EXCEPTION_EVENT_SEVERITY_CHANGED = "SEVERITY_CHANGED"
EXCEPTION_EVENT_DUE_DATE_CHANGED = "DUE_DATE_CHANGED"
EXCEPTION_EVENT_EVIDENCE_ADDED = "EVIDENCE_ADDED"
EXCEPTION_EVENT_CASE_LINKED = "CASE_LINKED"
EXCEPTION_EVENT_WORKFLOW_LINKED = "WORKFLOW_LINKED"
EXCEPTION_EVENT_RESOLVED = "RESOLVED"
EXCEPTION_EVENT_REOPENED = "REOPENED"
EXCEPTION_EVENT_CLOSED = "CLOSED"
EXCEPTION_EVENT_ROOT_CAUSE_SET = "ROOT_CAUSE_SET"

#: Source domain constants — where the exception originated.
SOURCE_DOMAIN_DATA_QUALITY = "data_quality"
SOURCE_DOMAIN_RISK = "risk"
SOURCE_DOMAIN_FINANCE = "finance"
SOURCE_DOMAIN_MIGRATION = "migration"
SOURCE_DOMAIN_MANUAL = "manual"
SOURCE_DOMAIN_SYSTEM = "system"


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class SystemException(Base):
    """A universal, tenant-scoped exception requiring tracking and resolution.

    One row per detected issue.  The ``source_domain`` + ``source_type`` +
    ``source_id`` triple uniquely identifies the originating record; combined
    with ``campus_id``, this prevents duplicate exceptions for the same issue.

    When human action is needed, ``case_id`` links to an operational ``Case``.
    For structured workflows, ``workflow_instance_id`` attaches a
    ``WorkflowInstance``.
    """

    __tablename__ = "system_exceptions"
    __table_args__ = (
        UniqueConstraint(
            "campus_id",
            "source_domain",
            "source_type",
            "source_id",
            name="uq_system_exception_source",
        ),
        Index(
            "ix_system_exception_entity",
            "entity_type",
            "entity_id",
        ),
        Index(
            "ix_system_exception_student",
            "student_id",
        ),
        Index(
            "ix_system_exception_status",
            "status",
        ),
        Index(
            "ix_system_exception_due",
            "due_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # --- Source provenance ---
    source_domain: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Domain that created the exception "
        "(data_quality, risk, finance, migration, manual)",
    )
    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Entity type in the source domain (e.g., 'finding', 'anomaly', 'import_error')",
    )
    source_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="ID of the source record (risk finding, DQ finding, payment, etc.)",
    )

    # --- Classification ---
    exception_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="High-level type: data_quality, financial, risk, migration, "
        "compliance, operational, manual",
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Severity: info, low, medium, high, critical",
    )
    rule_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Stable rule/check code that detected this "
        "(e.g., 'duplicate_students', 'payment_no_receipt')",
    )

    # --- Entity reference ---
    entity_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Target entity type (student, payment, migration_project, etc.)",
    )
    entity_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Target entity ID",
    )
    student_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("students.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Denormalized for fast student-scoped queries (Student 360)",
    )

    # --- Title & description ---
    title: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        comment="Short human-readable title",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed description of the issue",
    )

    # --- Lifecycle ---
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=EXCEPTION_STATUS_OPEN,
        index=True,
    )

    # --- Ownership ---
    owner_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Assigned investigator/resolver",
    )
    created_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # --- SLA ---
    due_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Resolution deadline (calculated from severity + SLA config)",
    )
    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="medium",
        index=True,
        comment="Operational priority (critical, high, medium, low) — may differ from severity",
    )

    # --- Resolution ---
    root_cause: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Root cause analysis after investigation",
    )
    resolution_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="How it was resolved: fixed, accepted_risk, false_positive, duplicate, no_action",
    )
    resolution_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Free-text resolution note",
    )
    resolved_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolved_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    closed_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    closed_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # --- Evidence ---
    evidence: Mapped[dict | None] = mapped_column(
        JSONType,
        nullable=True,
        comment="Deterministic snapshot of the check inputs for explainability + audit",
    )

    # --- Links ---
    case_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Optional link to an operational Case for human action",
    )
    workflow_instance_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("workflow_instances.id", ondelete="SET NULL"),
        nullable=True,
        comment="Optional link to a structured WorkflowInstance",
    )

    # --- Audit ---
    detected_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
        comment="When the issue was first detected",
    )
    last_verified_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
        comment="Last time the issue was confirmed to still exist",
    )
    acknowledged_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    acknowledged_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    in_progress_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # --- Concurrency ---
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # --- Timestamps ---
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
        onupdate=_now,
    )

    # --- Relationships ---
    events: Mapped[list[SystemExceptionEvent]] = relationship(
        "SystemExceptionEvent",
        back_populates="exception",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="SystemExceptionEvent.event_seq",
    )

    def __repr__(self) -> str:
        return (
            f"<SystemException id={self.id} type={self.exception_type} "
            f"severity={self.severity} status={self.status}>"
        )


class SystemExceptionEvent(Base):
    """Immutable timeline entry for a system exception.

    Never edited or deleted — enterprise accountability for every action
    taken on an exception (creation, assignment, transitions, evidence,
    resolution, closure).
    """

    __tablename__ = "system_exception_events"
    __table_args__ = (
        UniqueConstraint("exception_id", "event_seq", name="uq_system_exception_events_seq"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    exception_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("system_exceptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
    )

    # --- Relationship ---
    exception: Mapped[SystemException] = relationship("SystemException", back_populates="events")

    def __repr__(self) -> str:
        return (
            f"<SystemExceptionEvent exception={self.exception_id} "
            f"seq={self.event_seq} type={self.event_type}>"
        )


class ExceptionSLAConfig(Base):
    """Configurable default SLA rules by exception type + severity.

    ``campus_id`` NULL = global default; a campus row overrides the global
    row for the same ``exception_type``/``severity``.  ``after_hours`` is the
    default resolution deadline.
    """

    __tablename__ = "exception_sla_configs"
    __table_args__ = (
        UniqueConstraint(
            "campus_id",
            "exception_type",
            "severity",
            name="uq_exception_sla_config_type_severity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="CASCADE"), nullable=True, index=True
    )
    exception_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    after_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    updated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
        onupdate=_now,
    )

    def __repr__(self) -> str:
        return (
            f"<ExceptionSLAConfig campus={self.campus_id} "
            f"type={self.exception_type} sev={self.severity} h={self.after_hours}>"
        )
