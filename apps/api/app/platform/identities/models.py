"""Canonical identity layer — ORM models.

Six tenant-scoped tables implement the canonical identity foundation:

- ``canonical_people``    — one canonical record per real-world person.
  References existing Student/Teacher/Guardian rows (``entity_type`` +
  ``entity_id``) rather than replacing them.
- ``external_identities`` — identifiers from external systems (legacy ERP,
  biometric, RFID, transport, external organizations) linked to a person.
- ``identity_aliases``    — alternate names / identifiers observed for a
  person (nickname, previous name, maiden name, etc.).
- ``identity_matches``    — deterministic match proposals with confidence +
  review state (pending/confirmed/rejected).
- ``identity_merges``     — merge operations: source person folded into a
  target person, with an audit snapshot of what moved.
- ``identity_history``    — append-only audit trail of identity lifecycle
  events (created, linked, matched, reviewed, merged, unlinked).

Tenancy: every table carries ``campus_id`` (direct tenant scoping — the
multi-tenant registry classifies them ``TENANT_DIRECT`` automatically), so
the tenant-scoped repository pins every query to the caller's campus.
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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base
from app.infrastructure.types import JSONType

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Canonical person status.
PERSON_STATUS_ACTIVE = "active"
PERSON_STATUS_MERGED = "merged"  # folded into another canonical person
PERSON_STATUS_ARCHIVED = "archived"

#: External identity status.
IDENTITY_STATUS_ACTIVE = "active"
IDENTITY_STATUS_SUPERSEDED = "superseded"  # replaced by a newer identifier
IDENTITY_STATUS_UNLINKED = "unlinked"

#: Identity match review status.
MATCH_STATUS_PENDING = "pending"
MATCH_STATUS_CONFIRMED = "confirmed"
MATCH_STATUS_REJECTED = "rejected"

#: Identity merge status.
MERGE_STATUS_COMPLETED = "completed"
MERGE_STATUS_ROLLED_BACK = "rolled_back"

#: Canonical person status choices (validation helper).
PERSON_STATUSES = frozenset({PERSON_STATUS_ACTIVE, PERSON_STATUS_MERGED, PERSON_STATUS_ARCHIVED})
IDENTITY_STATUSES = frozenset(
    {IDENTITY_STATUS_ACTIVE, IDENTITY_STATUS_SUPERSEDED, IDENTITY_STATUS_UNLINKED}
)
MATCH_STATUSES = frozenset({MATCH_STATUS_PENDING, MATCH_STATUS_CONFIRMED, MATCH_STATUS_REJECTED})
MERGE_STATUSES = frozenset({MERGE_STATUS_COMPLETED, MERGE_STATUS_ROLLED_BACK})

#: Entity types a canonical person may reference (existing domain entities).
REFERENCED_ENTITY_TYPES = frozenset({"student", "teacher", "guardian", "user"})


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class CanonicalPerson(Base):
    """One canonical record per real-world person (tenant-scoped)."""

    __tablename__ = "canonical_people"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Reference to the primary existing entity this person corresponds to.
    # ``entity_type`` is one of REFERENCED_ENTITY_TYPES; ``entity_id`` is the
    # primary key of that entity.  Reference columns are intentionally not
    # FKs — the referenced rows may live in different domains and the
    # canonical person must survive entity deletion (soft reference).
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, default="user")
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # Deterministic identity attributes (best-known values).
    first_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    last_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    date_of_birth: Mapped[datetime.date | None] = mapped_column(nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PERSON_STATUS_ACTIVE, index=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        Index("ix_canonical_people_campus_entity", "campus_id", "entity_type", "entity_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<CanonicalPerson id={self.id} name={self.first_name} {self.last_name} "
            f"status={self.status}>"
        )


class ExternalIdentity(Base):
    """An identifier for a person from an external system (tenant-scoped)."""

    __tablename__ = "external_identities"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    canonical_person_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("canonical_people.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Source system label — e.g. ``legacy_erp``, ``biometric``, ``rfid``,
    #: ``transport``, ``external_org``, ``sdmas``.
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    #: Identifier within the source system (e.g. ERP admission number,
    #: biometric template id, RFID tag, transport pass number).
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    #: Display name as recorded by the external system (optional).
    external_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    #: Confidence that this identifier refers to the linked person (0..1).
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=IDENTITY_STATUS_ACTIVE, index=True
    )
    verified_at: Mapped[datetime.datetime | None] = mapped_column(
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
            "campus_id", "source_system", "external_id", name="uq_external_identity_source_id"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ExternalIdentity id={self.id} source={self.source_system} "
            f"external_id={self.external_id!r} confidence={self.confidence}>"
        )


class IdentityAlias(Base):
    """Alternate name / identifier observed for a person (tenant-scoped)."""

    __tablename__ = "identity_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    canonical_person_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("canonical_people.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Alias kind — ``name``, ``email``, ``phone``, ``external_ref``, ``other``.
    alias_type: Mapped[str] = mapped_column(String(30), nullable=False, default="name")
    alias_value: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        Index(
            "ix_identity_aliases_person_type_value",
            "canonical_person_id",
            "alias_type",
            "alias_value",
        ),
    )

    def __repr__(self) -> str:
        return f"<IdentityAlias id={self.id} type={self.alias_type} value={self.alias_value!r}>"


class IdentityMatch(Base):
    """A deterministic match proposal between two canonical people.

    Matching is rule-based (never AI).  ``matched_by`` records which rule
    produced the match; ``confidence`` quantifies the rule's strength.
    A match starts ``pending`` and must be confirmed or rejected by a human
    (manual review state) unless the confidence clears the auto-confirm
    threshold configured by the caller.
    """

    __tablename__ = "identity_matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    person_a_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("canonical_people.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_b_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("canonical_people.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: Matching rule id (e.g. ``exact_external_id``, ``exact_email``,
    #: ``name_dob``, ``normalized_name_phone``).
    matched_by: Mapped[str] = mapped_column(String(80), nullable=False)
    #: Rule confidence 0..1 (0.5 exact external id, 0.8 email, 0.95 name+DOB).
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    #: Evidence summary (JSON-safe dict of the attributes that matched).
    evidence: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=MATCH_STATUS_PENDING, index=True
    )
    reviewed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewed_at: Mapped[datetime.datetime | None] = mapped_column(
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
            "person_a_id", "person_b_id", "matched_by", name="uq_identity_match_pair_rule"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<IdentityMatch id={self.id} {self.person_a_id}~{self.person_b_id} "
            f"by={self.matched_by} conf={self.confidence} status={self.status}>"
        )


class IdentityMerge(Base):
    """Record of a merge: source person folded into a target person.

    ``before_snapshot`` / ``after_snapshot`` capture which external
    identities and aliases moved, so the merge is auditable and reversible.
    """

    __tablename__ = "identity_merges"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_person_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("canonical_people.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_person_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("canonical_people.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: Reason for the merge (free text, required for audit).
    reason: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=MERGE_STATUS_COMPLETED, index=True
    )
    performed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    performed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    before_snapshot: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    after_snapshot: Mapped[dict | None] = mapped_column(JSONType, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<IdentityMerge id={self.id} {self.source_person_id}->{self.target_person_id} "
            f"status={self.status}>"
        )


class IdentityHistory(Base):
    """Append-only audit trail of identity lifecycle events."""

    __tablename__ = "identity_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    canonical_person_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("canonical_people.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: Action — ``created``, ``linked``, ``unlinked``, ``matched``,
    #: ``reviewed``, ``merged``, ``rolled_back``, ``updated``.
    action: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<IdentityHistory id={self.id} person={self.canonical_person_id} action={self.action}>"
        )
