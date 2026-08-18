"""Enterprise evidence foundation — ORM models.

Application-level, tenant-scoped evidence storage that lets a future
auditor determine, for any claim:

- **what was claimed**          — ``evidence_items`` (statement + item type)
- **what data supported it**    — ``evidence_snapshots`` (captured data) and
  ``evidence_references`` (pointers to external data — referenced, never copied)
- **what calculation was performed** — snapshot ``calculation`` metadata
  (method, inputs, output, policy version)
- **what policy version applied** — item ``policy_id``/``policy_version``
- **who approved it**           — ``evidence_approvals``
- **when it was generated**     — timestamps on every row
- **whether it has changed**    — ``evidence_hashes``: a per-package hash
  chain over snapshots + items; ``verify_package`` recomputes digests and
  replays the chain to detect any tampering

Design notes
------------
- ``evidence_packages`` groups a claim with its items, snapshots,
  references, approvals and hashes; ``package_key`` is a stable business
  key (unique per campus), so re-creating the same package is idempotent.
- Snapshots are immutable by contract (the service refuses updates); the
  hash chain makes any change detectable even if a write slipped through.
- This is runtime evidence storage; the build-time ``scripts/evidence/``
  tool (JUnit manifests + artifact checksums) remains separate — the
  platform layer reuses the same SHA-256 / canonical-JSON conventions.

Tenancy: every table carries ``campus_id`` (direct tenant scoping — the
multi-tenant registry classifies them ``TENANT_DIRECT`` automatically).
"""

from __future__ import annotations

import datetime

from sqlalchemy import (
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

#: Package lifecycle.
PACKAGE_STATUS_DRAFT = "draft"
PACKAGE_STATUS_OPEN = "open"
PACKAGE_STATUS_APPROVED = "approved"
PACKAGE_STATUS_ARCHIVED = "archived"
PACKAGE_STATUSES = frozenset(
    {PACKAGE_STATUS_DRAFT, PACKAGE_STATUS_OPEN, PACKAGE_STATUS_APPROVED, PACKAGE_STATUS_ARCHIVED}
)

#: Item kinds (what kind of claim/statement this is).
ITEM_TYPE_CLAIM = "claim"
ITEM_TYPE_ASSERTION = "assertion"
ITEM_TYPE_OBSERVATION = "observation"
ITEM_TYPE_CALCULATION_RESULT = "calculation_result"
ITEM_TYPES = frozenset(
    {
        ITEM_TYPE_CLAIM,
        ITEM_TYPE_ASSERTION,
        ITEM_TYPE_OBSERVATION,
        ITEM_TYPE_CALCULATION_RESULT,
    }
)

#: Reference kinds (external supporting data).
REF_TYPE_AUDIT = "audit"
REF_TYPE_FILE = "file"
REF_TYPE_MIGRATION_RUN = "migration_run"
REF_TYPE_REPORT = "report"
REF_TYPE_SOURCE_RECORD = "source_record"
REF_TYPE_POLICY_EVALUATION = "policy_evaluation"
REF_TYPES = frozenset(
    {
        REF_TYPE_AUDIT,
        REF_TYPE_FILE,
        REF_TYPE_MIGRATION_RUN,
        REF_TYPE_REPORT,
        REF_TYPE_SOURCE_RECORD,
        REF_TYPE_POLICY_EVALUATION,
    }
)

#: Snapshot kinds (what the snapshot captured).
SNAPSHOT_INPUT_DATA = "input_data"
SNAPSHOT_CALCULATION = "calculation"
SNAPSHOT_RESULT = "result"
SNAPSHOT_KINDS = frozenset({SNAPSHOT_INPUT_DATA, SNAPSHOT_CALCULATION, SNAPSHOT_RESULT})

#: Hash targets (what a chain entry covers).
HASH_TARGET_SNAPSHOT = "snapshot"
HASH_TARGET_ITEM = "item"
HASH_TARGETS = frozenset({HASH_TARGET_SNAPSHOT, HASH_TARGET_ITEM})

#: Approval decisions.
APPROVAL_APPROVE = "approve"
APPROVAL_REJECT = "reject"
APPROVAL_WITHDRAW = "withdraw"
APPROVAL_DECISIONS = frozenset({APPROVAL_APPROVE, APPROVAL_REJECT, APPROVAL_WITHDRAW})

#: Hash algorithm (only SHA-256 — deterministic, collision-resistant).
HASH_ALGO_SHA256 = "sha256"


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class EvidencePackage(Base):
    """A claim bundled with its supporting evidence."""

    __tablename__ = "evidence_packages"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    #: Stable business key — e.g. ``reconciliation.financial-integrity-2026-08``.
    package_key: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    #: The claim this package substantiates.
    claim: Mapped[str] = mapped_column(String(2000), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PACKAGE_STATUS_DRAFT, index=True
    )
    #: Free-form metadata (e.g. related entity, tags).
    metadata_json: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
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

    __table_args__ = (UniqueConstraint("campus_id", "package_key", name="uq_evidence_package_key"),)

    def __repr__(self) -> str:
        return f"<EvidencePackage id={self.id} key={self.package_key!r} status={self.status}>"


class EvidenceItem(Base):
    """One claim/assertion within a package — *what was claimed*."""

    __tablename__ = "evidence_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    package_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("evidence_packages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default=ITEM_TYPE_CLAIM, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    #: The statement itself (the claim being made).
    statement: Mapped[str] = mapped_column(String(4000), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    #: Which policy version applied (denormalized for audit queries).
    policy_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    policy_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    def __repr__(self) -> str:
        return f"<EvidenceItem id={self.id} type={self.item_type} title={self.title!r}>"


class EvidenceReference(Base):
    """A pointer to external supporting data — referenced, never copied."""

    __tablename__ = "evidence_references"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    package_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("evidence_packages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("evidence_items.id", ondelete="CASCADE"),
        nullable=True,
    )
    ref_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default=REF_TYPE_AUDIT, index=True
    )
    reference: Mapped[str] = mapped_column(String(512), nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        Index("ix_evidence_references_pkg_type_ref", "package_id", "ref_type", "reference"),
    )

    def __repr__(self) -> str:
        return (
            f"<EvidenceReference id={self.id} package={self.package_id} "
            f"type={self.ref_type} ref={self.reference!r}>"
        )


class EvidenceSnapshot(Base):
    """An immutable capture of supporting data / a calculation.

    Answers "what data supported it" and "what calculation was performed".
    Content is stored as canonical JSON; ``content_hash`` is the SHA-256 of
    the canonical serialization.  Immutable by contract — the service
    refuses updates, and the hash chain makes tampering detectable.
    """

    __tablename__ = "evidence_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    package_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("evidence_packages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("evidence_items.id", ondelete="CASCADE"),
        nullable=True,
    )
    kind: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SNAPSHOT_RESULT, index=True
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    #: The captured data (input data, result, etc.).
    content: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    #: Calculation metadata: {method, inputs, output, policy_id, policy_version}.
    calculation: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    #: SHA-256 of the canonical serialization of ``content`` + ``calculation``.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    def __repr__(self) -> str:
        return f"<EvidenceSnapshot id={self.id} package={self.package_id} kind={self.kind}>"


class EvidenceHash(Base):
    """One link in a package's hash chain.

    Each substantive addition (snapshot or item) appends a chain entry:
    ``hash_value = chain_hash(prev_hash, target_type, target_id, digest)``.
    Verifying replays the chain in order — any change to a covered record
    breaks the link, answering "has this evidence changed?".
    """

    __tablename__ = "evidence_hashes"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    package_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("evidence_packages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    #: The digest this entry covers (snapshot content hash / item statement hash).
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Previous chain value ("" for the first entry in a package chain).
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    #: ``chain_hash(prev_hash, target_type, target_id, digest)``.
    hash_value: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    #: 0-based position within the package chain.
    chain_index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    def __repr__(self) -> str:
        return (
            f"<EvidenceHash id={self.id} package={self.package_id} "
            f"#{self.chain_index} {self.target_type}:{self.target_id}>"
        )


class EvidenceApproval(Base):
    """Approval trail — *who approved it* (and when)."""

    __tablename__ = "evidence_approvals"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    package_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("evidence_packages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    approver_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    def __repr__(self) -> str:
        return f"<EvidenceApproval id={self.id} package={self.package_id} {self.decision}>"
