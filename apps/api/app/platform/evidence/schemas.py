"""Enterprise evidence foundation — Pydantic schemas (API contract)."""

from __future__ import annotations

import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.platform.evidence.models import (
    APPROVAL_DECISIONS,
    ITEM_TYPES,
    PACKAGE_STATUSES,
    REF_TYPES,
    SNAPSHOT_KINDS,
)

# ---------------------------------------------------------------------------
# Packages
# ---------------------------------------------------------------------------


class EvidencePackageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_key: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9._-]+$")
    title: str = Field(min_length=1, max_length=255)
    claim: str = Field(min_length=1, max_length=2000)
    metadata_json: Optional[dict[str, Any]] = None
    created_by: Optional[int] = None


class EvidencePackageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    package_key: str
    title: str
    claim: str
    status: str
    metadata_json: Optional[dict[str, Any]] = None
    created_by: Optional[int] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------


class EvidenceItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_type: str = Field(default="claim", max_length=30)
    title: str = Field(min_length=1, max_length=255)
    statement: str = Field(min_length=1, max_length=4000)
    entity_type: Optional[str] = Field(default=None, max_length=80)
    entity_id: Optional[str] = Field(default=None, max_length=200)
    policy_id: Optional[str] = Field(default=None, max_length=200)
    policy_version: Optional[int] = None
    created_by: Optional[int] = None


class EvidenceItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    package_id: int
    item_type: str
    title: str
    statement: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    policy_id: Optional[str] = None
    policy_version: Optional[int] = None
    created_by: Optional[int] = None
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------


class EvidenceReferenceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref_type: str = Field(default="audit", max_length=30)
    reference: str = Field(min_length=1, max_length=512)
    item_id: Optional[int] = None
    checksum: Optional[str] = Field(default=None, max_length=128)
    note: Optional[str] = Field(default=None, max_length=1000)


class EvidenceReferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    package_id: int
    item_id: Optional[int] = None
    ref_type: str
    reference: str
    checksum: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------


class EvidenceSnapshotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(default="result", max_length=20)
    label: str = Field(min_length=1, max_length=255)
    content: Optional[dict[str, Any]] = None
    #: {method, inputs, output, policy_id, policy_version}
    calculation: Optional[dict[str, Any]] = None
    item_id: Optional[int] = None
    created_by: Optional[int] = None


class EvidenceSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    package_id: int
    item_id: Optional[int] = None
    kind: str
    label: str
    content: Optional[dict[str, Any]] = None
    calculation: Optional[dict[str, Any]] = None
    content_hash: str
    created_by: Optional[int] = None
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# Hashes / approvals / verification
# ---------------------------------------------------------------------------


class EvidenceHashRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    package_id: int
    target_type: str
    target_id: int
    digest: str
    prev_hash: str
    hash_value: str
    chain_index: int
    created_at: datetime.datetime


class EvidenceApprovalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str = Field(max_length=20)
    approver_id: Optional[int] = None
    comment: Optional[str] = Field(default=None, max_length=1000)


class EvidenceApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    package_id: int
    decision: str
    approver_id: Optional[int] = None
    comment: Optional[str] = None
    created_at: datetime.datetime


class VerificationEntry(BaseModel):
    """Per-record verification result."""

    target_type: str
    target_id: int
    label: str
    ok: bool
    detail: str


class VerificationReport(BaseModel):
    """The tamper-detection report for one package."""

    package_id: int
    package_key: str
    chain_ok: bool
    chain_length: int
    entries: list[VerificationEntry]
    verified_at: datetime.datetime


__all__ = [
    "EvidencePackageCreate",
    "EvidencePackageRead",
    "EvidenceItemCreate",
    "EvidenceItemRead",
    "EvidenceReferenceCreate",
    "EvidenceReferenceRead",
    "EvidenceSnapshotCreate",
    "EvidenceSnapshotRead",
    "EvidenceHashRead",
    "EvidenceApprovalCreate",
    "EvidenceApprovalRead",
    "VerificationEntry",
    "VerificationReport",
    "PACKAGE_STATUSES",
    "ITEM_TYPES",
    "REF_TYPES",
    "SNAPSHOT_KINDS",
    "APPROVAL_DECISIONS",
]
