"""Universal reconciliation engine — ORM models.

Six tenant-scoped tables implement the generic framework:

- ``reconciliation_runs``          — one reconciliation pass between a
  source and a target dataset
- ``reconciliation_rule_configs``  — named, reusable matching/comparison
  rules (match keys + normalizers + tolerance fields)
- ``reconciliation_matches``       — per-record result with differences
- ``reconciliation_exceptions``    — out-of-tolerance / unmatched records
  requiring manual review
- ``reconciliation_approvals``     — approval trail (approve/reject/escalate)
- ``reconciliation_evidence``      — evidence pointers (audit, files,
  source records, reports)

Status model (runs): ``draft → running → completed | exceptions_pending →
approved → closed``.  A run is *idempotent*: ``idempotency_key`` is unique
per campus, so re-running the same pass returns the existing run instead of
duplicating records.

Tenancy: every table carries ``campus_id`` (direct tenant scoping — the
multi-tenant registry classifies them ``TENANT_DIRECT`` automatically).
"""

from __future__ import annotations

import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base
from app.infrastructure.types import JSONType

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Run lifecycle.
RUN_STATUS_DRAFT = "draft"
RUN_STATUS_RUNNING = "running"
RUN_STATUS_COMPLETED = "completed"
RUN_STATUS_EXCEPTIONS_PENDING = "exceptions_pending"
RUN_STATUS_APPROVED = "approved"
RUN_STATUS_CLOSED = "closed"
RUN_STATUSES = frozenset(
    {
        RUN_STATUS_DRAFT,
        RUN_STATUS_RUNNING,
        RUN_STATUS_COMPLETED,
        RUN_STATUS_EXCEPTIONS_PENDING,
        RUN_STATUS_APPROVED,
        RUN_STATUS_CLOSED,
    }
)

#: Per-record match outcome.
MATCH_STATUS_MATCHED = "matched"
MATCH_STATUS_SOURCE_ONLY = "source_only"
MATCH_STATUS_TARGET_ONLY = "target_only"
MATCH_STATUS_EXCEPTION = "exception"
MATCH_STATUSES = frozenset(
    {
        MATCH_STATUS_MATCHED,
        MATCH_STATUS_SOURCE_ONLY,
        MATCH_STATUS_TARGET_ONLY,
        MATCH_STATUS_EXCEPTION,
    }
)

#: Exception review lifecycle.
EXCEPTION_STATUS_OPEN = "open"
EXCEPTION_STATUS_IN_REVIEW = "in_review"
EXCEPTION_STATUS_RESOLVED = "resolved"
EXCEPTION_STATUS_CLOSED = "closed"
EXCEPTION_STATUSES = frozenset(
    {
        EXCEPTION_STATUS_OPEN,
        EXCEPTION_STATUS_IN_REVIEW,
        EXCEPTION_STATUS_RESOLVED,
        EXCEPTION_STATUS_CLOSED,
    }
)

#: Exception severity.
EXCEPTION_SEVERITY_INFO = "info"
EXCEPTION_SEVERITY_WARNING = "warning"
EXCEPTION_SEVERITY_CRITICAL = "critical"
EXCEPTION_SEVERITIES = frozenset(
    {
        EXCEPTION_SEVERITY_INFO,
        EXCEPTION_SEVERITY_WARNING,
        EXCEPTION_SEVERITY_CRITICAL,
    }
)

#: Approval decisions.
APPROVAL_APPROVE = "approve"
APPROVAL_REJECT = "reject"
APPROVAL_ESCALATE = "escalate"
APPROVAL_DECISIONS = frozenset({APPROVAL_APPROVE, APPROVAL_REJECT, APPROVAL_ESCALATE})

#: Evidence kinds.
EVIDENCE_AUDIT = "audit"
EVIDENCE_FILE = "file"
EVIDENCE_SOURCE_RECORD = "source_record"
EVIDENCE_REPORT = "report"
EVIDENCE_TYPES = frozenset({EVIDENCE_AUDIT, EVIDENCE_FILE, EVIDENCE_SOURCE_RECORD, EVIDENCE_REPORT})

#: Tolerance kinds for comparison fields.
TOLERANCE_EXACT = "exact"
TOLERANCE_ABSOLUTE = "absolute"
TOLERANCE_PERCENT = "percent"
TOLERANCE_DAYS = "days"
TOLERANCE_TYPES = frozenset(
    {TOLERANCE_EXACT, TOLERANCE_ABSOLUTE, TOLERANCE_PERCENT, TOLERANCE_DAYS}
)

#: Normalizers for match keys.
NORMALIZER_EXACT = "exact"
NORMALIZER_LOWER = "lower"
NORMALIZER_DIGITS = "digits"
NORMALIZER_ISO_DATE = "iso_date"
NORMALIZER_NUMERIC = "numeric"
NORMALIZERS = frozenset(
    {
        NORMALIZER_EXACT,
        NORMALIZER_LOWER,
        NORMALIZER_DIGITS,
        NORMALIZER_ISO_DATE,
        NORMALIZER_NUMERIC,
    }
)


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class ReconciliationRun(Base):
    """One reconciliation pass between a source and a target dataset."""

    __tablename__ = "reconciliation_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    #: Use-case label — e.g. ``payment_invoice``, ``student_legacy``,
    #: ``attendance_biometric``, ``transport_boarding``, ``migration_target``,
    #: ``inventory_physical``.
    run_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_dataset: Mapped[str] = mapped_column(String(255), nullable=False)
    target_dataset: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=RUN_STATUS_DRAFT, index=True
    )
    #: List of {source_field, target_field, normalizer} dicts.
    match_keys: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    #: List of {source_field, target_field, tolerance, value} dicts.
    comparison_fields: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    #: Idempotency — re-running the same pass (same campus + key) returns
    #: the existing run.
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    #: Optional reference to the reusable rule config that drove this run.
    rule_config_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("reconciliation_rule_configs.id", ondelete="SET NULL"),
        nullable=True,
    )
    summary: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        UniqueConstraint("campus_id", "idempotency_key", name="uq_reconciliation_run_idempotency"),
    )

    def __repr__(self) -> str:
        return f"<ReconciliationRun id={self.id} type={self.run_type} status={self.status}>"


class ReconciliationRuleConfig(Base):
    """A named, reusable reconciliation rule (match keys + comparison)."""

    __tablename__ = "reconciliation_rule_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    run_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    #: List of {source_field, target_field, normalizer} dicts.
    match_keys: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    #: List of {source_field, target_field, tolerance, value} dicts.
    comparison_fields: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (UniqueConstraint("campus_id", "name", name="uq_reconciliation_rule_name"),)

    def __repr__(self) -> str:
        return f"<ReconciliationRuleConfig id={self.id} name={self.name!r}>"


class ReconciliationMatch(Base):
    """Per-record reconciliation result (tenant-scoped)."""

    __tablename__ = "reconciliation_matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("reconciliation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Reference into the source dataset (e.g. legacy id, biometric id).
    source_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    #: Snapshot of the source record (informational, JSON).
    source_payload: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    #: Reference into the target dataset when matched.
    target_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_payload: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    #: matched | source_only | target_only | exception
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=MATCH_STATUS_MATCHED, index=True
    )
    #: Per-field differences {field: {"source": x, "target": y, "diff": z}}.
    differences: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    within_tolerance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    #: Exception code when this row became an exception (e.g. ``AMOUNT_MISMATCH``).
    exception_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    exception_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        UniqueConstraint("run_id", "source_ref", name="uq_reconciliation_match_source"),
    )

    def __repr__(self) -> str:
        return (
            f"<ReconciliationMatch id={self.id} run={self.run_id} "
            f"source={self.source_ref!r} status={self.status}>"
        )


class ReconciliationException(Base):
    """An out-of-tolerance or unmatched record requiring review."""

    __tablename__ = "reconciliation_exceptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("reconciliation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    match_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("reconciliation_matches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default=EXCEPTION_SEVERITY_WARNING
    )
    reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=EXCEPTION_STATUS_OPEN, index=True
    )
    #: Resolution details {decision, note, corrected_value, ...}.
    resolution: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    resolved_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolved_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    def __repr__(self) -> str:
        return f"<ReconciliationException id={self.id} code={self.code} status={self.status}>"


class ReconciliationApproval(Base):
    """Approval trail entry for a reconciliation run."""

    __tablename__ = "reconciliation_approvals"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("reconciliation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: approve | reject | escalate
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    approver_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    def __repr__(self) -> str:
        return f"<ReconciliationApproval id={self.id} run={self.run_id} decision={self.decision}>"


class ReconciliationEvidence(Base):
    """Evidence pointer for a reconciliation run (referenced, never copied)."""

    __tablename__ = "reconciliation_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("reconciliation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    match_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kind: Mapped[str] = mapped_column(
        String(30), nullable=False, default=EVIDENCE_AUDIT, index=True
    )
    reference: Mapped[str] = mapped_column(String(512), nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        Index(
            "ix_reconciliation_evidence_run_kind_ref",
            "run_id",
            "kind",
            "reference",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ReconciliationEvidence id={self.id} run={self.run_id} "
            f"kind={self.kind} ref={self.reference!r}>"
        )
