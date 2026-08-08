"""Operational Case Management — persistence models.

A :class:`Case` represents something requiring human action, created
either manually or promoted from a P7 finding (risk / data-quality).  The
case *references* its source (``source_type`` + ``source_id``) rather than
duplicating it, so the original exception stays the single source of truth.

Lifecycle is controlled: every transition goes through the whitelist in
``CASE_TRANSITIONS`` and appends an immutable :class:`CaseEvent`.  SLA
defaults live in :class:`CaseSLAConfig` (campus-scoped, overridable global
defaults) and the derived due/overdue state is always *calculated* from
``status`` + ``due_at`` + now — never stored as a boolean.
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

#: Case categories (mirror the P7 exception taxonomy + manual tasks).
CASE_TYPES = (
    "attendance",
    "finance",
    "academic",
    "documents",
    "data_quality",
    "admissions",
    "operational",
    "administrative",
)

CASE_PRIORITIES = ("critical", "high", "medium", "low")

#: Lifecycle statuses — controlled, forward-moving with explicit reopen.
CASE_STATUS_OPEN = "open"
CASE_STATUS_ACKNOWLEDGED = "acknowledged"
CASE_STATUS_IN_PROGRESS = "in_progress"
CASE_STATUS_WAITING = "waiting"
CASE_STATUS_RESOLVED = "resolved"
CASE_STATUS_CLOSED = "closed"
CASE_VALID_STATUSES = {
    CASE_STATUS_OPEN,
    CASE_STATUS_ACKNOWLEDGED,
    CASE_STATUS_IN_PROGRESS,
    CASE_STATUS_WAITING,
    CASE_STATUS_RESOLVED,
    CASE_STATUS_CLOSED,
}

#: Terminal states — excluded from open/overdue counts.
CASE_TERMINAL_STATUSES = {CASE_STATUS_RESOLVED, CASE_STATUS_CLOSED}

#: Whitelisted lifecycle transitions.  ``OPEN -> CLOSED`` is NOT allowed;
#: a case must pass through RESOLVED (or be explicitly reopened) first.
CASE_TRANSITIONS: dict[str, set[str]] = {
    CASE_STATUS_OPEN: {
        CASE_STATUS_ACKNOWLEDGED, CASE_STATUS_IN_PROGRESS,
        CASE_STATUS_WAITING, CASE_STATUS_RESOLVED,
    },
    CASE_STATUS_ACKNOWLEDGED: {
        CASE_STATUS_IN_PROGRESS, CASE_STATUS_WAITING,
        CASE_STATUS_RESOLVED, CASE_STATUS_OPEN,
    },
    CASE_STATUS_IN_PROGRESS: {
        CASE_STATUS_WAITING, CASE_STATUS_RESOLVED, CASE_STATUS_OPEN,
    },
    CASE_STATUS_WAITING: {
        CASE_STATUS_IN_PROGRESS, CASE_STATUS_RESOLVED, CASE_STATUS_OPEN,
    },
    CASE_STATUS_RESOLVED: {CASE_STATUS_CLOSED, CASE_STATUS_OPEN},
    CASE_STATUS_CLOSED: {CASE_STATUS_OPEN},
}

#: Immutable event types recorded on the case timeline.
CASE_EVENT_CREATED = "CASE_CREATED"
CASE_EVENT_ASSIGNED = "ASSIGNED"
CASE_EVENT_REASSIGNED = "REASSIGNED"
CASE_EVENT_STATUS_CHANGED = "STATUS_CHANGED"
CASE_EVENT_PRIORITY_CHANGED = "PRIORITY_CHANGED"
CASE_EVENT_COMMENT_ADDED = "COMMENT_ADDED"
CASE_EVENT_EVIDENCE_ADDED = "EVIDENCE_ADDED"
CASE_EVENT_DUE_DATE_CHANGED = "DUE_DATE_CHANGED"
CASE_EVENT_RESOLVED = "RESOLVED"
CASE_EVENT_REOPENED = "REOPENED"
CASE_EVENT_CLOSED = "CLOSED"
CASE_EVENT_ESCALATED = "ESCALATED"

#: Source kinds a case may reference.
CASE_SOURCE_MANUAL = "manual"
CASE_SOURCE_RISK_FINDING = "risk_finding"
CASE_SOURCE_DATA_QUALITY = "data_quality_finding"
CASE_VALID_SOURCES = {
    CASE_SOURCE_MANUAL,
    CASE_SOURCE_RISK_FINDING,
    CASE_SOURCE_DATA_QUALITY,
}

#: Evidence kinds — references to existing system objects, never raw uploads.
CASE_EVIDENCE_KINDS = (
    "attendance_report",
    "fee_receipt",
    "student_document",
    "exported_report",
    "administrative_note",
)


class Case(Base):
    """An operational case requiring human action."""

    __tablename__ = "cases"
    __table_args__ = (
        UniqueConstraint("case_number", name="uq_cases_case_number"),
        UniqueConstraint(
            "campus_id",
            "source_type",
            "source_id",
            name="uq_cases_source",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    case_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    case_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    priority: Mapped[str] = mapped_column(
        String(20), nullable=False, default="medium", index=True
    )
    original_priority: Mapped[str] = mapped_column(
        String(20), nullable=False, default="medium"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=CASE_STATUS_OPEN, index=True
    )
    # Polymorphic reference back to the originating P7 finding.
    source_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default=CASE_SOURCE_MANUAL
    )
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Denormalised for fast student-scoped queries.
    student_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("students.id", ondelete="SET NULL"), nullable=True, index=True
    )

    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_to: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assigned_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    due_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    escalated_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    resolved_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    closed_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Optimistic concurrency guard for targeted updates.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

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
            f"<Case {self.case_number} type={self.case_type} "
            f"status={self.status} priority={self.priority}>"
        )


class CaseEvent(Base):
    """Immutable timeline entry for a case.

    Never edited or deleted — enterprise accountability for every action
    taken on a case (creation, assignment, transitions, comments, evidence,
    escalation, resolution, closure).
    """

    __tablename__ = "case_events"
    __table_args__ = (
        UniqueConstraint("case_id", "event_seq", name="uq_case_events_seq"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<CaseEvent case={self.case_id} seq={self.event_seq} type={self.event_type}>"


class CaseComment(Base):
    """A user comment on a case.

    Append-only: comments are never edited in place (preserving the audit
    trail).  Plain text with safe formatting — no rich-text editor.
    """

    __tablename__ = "case_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    author_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<CaseComment case={self.case_id} author={self.author_id}>"


class CaseEvidence(Base):
    """A controlled reference to supporting evidence.

    ``kind`` selects the evidence domain (attendance report, fee receipt,
    student document, exported report, note).  ``reference_type`` +
    ``reference_id`` point at the existing system object; ``summary`` is a
    short human description.  No raw files are stored here — the existing
    document/storage architecture owns files, this only references them.
    """

    __tablename__ = "case_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    added_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"<CaseEvidence case={self.case_id} kind={self.kind} "
            f"ref={self.reference_type}:{self.reference_id}>"
        )


class CaseSLAConfig(Base):
    """Configurable default SLA rules by case type + priority.

    ``campus_id`` NULL = global default; a campus row overrides the global
    row for the same ``case_type``/``priority``.  ``after_hours`` is the
    default resolution deadline; ``escalation_after_hours`` is the point at
    which a still-open overdue case escalates (``None`` = no escalation).
    """

    __tablename__ = "case_sla_configs"
    __table_args__ = (
        UniqueConstraint(
            "campus_id",
            "case_type",
            "priority",
            name="uq_case_sla_config_type_priority",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="CASCADE"), nullable=True, index=True
    )
    case_type: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    after_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    escalation_after_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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
            f"<CaseSLAConfig campus={self.campus_id} type={self.case_type} "
            f"pri={self.priority} h={self.after_hours}>"
        )
