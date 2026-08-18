"""Canonical identity layer — Pydantic schemas (API contract)."""

from __future__ import annotations

import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.platform.identities.models import (
    IDENTITY_STATUSES,
    MATCH_STATUSES,
    MERGE_STATUSES,
    PERSON_STATUSES,
    REFERENCED_ENTITY_TYPES,
)

# ---------------------------------------------------------------------------
# CanonicalPerson
# ---------------------------------------------------------------------------


class PersonCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: str = Field(default="user", pattern=r"^(student|teacher|guardian|user)$")
    entity_id: Optional[int] = None
    first_name: str = Field(default="", max_length=100)
    last_name: str = Field(default="", max_length=100)
    date_of_birth: Optional[datetime.date] = None
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)


class PersonUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: Optional[str] = Field(default=None, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    date_of_birth: Optional[datetime.date] = None
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    status: Optional[str] = Field(default=None, pattern=r"^(active|merged|archived)$")


class PersonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    entity_type: str
    entity_id: Optional[int] = None
    first_name: str
    last_name: str
    date_of_birth: Optional[datetime.date] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# ExternalIdentity
# ---------------------------------------------------------------------------


class ExternalIdentityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_person_id: int
    source_system: str = Field(min_length=1, max_length=50)
    external_id: str = Field(min_length=1, max_length=128)
    external_name: Optional[str] = Field(default=None, max_length=255)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ExternalIdentityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    canonical_person_id: int
    source_system: str
    external_id: str
    external_name: Optional[str] = None
    confidence: float
    status: str
    verified_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# IdentityAlias
# ---------------------------------------------------------------------------


class IdentityAliasCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_person_id: int
    alias_type: str = Field(default="name", max_length=30)
    alias_value: str = Field(min_length=1, max_length=255)


class IdentityAliasRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    canonical_person_id: int
    alias_type: str
    alias_value: str
    is_active: bool
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# IdentityMatch
# ---------------------------------------------------------------------------


class MatchReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: confirm | reject
    decision: str = Field(pattern=r"^(confirm|reject)$")
    reviewer_id: Optional[int] = None


class IdentityMatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    person_a_id: int
    person_b_id: int
    matched_by: str
    confidence: float
    evidence: Optional[dict[str, Any]] = None
    status: str
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# IdentityMerge
# ---------------------------------------------------------------------------


class MergeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_person_id: int
    target_person_id: int
    reason: str = Field(min_length=1, max_length=500)
    actor_id: Optional[int] = None


class IdentityMergeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    source_person_id: int
    target_person_id: int
    reason: str
    status: str
    performed_by: Optional[int] = None
    performed_at: datetime.datetime
    before_snapshot: Optional[dict[str, Any]] = None
    after_snapshot: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# IdentityHistory
# ---------------------------------------------------------------------------


class IdentityHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    canonical_person_id: int
    action: str
    actor_id: Optional[int] = None
    details: Optional[dict[str, Any]] = None
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


class PersonMatchInput(BaseModel):
    """Attributes of one candidate person for deterministic matching."""

    model_config = ConfigDict(extra="forbid")

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[datetime.date] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    source_system: Optional[str] = None
    external_id: Optional[str] = None


class MatchCandidateRead(BaseModel):
    """A canonical person plus the deterministic proposal against a probe."""

    person: PersonRead
    matched_by: str
    confidence: float
    evidence: Optional[dict[str, Any]] = None
    status: str  # pending | confirmed


# ---------------------------------------------------------------------------
# Status constants re-exported for the API layer
# ---------------------------------------------------------------------------

__all__ = [
    "PERSON_STATUSES",
    "IDENTITY_STATUSES",
    "MATCH_STATUSES",
    "MERGE_STATUSES",
    "REFERENCED_ENTITY_TYPES",
    "PersonCreate",
    "PersonUpdate",
    "PersonRead",
    "ExternalIdentityCreate",
    "ExternalIdentityRead",
    "IdentityAliasCreate",
    "IdentityAliasRead",
    "MatchReview",
    "IdentityMatchRead",
    "MergeRequest",
    "IdentityMergeRead",
    "IdentityHistoryRead",
    "PersonMatchInput",
    "MatchCandidateRead",
]
