"""Enterprise evidence foundation tests (TASK 12).

Covers:

- integrity core: canonical serialization determinism, content digests,
  hash-chain links (pure functions)
- package lifecycle: idempotent creation, open, add item/reference/snapshot
- hash chain: entries appended in order with prev-linking
- tamper detection: modifying a snapshot's content breaks verification
- immutability: no snapshot update path; approved packages reject additions
- approval: status + metadata recorded, decision validation
- policy version capture on items (audit question: which policy applied)
- tenant isolation (campus A can never see / mutate campus B evidence)
"""

from __future__ import annotations

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.audit.actors import ActorType, AuditActor
from app.multi_tenant.models import TenantContext
from app.platform.evidence.integrity import (
    chain_hash,
    content_digest,
    sha256_hex,
    verify_chain,
)
from app.platform.evidence.models import (
    PACKAGE_STATUS_APPROVED,
    PACKAGE_STATUS_OPEN,
    EvidenceHash,
    EvidenceItem,
    EvidencePackage,
    EvidenceSnapshot,
)
from app.platform.evidence.schemas import (
    EvidenceApprovalCreate,
    EvidenceItemCreate,
    EvidencePackageCreate,
    EvidenceReferenceCreate,
    EvidenceSnapshotCreate,
)
from app.platform.evidence.service import EvidenceService


@pytest.fixture
def tenant_a() -> TenantContext:
    return TenantContext(campus_id=1, institution_id=1, user_id=99)


@pytest.fixture
def tenant_b() -> TenantContext:
    return TenantContext(campus_id=2, institution_id=1, user_id=98)


def _actor(user_id: int = 99) -> AuditActor:
    return AuditActor(actor_type=ActorType.USER, actor_id=str(user_id))


def _package_create(**overrides) -> EvidencePackageCreate:
    base = {
        "package_key": "reconciliation.financial-integrity-2026-08",
        "title": "Financial integrity evidence package",
        "claim": "Ledger balances reconcile to source payments within tolerance.",
    }
    base.update(overrides)
    return EvidencePackageCreate(**base)


async def _open_package_with_content(
    db_session: AsyncSession, tenant: TenantContext
) -> tuple[EvidenceService, EvidencePackage]:
    svc = EvidenceService(db_session, tenant)
    package = await svc.create_package(_package_create(), actor=_actor())
    package = await svc.open_package(package.id, actor=_actor())
    await svc.add_item(
        package.id,
        EvidenceItemCreate(
            item_type="assertion",
            title="Payments reconcile",
            statement="All 4 source payments match target invoices within 0 tolerance.",
            entity_type="reconciliation_run",
            entity_id="1",
            policy_id="fees.payment_reconciliation",
            policy_version=2,
        ),
        actor=_actor(),
    )
    await svc.add_snapshot(
        package.id,
        EvidenceSnapshotCreate(
            kind="input_data",
            label="Source payments Aug 2026",
            content={
                "payments": [
                    {"legacy_id": "P-001", "amount": 45000},
                    {"legacy_id": "P-002", "amount": 12000},
                ]
            },
        ),
        actor=_actor(),
    )
    await svc.add_snapshot(
        package.id,
        EvidenceSnapshotCreate(
            kind="calculation",
            label="Reconciliation summary",
            content={"matched": 2, "exceptions": 0},
            calculation={
                "method": "reconciliation_engine.execute",
                "policy_id": "fees.payment_reconciliation",
                "policy_version": 2,
            },
        ),
        actor=_actor(),
    )
    await svc.add_reference(
        package.id,
        EvidenceReferenceCreate(
            ref_type="audit",
            reference="audit:reconciliation_run:1",
            checksum="sha256:abc123",
            note="Audit trail for the run",
        ),
        actor=_actor(),
    )
    return svc, package


# ---------------------------------------------------------------------------
# Integrity core (pure)
# ---------------------------------------------------------------------------


class TestIntegrityCore:
    def test_canonical_serialization_deterministic(self) -> None:
        a = {"b": 1, "a": {"x": 2}, "list": [3, 1, 2]}
        b = {"a": {"x": 2}, "list": [3, 1, 2], "b": 1}
        assert content_digest(a) == content_digest(b)

    def test_different_content_different_digest(self) -> None:
        assert content_digest({"amount": 100}) != content_digest({"amount": 101})

    def test_sha256_hex_format(self) -> None:
        digest = sha256_hex(b"sdmas-evidence")
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_content_digest_over_multiple_parts(self) -> None:
        assert content_digest("a", 1) == content_digest("a", 1)
        assert content_digest("a", 1) != content_digest("a", 2)

    def test_chain_hash_links_and_verification(self) -> None:
        d1 = content_digest({"x": 1})
        d2 = content_digest({"x": 2})
        h1 = chain_hash("", "snapshot", 1, d1)
        h2 = chain_hash(h1, "item", 2, d2)
        assert verify_chain(
            prev_hash="", target_type="snapshot", target_id=1, digest=d1, expected=h1
        )
        assert verify_chain(prev_hash=h1, target_type="item", target_id=2, digest=d2, expected=h2)
        # Wrong digest or wrong prev breaks the link.
        assert not verify_chain(
            prev_hash="", target_type="snapshot", target_id=1, digest=d2, expected=h1
        )
        assert not verify_chain(
            prev_hash=h1, target_type="item", target_id=2, digest=d2, expected=h1
        )


# ---------------------------------------------------------------------------
# Package lifecycle
# ---------------------------------------------------------------------------


class TestPackageLifecycle:
    async def test_create_idempotent(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = EvidenceService(db_session, tenant_a)
        package = await svc.create_package(_package_create(), actor=_actor())
        assert package.campus_id == 1
        assert package.status == "draft"

        again = await svc.create_package(_package_create(), actor=_actor())
        assert again.id == package.id
        packages, total = await svc.list_packages()
        assert total == 1

    async def test_open_then_add_content(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, package = await _open_package_with_content(db_session, tenant_a)
        assert package.status == PACKAGE_STATUS_OPEN

        items = await svc.items(package.id)
        assert len(items) == 1
        assert items[0].policy_id == "fees.payment_reconciliation"
        assert items[0].policy_version == 2

        snapshots = await svc.snapshots(package.id)
        assert len(snapshots) == 2
        # Content hash computed and stored.
        assert all(len(s.content_hash) == 64 for s in snapshots)
        assert snapshots[1].calculation["method"] == "reconciliation_engine.execute"

        references = await svc.references(package.id)
        assert len(references) == 1
        assert references[0].ref_type == "audit"

    async def test_item_type_validation(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = EvidenceService(db_session, tenant_a)
        package = await svc.create_package(_package_create(), actor=_actor())
        await svc.open_package(package.id, actor=_actor())
        with pytest.raises(ValidationError):
            await svc.add_item(
                package.id,
                EvidenceItemCreate(item_type="gossip", title="x", statement="y"),
                actor=_actor(),
            )

    async def test_open_only_from_draft(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = EvidenceService(db_session, tenant_a)
        package = await svc.create_package(_package_create(), actor=_actor())
        await svc.open_package(package.id, actor=_actor())
        with pytest.raises(ConflictError):
            await svc.open_package(package.id, actor=_actor())


# ---------------------------------------------------------------------------
# Hash chain + tamper detection
# ---------------------------------------------------------------------------


class TestHashChain:
    async def test_chain_entries_appended_in_order(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, package = await _open_package_with_content(db_session, tenant_a)
        hashes = await svc.hashes(package.id)
        # 1 item + 2 snapshots = 3 chain entries.
        assert len(hashes) == 3
        assert [h.chain_index for h in hashes] == [0, 1, 2]
        # First link has empty prev; each subsequent link chains to the previous.
        assert hashes[0].prev_hash == ""
        assert hashes[1].prev_hash == hashes[0].hash_value
        assert hashes[2].prev_hash == hashes[1].hash_value
        # Every link verifies against its own fields.
        for h in hashes:
            assert verify_chain(
                prev_hash=h.prev_hash,
                target_type=h.target_type,
                target_id=h.target_id,
                digest=h.digest,
                expected=h.hash_value,
            )

    async def test_snapshot_digest_matches_chain_entry(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, package = await _open_package_with_content(db_session, tenant_a)
        snapshots = await svc.snapshots(package.id)
        hashes = await svc.hashes(package.id)
        snap_entries = {h.target_id: h for h in hashes if h.target_type == "snapshot"}
        for snap in snapshots:
            assert snap_entries[snap.id].digest == snap.content_hash

    async def test_tampered_snapshot_detected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, package = await _open_package_with_content(db_session, tenant_a)
        # Trusted state verifies (2 snapshots + 1 item entries; chain links
        # are only reported when broken).
        report = await svc.verify_package(package.id)
        assert report.chain_ok is True
        assert len(report.entries) == 3
        assert all(e.ok for e in report.entries)

        # Tamper: change a snapshot's content directly in the DB.
        snapshot = (await svc.snapshots(package.id))[0]
        await db_session.execute(
            update(EvidenceSnapshot)
            .where(EvidenceSnapshot.id == snapshot.id)
            .values(content={"payments": [{"legacy_id": "P-001", "amount": 999999}]})
        )
        await db_session.commit()
        package_id = package.id  # capture before expiring the identity map
        # The fixture session keeps identity-mapped objects (expire_on_commit
        # False); a real tamper comes from outside this session, so expire it
        # to force a fresh read — exactly what a new request would see.
        db_session.expire_all()

        report = await svc.verify_package(package_id)
        assert report.chain_ok is False
        snapshot_entries = [e for e in report.entries if e.target_type == "snapshot"]
        assert any(not e.ok for e in snapshot_entries)
        broken = [e for e in snapshot_entries if not e.ok][0]
        assert "content hash changed" in broken.detail

    async def test_tampered_chain_link_detected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, package = await _open_package_with_content(db_session, tenant_a)
        # Tamper: flip one link's hash_value in the DB.
        hashes = await svc.hashes(package.id)
        target = hashes[1]
        await db_session.execute(
            update(EvidenceHash).where(EvidenceHash.id == target.id).values(hash_value="0" * 64)
        )
        await db_session.commit()
        package_id = package.id  # capture before expiring the identity map
        db_session.expire_all()

        report = await svc.verify_package(package_id)
        assert report.chain_ok is False
        chain_entries = [e for e in report.entries if e.target_type == "chain"]
        assert any(not e.ok for e in chain_entries)

    async def test_tampered_item_detected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, package = await _open_package_with_content(db_session, tenant_a)
        item = (await svc.items(package.id))[0]
        await db_session.execute(
            update(EvidenceItem)
            .where(EvidenceItem.id == item.id)
            .values(statement="All payments actually matched. Trust us.")
        )
        await db_session.commit()
        package_id = package.id  # capture before expiring the identity map
        db_session.expire_all()

        report = await svc.verify_package(package_id)
        assert report.chain_ok is False


# ---------------------------------------------------------------------------
# Immutability + approval
# ---------------------------------------------------------------------------


class TestImmutabilityAndApproval:
    async def test_approved_package_rejects_additions(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, package = await _open_package_with_content(db_session, tenant_a)
        await svc.approve(
            package.id,
            EvidenceApprovalCreate(decision="approve", approver_id=7, comment="evidence verified"),
            actor=_actor(),
        )
        package = await svc.get_package(package.id)
        assert package.status == PACKAGE_STATUS_APPROVED
        assert package.approved_by == 7
        assert package.approved_at is not None

        with pytest.raises(ConflictError):
            await svc.add_item(
                package.id,
                EvidenceItemCreate(title="late", statement="too late"),
                actor=_actor(),
            )
        with pytest.raises(ConflictError):
            await svc.add_snapshot(
                package.id,
                EvidenceSnapshotCreate(kind="result", label="late", content={}),
                actor=_actor(),
            )

    async def test_approval_decision_validation(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, package = await _open_package_with_content(db_session, tenant_a)
        with pytest.raises(ValidationError):
            await svc.approve(
                package.id,
                EvidenceApprovalCreate(decision="maybe"),
                actor=_actor(),
            )

    async def test_approval_trail_recorded(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, package = await _open_package_with_content(db_session, tenant_a)
        await svc.approve(
            package.id,
            EvidenceApprovalCreate(decision="approve", approver_id=42, comment="ok"),
            actor=_actor(),
        )
        approvals = await svc.approvals(package.id)
        assert len(approvals) == 1
        assert approvals[0].decision == "approve"
        assert approvals[0].approver_id == 42


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    async def test_cross_tenant_package_invisible(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a, package = await _open_package_with_content(db_session, tenant_a)
        assert package.campus_id == 1

        svc_b = EvidenceService(db_session, tenant_b)
        with pytest.raises(NotFoundError):
            await svc_b.get_package(package.id)
        with pytest.raises(NotFoundError):
            await svc_b.items(package.id)
        with pytest.raises(NotFoundError):
            await svc_b.snapshots(package.id)
        with pytest.raises(NotFoundError):
            await svc_b.hashes(package.id)

        packages_b, total_b = await svc_b.list_packages()
        assert total_b == 0

    async def test_cross_tenant_add_and_approve_denied(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a, package = await _open_package_with_content(db_session, tenant_a)
        svc_b = EvidenceService(db_session, tenant_b)
        with pytest.raises(NotFoundError):
            await svc_b.add_item(
                package.id,
                EvidenceItemCreate(title="sneaky", statement="tenant B claim"),
                actor=_actor(),
            )
        with pytest.raises(NotFoundError):
            await svc_b.approve(
                package.id,
                EvidenceApprovalCreate(decision="approve", approver_id=1),
                actor=_actor(),
            )
        with pytest.raises(NotFoundError):
            await svc_b.verify_package(package.id)

    async def test_cross_tenant_tamper_cannot_hide(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a, package = await _open_package_with_content(db_session, tenant_a)
        svc_b = EvidenceService(db_session, tenant_b)
        # B cannot even read the package to verify it, let alone mutate it.
        with pytest.raises(NotFoundError):
            await svc_b.verify_package(package.id)

    async def test_same_package_key_different_campus_ok(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = EvidenceService(db_session, tenant_a)
        svc_b = EvidenceService(db_session, tenant_b)
        package_a = await svc_a.create_package(_package_create(), actor=_actor())
        package_b = await svc_b.create_package(_package_create(), actor=_actor())
        assert package_a.id != package_b.id  # per-campus uniqueness
