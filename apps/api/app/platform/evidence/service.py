"""Enterprise evidence foundation — application service.

Owns the evidence lifecycle:

- ``create_package``  — create a claim package (idempotent on ``package_key``)
- ``add_item``        — record a claim/assertion; appends a hash-chain entry
- ``add_reference``   — point at external supporting data (never copied)
- ``add_snapshot``    — capture supporting data / a calculation; computes
  the content SHA-256 and appends a hash-chain entry (immutable by contract)
- ``approve``         — record approval and move the package to approved
- ``verify_package``  — recompute digests and replay the hash chain to
  detect any tampering (*has this evidence changed?*)

Every operation is tenant-scoped through the repository and audited through
the existing audit domain.  The hash chain covers snapshots and items; a
change to any covered record breaks its chain link, so the verification
report is deterministic and trustworthy.
"""

from __future__ import annotations

import datetime
import logging
from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationError
from app.domains.audit.actors import ActorType, AuditActor
from app.domains.audit.service import AuditService
from app.multi_tenant.models import TenantContext
from app.platform.evidence.integrity import (
    chain_hash,
    content_digest,
)
from app.platform.evidence.models import (
    APPROVAL_APPROVE,
    APPROVAL_DECISIONS,
    HASH_TARGET_ITEM,
    HASH_TARGET_SNAPSHOT,
    ITEM_TYPES,
    PACKAGE_STATUS_APPROVED,
    PACKAGE_STATUS_DRAFT,
    PACKAGE_STATUS_OPEN,
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
from app.platform.evidence.schemas import (
    EvidenceApprovalCreate,
    EvidenceItemCreate,
    EvidencePackageCreate,
    EvidenceReferenceCreate,
    EvidenceSnapshotCreate,
    VerificationEntry,
    VerificationReport,
)

logger = logging.getLogger(__name__)


class EvidenceService:
    """Evidence operations (one tenant per instance)."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: Optional[TenantContext] = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.repo = EvidenceRepository(session, tenant)
        self.audit = AuditService(session, tenant)

    # ------------------------------------------------------------------
    # Packages
    # ------------------------------------------------------------------

    async def create_package(
        self, data: EvidencePackageCreate, actor: AuditActor | None = None
    ) -> EvidencePackage:
        """Create a claim package; idempotent on ``package_key`` (per
        campus) — re-creating the same package returns the existing one."""
        existing = await self.repo.find_by_key(data.package_key)
        if existing is not None:
            return existing
        package = EvidencePackage(
            campus_id=self.repo._effective_campus_id(),
            package_key=data.package_key,
            title=data.title,
            claim=data.claim,
            status=PACKAGE_STATUS_DRAFT,
            metadata_json=data.metadata_json,
            created_by=data.created_by or _actor_id(actor),
        )
        package = await self.repo.create_package(package)
        await self.audit.record(
            action="CREATE",
            resource_type="evidence_package",
            resource_id=str(package.id),
            actor=actor,
            details={
                "package_key": data.package_key,
                "title": data.title,
                "claim": data.claim,
            },
        )
        return package

    async def open_package(
        self, package_id: int, actor: AuditActor | None = None
    ) -> EvidencePackage:
        """Move a draft package to open (evidence can now be added)."""
        package = await self.repo.get_package_or_404(package_id)
        if package.status != PACKAGE_STATUS_DRAFT:
            raise ConflictError("only a draft package can be opened")
        package.status = PACKAGE_STATUS_OPEN
        await self.session.flush()
        await self.audit.record(
            action="OPEN",
            resource_type="evidence_package",
            resource_id=str(package.id),
            actor=actor,
        )
        return package

    # ------------------------------------------------------------------
    # Items
    # ------------------------------------------------------------------

    async def add_item(
        self,
        package_id: int,
        data: EvidenceItemCreate,
        actor: AuditActor | None = None,
    ) -> EvidenceItem:
        """Record a claim/assertion (*what was claimed*).  Appends a
        hash-chain entry so the statement is tamper-evident."""
        if data.item_type not in ITEM_TYPES:
            raise ValidationError(f"item_type must be one of {sorted(ITEM_TYPES)}")
        package = await self.repo.get_package_or_404(package_id)
        if package.status == PACKAGE_STATUS_APPROVED:
            raise ConflictError("cannot add items to an approved package")
        item = EvidenceItem(
            campus_id=package.campus_id,
            package_id=package.id,
            item_type=data.item_type,
            title=data.title,
            statement=data.statement,
            entity_type=data.entity_type,
            entity_id=data.entity_id,
            policy_id=data.policy_id,
            policy_version=data.policy_version,
            created_by=data.created_by or _actor_id(actor),
        )
        item = await self.repo.create_item(item)
        digest = content_digest(item.statement, item.policy_id, item.policy_version)
        await self._append_hash(package, HASH_TARGET_ITEM, item.id, digest)
        await self.audit.record(
            action="CREATE",
            resource_type="evidence_item",
            resource_id=str(item.id),
            actor=actor,
            details={
                "package_id": package.id,
                "item_type": data.item_type,
                "title": data.title,
                "policy_id": data.policy_id,
                "policy_version": data.policy_version,
            },
        )
        return item

    # ------------------------------------------------------------------
    # References
    # ------------------------------------------------------------------

    async def add_reference(
        self,
        package_id: int,
        data: EvidenceReferenceCreate,
        actor: AuditActor | None = None,
    ) -> EvidenceReference:
        """Point at external supporting data (referenced, never copied)."""
        if data.ref_type not in REF_TYPES:
            raise ValidationError(f"ref_type must be one of {sorted(REF_TYPES)}")
        package = await self.repo.get_package_or_404(package_id)
        reference = EvidenceReference(
            campus_id=package.campus_id,
            package_id=package.id,
            item_id=data.item_id,
            ref_type=data.ref_type,
            reference=data.reference,
            checksum=data.checksum,
            note=data.note,
        )
        reference = await self.repo.create_reference(reference)
        await self.audit.record(
            action="CREATE",
            resource_type="evidence_reference",
            resource_id=str(reference.id),
            actor=actor,
            details={
                "package_id": package.id,
                "ref_type": data.ref_type,
                "reference": data.reference,
            },
        )
        return reference

    # ------------------------------------------------------------------
    # Snapshots (immutable captures)
    # ------------------------------------------------------------------

    async def add_snapshot(
        self,
        package_id: int,
        data: EvidenceSnapshotCreate,
        actor: AuditActor | None = None,
    ) -> EvidenceSnapshot:
        """Capture supporting data / a calculation.

        ``content_hash`` is the SHA-256 of the canonical serialization of
        ``content`` + ``calculation``; a hash-chain entry is appended.  The
        record is immutable by contract — the service offers no update path.
        """
        if data.kind not in SNAPSHOT_KINDS:
            raise ValidationError(f"kind must be one of {sorted(SNAPSHOT_KINDS)}")
        package = await self.repo.get_package_or_404(package_id)
        if package.status == PACKAGE_STATUS_APPROVED:
            raise ConflictError("cannot add snapshots to an approved package")
        snapshot = EvidenceSnapshot(
            campus_id=package.campus_id,
            package_id=package.id,
            item_id=data.item_id,
            kind=data.kind,
            label=data.label,
            content=data.content,
            calculation=data.calculation,
            content_hash=content_digest(data.content, data.calculation),
            created_by=data.created_by or _actor_id(actor),
        )
        snapshot = await self.repo.create_snapshot(snapshot)
        await self._append_hash(package, HASH_TARGET_SNAPSHOT, snapshot.id, snapshot.content_hash)
        await self.audit.record(
            action="CREATE",
            resource_type="evidence_snapshot",
            resource_id=str(snapshot.id),
            actor=actor,
            details={
                "package_id": package.id,
                "kind": data.kind,
                "label": data.label,
                "content_hash": snapshot.content_hash,
            },
        )
        return snapshot

    # ------------------------------------------------------------------
    # Approval
    # ------------------------------------------------------------------

    async def approve(
        self,
        package_id: int,
        data: EvidenceApprovalCreate,
        actor: AuditActor | None = None,
    ) -> EvidencePackage:
        """Approve / reject / withdraw a package (*who approved it*)."""
        if data.decision not in APPROVAL_DECISIONS:
            raise ValidationError(f"decision must be one of {sorted(APPROVAL_DECISIONS)}")
        package = await self.repo.get_package_or_404(package_id)
        approval = EvidenceApproval(
            campus_id=package.campus_id,
            package_id=package.id,
            decision=data.decision,
            approver_id=data.approver_id or _actor_id(actor),
            comment=data.comment,
        )
        await self.repo.create_approval(approval)
        if data.decision == APPROVAL_APPROVE:
            package.status = PACKAGE_STATUS_APPROVED
            package.approved_by = data.approver_id or _actor_id(actor)
            package.approved_at = _now()
        await self.session.flush()
        await self.audit.record(
            action="APPROVAL",
            resource_type="evidence_package",
            resource_id=str(package.id),
            actor=actor,
            details={"decision": data.decision, "comment": data.comment},
        )
        return package

    # ------------------------------------------------------------------
    # Verification (tamper detection)
    # ------------------------------------------------------------------

    async def verify_package(self, package_id: int) -> VerificationReport:
        """Verify the package's integrity.

        For every snapshot: recompute the content digest and compare with
        the stored hash.  For every item: recompute the statement digest
        and compare with the digest recorded in its chain entry.  Then
        replay the chain in order, checking each link.  Any mismatch means
        the evidence changed since capture.
        """
        package = await self.repo.get_package_or_404(package_id)
        entries: list[VerificationEntry] = []

        snapshots = await self.repo.list_snapshots(package.id)
        snapshot_digests: dict[int, str] = {}
        for snap in snapshots:
            recomputed = content_digest(snap.content, snap.calculation)
            ok = recomputed == snap.content_hash
            snapshot_digests[snap.id] = snap.content_hash
            entries.append(
                VerificationEntry(
                    target_type=HASH_TARGET_SNAPSHOT,
                    target_id=snap.id,
                    label=snap.label,
                    ok=ok,
                    detail=(
                        "hash matches"
                        if ok
                        else (
                            "content hash changed: stored "
                            f"{snap.content_hash}, recomputed {recomputed}"
                        )
                    ),
                )
            )

        items = await self.repo.list_items(package.id)
        item_digests: dict[int, str] = {}
        for item in items:
            digest = content_digest(item.statement, item.policy_id, item.policy_version)
            item_digests[item.id] = digest
            entries.append(
                VerificationEntry(
                    target_type=HASH_TARGET_ITEM,
                    target_id=item.id,
                    label=item.title,
                    ok=True,
                    detail="digest recorded",
                )
            )

        # Replay the chain.
        chain = await self.repo.list_hashes(package.id)
        chain_ok = True
        prev = ""
        chain_digests: dict[tuple[str, int], str] = {}
        for entry in chain:
            if entry.prev_hash != prev:
                chain_ok = False
                entries.append(
                    VerificationEntry(
                        target_type="chain",
                        target_id=entry.chain_index,
                        label=f"link {entry.chain_index}",
                        ok=False,
                        detail=(
                            f"prev_hash mismatch: stored {entry.prev_hash[:12]}..., "
                            f"expected {prev[:12]}..."
                        ),
                    )
                )
            expected = chain_hash(prev, entry.target_type, entry.target_id, entry.digest)
            if expected != entry.hash_value:
                chain_ok = False
                entries.append(
                    VerificationEntry(
                        target_type="chain",
                        target_id=entry.chain_index,
                        label=f"link {entry.chain_index}",
                        ok=False,
                        detail=(
                            f"hash mismatch: stored {entry.hash_value[:12]}..., "
                            f"recomputed {expected[:12]}..."
                        ),
                    )
                )
            chain_digests[(entry.target_type, entry.target_id)] = entry.digest
            prev = entry.hash_value

        # Cross-check: chain digests must match the current record digests.
        for snap_id, digest in snapshot_digests.items():
            recorded = chain_digests.get((HASH_TARGET_SNAPSHOT, snap_id))
            if recorded != digest:
                chain_ok = False
                entries.append(
                    VerificationEntry(
                        target_type=HASH_TARGET_SNAPSHOT,
                        target_id=snap_id,
                        label=f"snapshot {snap_id}",
                        ok=False,
                        detail=(
                            f"chain digest {recorded[:12] if recorded else None} "
                            f"!= record digest {digest[:12]}"
                        ),
                    )
                )
        for item_id, digest in item_digests.items():
            recorded = chain_digests.get((HASH_TARGET_ITEM, item_id))
            if recorded != digest:
                chain_ok = False
                entries.append(
                    VerificationEntry(
                        target_type=HASH_TARGET_ITEM,
                        target_id=item_id,
                        label=f"item {item_id}",
                        ok=False,
                        detail=(
                            f"chain digest {recorded[:12] if recorded else None} "
                            f"!= record digest {digest[:12]}"
                        ),
                    )
                )

        # The overall verdict covers both layers: the chain replay AND every
        # record-level check (a snapshot whose content no longer matches its
        # stored hash has changed, even though the chain itself is intact).
        all_ok = all(e.ok for e in entries)
        return VerificationReport(
            package_id=package.id,
            package_key=package.package_key,
            chain_ok=chain_ok and all_ok,
            chain_length=len(chain),
            entries=entries,
            verified_at=_now(),
        )

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def get_package(self, package_id: int) -> EvidencePackage:
        return await self.repo.get_package_or_404(package_id)

    async def list_packages(
        self,
        *,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[EvidencePackage], int]:
        return await self.repo.list_packages(status=status, skip=skip, limit=limit)

    async def items(self, package_id: int) -> Sequence[EvidenceItem]:
        return await self.repo.list_items(package_id)

    async def references(self, package_id: int) -> Sequence[EvidenceReference]:
        return await self.repo.list_references(package_id)

    async def snapshots(self, package_id: int) -> Sequence[EvidenceSnapshot]:
        return await self.repo.list_snapshots(package_id)

    async def approvals(self, package_id: int) -> Sequence[EvidenceApproval]:
        return await self.repo.list_approvals(package_id)

    async def hashes(self, package_id: int) -> Sequence[EvidenceHash]:
        return await self.repo.list_hashes(package_id)

    # ------------------------------------------------------------------
    # Hash chain
    # ------------------------------------------------------------------

    async def _append_hash(
        self,
        package: EvidencePackage,
        target_type: str,
        target_id: int,
        digest: str,
    ) -> EvidenceHash:
        last = await self.repo.last_hash(package.id)
        prev = last.hash_value if last is not None else ""
        index = last.chain_index + 1 if last is not None else 0
        return await self.repo.create_hash(
            EvidenceHash(
                campus_id=package.campus_id,
                package_id=package.id,
                target_type=target_type,
                target_id=target_id,
                digest=digest,
                prev_hash=prev,
                hash_value=chain_hash(prev, target_type, target_id, digest),
                chain_index=index,
            )
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _actor_id(actor: AuditActor | None) -> Optional[int]:
    if actor is None or actor.actor_type != ActorType.USER:
        return None
    raw = actor.actor_id
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)
