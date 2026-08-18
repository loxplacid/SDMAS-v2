"""Declarative compliance engine — ORM models (TASK 20).

Seven tenant-scoped tables implement the schema-driven compliance framework:

- ``compliance_regulations``    — named regulations with metadata
- ``compliance_requirements``   — specific requirements within a regulation
- ``compliance_schemas``        — versioned schema packs (JSON rule definitions)
- ``compliance_rules``          — individual validation rules within a schema
- ``compliance_submissions``    — batches of data submitted for checking
- ``compliance_evaluations``    — immutable evaluation records (audit trail)
- ``compliance_approvals``      — human sign-off on compliance results

Design: no CBSE/ICSE/state rules are hard-coded.  Schema packs are
loaded as JSON; the evaluator interprets them deterministically.
"""

from __future__ import annotations

import datetime

from sqlalchemy import (
    Boolean,
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


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


# ---------------------------------------------------------------------------
# Regulation
# ---------------------------------------------------------------------------


class ComplianceRegulation(Base):
    """A named regulation (e.g., 'Affiliation Bylaws 2024')."""

    __tablename__ = "compliance_regulations"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("campuses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    regulation_id: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Stable business key (e.g. 'cbse_affiliation_2024')",
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    authority: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Issuing authority (e.g. 'CBSE', 'State Board')",
    )
    jurisdiction: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Geographic / institutional scope",
    )
    effective_from: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    effective_until: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        index=True,
    )
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        UniqueConstraint(
            "campus_id", "regulation_id", name="uq_compliance_regulation_key"
        ),
    )

    requirements: Mapped[list[ComplianceRequirement]] = relationship(
        "ComplianceRequirement",
        back_populates="regulation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<ComplianceRegulation id={self.id} "
            f"key={self.regulation_id!r} status={self.status}>"
        )


# ---------------------------------------------------------------------------
# Requirement
# ---------------------------------------------------------------------------


class ComplianceRequirement(Base):
    """A specific requirement within a regulation."""

    __tablename__ = "compliance_requirements"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("campuses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    regulation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("compliance_regulations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requirement_id: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Stable key within the regulation (e.g. 'R1.2.3')",
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Functional area (student_data, finance, attendance, etc.)",
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="medium",
        comment="Impact if not met: critical, high, medium, low",
    )
    is_mandatory: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    effective_from: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    effective_until: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    regulation: Mapped[ComplianceRegulation] = relationship(
        "ComplianceRegulation", back_populates="requirements"
    )

    __table_args__ = (
        UniqueConstraint(
            "regulation_id",
            "requirement_id",
            name="uq_compliance_requirement_key",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ComplianceRequirement id={self.id} "
            f"key={self.requirement_id!r}>"
        )


# ---------------------------------------------------------------------------
# Schema (versioned rule pack)
# ---------------------------------------------------------------------------


class ComplianceSchema(Base):
    """A versioned schema pack — the JSON rule definitions for requirements.

    A schema pack groups rules for one or more requirements.  Each version
    is immutable; ``is_current`` is a fast-path flag maintained by the
    service.  ``effective_from`` / ``effective_until`` are authoritative.
    """

    __tablename__ = "compliance_schemas"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("campuses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    schema_id: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Stable business key (e.g. 'student_data_schema')",
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Data sources this schema validates against.
    data_sources: Mapped[dict | None] = mapped_column(
        JSONType,
        nullable=True,
        comment='["student", "attendance", "finance", "documents"]',
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    effective_from: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    effective_until: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", index=True
    )
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        UniqueConstraint(
            "schema_id", "version", name="uq_compliance_schema_version"
        ),
    )

    rules: Mapped[list[ComplianceRule]] = relationship(
        "ComplianceRule",
        back_populates="schema",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<ComplianceSchema id={self.id} key={self.schema_id!r} "
            f"v{self.version}>"
        )


# ---------------------------------------------------------------------------
# Rule
# ---------------------------------------------------------------------------


class ComplianceRule(Base):
    """A deterministic validation rule within a schema.

    Each rule defines:
    - ``rule_type``: what to check (field_exists, value_range, count_min,
      custom_query, aggregate_check)
    - ``target``: which data source / entity / field
    - ``condition``: JSON condition to evaluate
    - ``expected``: what the result should be
    - ``severity``: impact if the rule fails
    - ``explanation``: human-readable explanation of what this rule checks
    """

    __tablename__ = "compliance_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("campuses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    schema_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("compliance_schemas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requirement_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("compliance_requirements.id", ondelete="SET NULL"),
        nullable=True,
    )
    rule_code: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Stable code (e.g. 'student.has_roll_number')",
    )
    rule_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment=(
            "field_exists | value_range | value_in_set | "
            "count_min | count_max | ratio_min | "
            "custom_query | aggregate_check"
        ),
    )
    target_entity: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Which entity to check (student, attendance_record, payment, etc.)",
    )
    target_field: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Which field to inspect (for field_exists / value_range)",
    )
    #: JSON condition — structure depends on rule_type.
    condition: Mapped[dict | None] = mapped_column(
        JSONType,
        nullable=True,
        comment="Rule-specific condition parameters",
    )
    #: Expected result for comparison rules.
    expected: Mapped[dict | None] = mapped_column(
        JSONType,
        nullable=True,
        comment="Expected value / threshold",
    )
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="medium"
    )
    is_mandatory: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    explanation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable explanation of what this rule checks and why",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    schema: Mapped[ComplianceSchema] = relationship(
        "ComplianceSchema", back_populates="rules"
    )

    __table_args__ = (
        UniqueConstraint(
            "schema_id", "rule_code", name="uq_compliance_rule_code"
        ),
        Index("ix_compliance_rule_target", "target_entity", "target_field"),
    )

    def __repr__(self) -> str:
        return (
            f"<ComplianceRule id={self.id} code={self.rule_code!r} "
            f"type={self.rule_type}>"
        )


# ---------------------------------------------------------------------------
# Submission
# ---------------------------------------------------------------------------


class ComplianceSubmission(Base):
    """A batch of data submitted for compliance checking.

    Groups one or more evaluations under a single submission with
    approval workflow.
    """

    __tablename__ = "compliance_submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("campuses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    regulation_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("compliance_regulations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    schema_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("compliance_schemas.id", ondelete="SET NULL"),
        nullable=True,
    )
    submission_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Stable business key for this submission batch",
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Snapshot of the data being evaluated.
    data_snapshot: Mapped[dict | None] = mapped_column(
        JSONType, nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
    )
    #: Aggregate result after evaluation.
    total_rules: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    compliance_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="0-100 compliance percentage",
    )
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        UniqueConstraint(
            "campus_id", "submission_id", name="uq_compliance_submission_key"
        ),
    )

    evaluations: Mapped[list[ComplianceEvaluation]] = relationship(
        "ComplianceEvaluation",
        back_populates="submission",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<ComplianceSubmission id={self.id} "
            f"key={self.submission_id!r} score={self.compliance_score}>"
        )


# ---------------------------------------------------------------------------
# Evaluation (immutable audit trail)
# ---------------------------------------------------------------------------


class ComplianceEvaluation(Base):
    """An immutable record of a single rule evaluation.

    Every evaluation is traceable to: submission + rule + input data +
    result + explanation.  Rows are append-only.
    """

    __tablename__ = "compliance_evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("campuses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    submission_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("compliance_submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("compliance_rules.id", ondelete="SET NULL"),
        nullable=True,
    )
    rule_code: Mapped[str] = mapped_column(String(200), nullable=False)
    requirement_id: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    #: pass | fail | warning | skipped | error
    result: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    #: What data was checked (input snapshot for this specific rule).
    input_data: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    #: What the rule expected vs what was found.
    expected_value: Mapped[dict | None] = mapped_column(
        JSONType, nullable=True
    )
    actual_value: Mapped[dict | None] = mapped_column(
        JSONType, nullable=True
    )
    #: Human-readable explanation of this evaluation.
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Deterministic trace — what steps the evaluator took.
    trace: Mapped[dict | None] = mapped_column(
        JSONType,
        nullable=True,
        comment="Step-by-step evaluation trace for explainability",
    )
    evaluated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, index=True
    )

    submission: Mapped[ComplianceSubmission] = relationship(
        "ComplianceSubmission", back_populates="evaluations"
    )

    __table_args__ = (
        Index(
            "ix_compliance_eval_rule",
            "rule_code",
            "result",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ComplianceEvaluation id={self.id} "
            f"rule={self.rule_code!r} result={self.result}>"
        )


# ---------------------------------------------------------------------------
# Approval
# ---------------------------------------------------------------------------


class ComplianceApproval(Base):
    """Human sign-off on a compliance submission result."""

    __tablename__ = "compliance_approvals"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("campuses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    submission_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("compliance_submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="approved | rejected | needs_revision",
    )
    approver_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    def __repr__(self) -> str:
        return (
            f"<ComplianceApproval id={self.id} "
            f"submission={self.submission_id} {self.decision}>"
        )
