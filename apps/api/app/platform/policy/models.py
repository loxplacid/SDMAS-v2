"""Policy-as-code foundation — ORM models.

Three tenant-scoped tables implement the versioned policy engine:

- ``policy_definitions``  — a named policy with a stable business key
  (``policy_id``), scope, and lifecycle status
- ``policy_versions``     — immutable versioned snapshots: rules +
  exceptions + applicability, effective dates, approval metadata
- ``policy_evaluations``  — persisted evaluation records (traceability:
  policy version + input data + result)

Versioning model: a policy has one *current* version (maintained by the
service); publishing a new version ends the previous one's effective window
(``effective_until = new effective_from``) so the version chain stays
contiguous and deterministic.  ``effective_from <= now < effective_until``
is authoritative; ``is_current`` is a fast-path flag the service maintains.

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

#: Supported policy scopes (catalogue in registry.py).  Future use cases:
#: attendance, fees, admissions, approvals, compliance, security, workflow.
POLICY_SCOPE_ATTENDANCE = "attendance"
POLICY_SCOPE_FEES = "fees"
POLICY_SCOPE_ADMISSIONS = "admissions"
POLICY_SCOPE_APPROVALS = "approvals"
POLICY_SCOPE_COMPLIANCE = "compliance"
POLICY_SCOPE_SECURITY = "security"
POLICY_SCOPE_WORKFLOW = "workflow"
POLICY_SCOPE_GLOBAL = "global"
POLICY_SCOPES = frozenset(
    {
        POLICY_SCOPE_ATTENDANCE,
        POLICY_SCOPE_FEES,
        POLICY_SCOPE_ADMISSIONS,
        POLICY_SCOPE_APPROVALS,
        POLICY_SCOPE_COMPLIANCE,
        POLICY_SCOPE_SECURITY,
        POLICY_SCOPE_WORKFLOW,
        POLICY_SCOPE_GLOBAL,
    }
)

#: Policy definition lifecycle.
POLICY_STATUS_DRAFT = "draft"
POLICY_STATUS_ACTIVE = "active"
POLICY_STATUS_RETIRED = "retired"
POLICY_STATUSES = frozenset({POLICY_STATUS_DRAFT, POLICY_STATUS_ACTIVE, POLICY_STATUS_RETIRED})

#: Version lifecycle (publish is the approval action — it stamps approval
#: metadata and opens the effective window).
VERSION_STATUS_DRAFT = "draft"
VERSION_STATUS_PUBLISHED = "published"
VERSION_STATUS_RETIRED = "retired"
VERSION_STATUSES = frozenset(
    {VERSION_STATUS_DRAFT, VERSION_STATUS_PUBLISHED, VERSION_STATUS_RETIRED}
)

#: Rule effects.
EFFECT_ALLOW = "allow"
EFFECT_DENY = "deny"
EFFECT_REVIEW = "review"
EFFECTS = frozenset({EFFECT_ALLOW, EFFECT_DENY, EFFECT_REVIEW})

#: Exception effects (waive a denial).
EXCEPTION_EFFECT_ALLOW = "allow"
EXCEPTION_EFFECT_REVIEW = "review"
EXCEPTION_EFFECTS = frozenset({EXCEPTION_EFFECT_ALLOW, EXCEPTION_EFFECT_REVIEW})

#: Evaluation decisions.
DECISION_ALLOW = "allow"
DECISION_DENY = "deny"
DECISION_REVIEW = "review"
DECISION_NOT_APPLICABLE = "not_applicable"
DECISIONS = frozenset({DECISION_ALLOW, DECISION_DENY, DECISION_REVIEW, DECISION_NOT_APPLICABLE})


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class PolicyDefinition(Base):
    """A named policy with a stable business key and a scope."""

    __tablename__ = "policy_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    #: Stable business key — e.g. ``attendance.min_attendance``.
    policy_id: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    scope: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    #: Optional entity the policy applies to (e.g. ``student``, ``payment``).
    scope_ref: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=POLICY_STATUS_DRAFT, index=True
    )
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (UniqueConstraint("campus_id", "policy_id", name="uq_policy_definition_key"),)

    def __repr__(self) -> str:
        return f"<PolicyDefinition id={self.id} key={self.policy_id!r} scope={self.scope}>"


class PolicyVersion(Base):
    """An immutable snapshot of a policy: rules + exceptions + effective
    dates + approval metadata."""

    __tablename__ = "policy_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    policy_def_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("policy_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Sequential per policy (1, 2, 3, ...).
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    #: List of {id, description, condition, effect, reason} dicts.
    rules: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    #: List of {id, description, condition, effect, reason} dicts.
    exceptions: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    #: Optional applicability condition — when present and false the
    #: evaluation is ``not_applicable`` (rules skipped).
    applicability: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=VERSION_STATUS_DRAFT, index=True
    )
    #: Fast-path flag; effective dates are authoritative.
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    effective_from: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    effective_until: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Approval metadata — publishing IS the approval action.
    approved_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approval_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    published_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        UniqueConstraint("policy_def_id", "version", name="uq_policy_version_number"),
    )

    def __repr__(self) -> str:
        return f"<PolicyVersion id={self.id} policy={self.policy_def_id} v{self.version}>"


class PolicyEvaluation(Base):
    """A persisted evaluation record — the traceability backbone.

    Every evaluation is traceable to: policy version + input data + result.
    """

    __tablename__ = "policy_evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    #: Denormalized for query convenience.
    policy_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    policy_def_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("policy_definitions.id", ondelete="CASCADE"),
        nullable=True,
    )
    policy_version_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("policy_versions.id", ondelete="CASCADE"),
        nullable=True,
    )
    version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subject_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    subject_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    #: allow | deny | review | not_applicable
    decision: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    #: Per-rule outcomes + applied exceptions.
    result: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    #: The input data the evaluation ran against.
    input_snapshot: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    evaluated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evaluated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, index=True
    )

    __table_args__ = (
        Index("ix_policy_evaluations_policy_version", "policy_id", "version"),
        Index(
            "ix_policy_evaluations_subject",
            "subject_type",
            "subject_id",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PolicyEvaluation id={self.id} policy={self.policy_id!r} "
            f"v{self.version} decision={self.decision}>"
        )
