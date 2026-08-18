"""Enterprise evidence foundation (platform).

Application-level, tenant-scoped evidence storage that lets a future
auditor determine, for any claim:

- **what was claimed**          — ``evidence_items`` (statement + item type)
- **what data supported it**    — ``evidence_snapshots`` (captured data)
  and ``evidence_references`` (pointers — referenced, never copied)
- **what calculation was performed** — snapshot ``calculation`` metadata
- **what policy version applied** — item ``policy_id``/``policy_version``
- **who approved it**           — ``evidence_approvals``
- **when it was generated**     — timestamps on every row
- **whether it has changed**    — ``evidence_hashes``: a per-package hash
  chain; ``verify_package`` recomputes digests and replays the chain

Primitives
----------
- ``evidence_packages``   — a claim bundled with its evidence (stable
  ``package_key``, unique per campus — idempotent re-creation)
- ``evidence_items``      — claims/assertions, each covered by a chain entry
- ``evidence_references`` — pointers to external supporting data
- ``evidence_snapshots``  — immutable captures (content + calculation) with
  a SHA-256 content hash
- ``evidence_hashes``     — the per-package hash chain (tamper detection)
- ``evidence_approvals``  — approval trail

Properties
----------
- **deterministic integrity** — canonical-JSON SHA-256 hashing (same
  conventions as the build-time ``scripts/evidence/`` tool); verification
  is a pure replay of the chain
- **immutable by contract** — snapshots have no update path; tampering is
  detectable, not silently accepted
- **audit trail** — lifecycle operations recorded through the audit domain
- **tenant isolation** — every table carries ``campus_id``; reads go
  through the tenant-scoped repository
"""

from app.platform.evidence.integrity import (
    canonical_bytes,
    chain_hash,
    content_digest,
    sha256_hex,
    verify_chain,
)
from app.platform.evidence.models import (
    APPROVAL_APPROVE,
    APPROVAL_DECISIONS,
    APPROVAL_REJECT,
    APPROVAL_WITHDRAW,
    HASH_TARGET_ITEM,
    HASH_TARGET_SNAPSHOT,
    HASH_TARGETS,
    ITEM_TYPES,
    PACKAGE_STATUSES,
    REF_TYPES,
    SNAPSHOT_KINDS,
    EvidenceApproval,
    EvidenceHash,
    EvidenceItem,
    EvidencePackage,
    EvidenceReference,
    EvidenceSnapshot,
)
from app.platform.evidence.repository import EvidenceRepository
from app.platform.evidence.service import EvidenceService

__all__ = [
    "canonical_bytes",
    "chain_hash",
    "content_digest",
    "sha256_hex",
    "verify_chain",
    "APPROVAL_APPROVE",
    "APPROVAL_DECISIONS",
    "APPROVAL_REJECT",
    "APPROVAL_WITHDRAW",
    "HASH_TARGET_ITEM",
    "HASH_TARGET_SNAPSHOT",
    "HASH_TARGETS",
    "ITEM_TYPES",
    "PACKAGE_STATUSES",
    "REF_TYPES",
    "SNAPSHOT_KINDS",
    "EvidenceApproval",
    "EvidenceHash",
    "EvidenceItem",
    "EvidencePackage",
    "EvidenceReference",
    "EvidenceSnapshot",
    "EvidenceRepository",
    "EvidenceService",
]
