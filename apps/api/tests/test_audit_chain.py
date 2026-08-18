"""Tamper-evident audit chain tests (TASK 13).

Covers:

- normal verification: a clean chain verifies (payload hashes, links,
  signatures, checkpoints)
- modification: editing an audit row's content is detected
- chain break: altering a chain entry's current_hash is detected
- deletion: removing a middle chain entry (INDEX_GAP / PREV_MISMATCH)
  and a tail after a checkpoint (CHECKPOINT_TAIL_DELETION) is detected
- reordering: swapping entries is detected
- missing audit row: deleting the audit row a chain entry covers is detected
- uncovered rows: audit rows without chain entries are reported as a
  coverage gap, not silently claimed as chained
- signatures: right secret verifies; wrong secret is flagged
- tenant isolation: per-campus chains are independent — a tamper in
  campus A never breaks campus B, and B cannot read A's chain
- integration: AuditService.record() chains every event automatically
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.audit.actors import ActorType, AuditActor
from app.domains.audit.models import AuditLog
from app.domains.audit.service import AuditService
from app.multi_tenant.models import TenantContext
from app.platform.cryptography.models import (
    AuditChainEntry,
)
from app.platform.cryptography.service import AuditChainService
from app.platform.cryptography.verifier import (
    F_CHECKPOINT_TAIL_DELETION,
    F_INDEX_GAP,
    F_LINK_BROKEN,
    F_MISSING_ENTRY_REF,
    F_PAYLOAD_MISMATCH,
    F_PREV_MISMATCH,
    F_SIGNATURE_INVALID,
)

SECRET = "test-chain-secret"

# The audit service chains every event with the server secret read from
# the environment — set it before any recording so signatures match.
os.environ["AUDIT_CHAIN_SECRET"] = SECRET


@pytest.fixture
def tenant_a() -> TenantContext:
    return TenantContext(campus_id=1, institution_id=1, user_id=99)


@pytest.fixture
def tenant_b() -> TenantContext:
    return TenantContext(campus_id=2, institution_id=1, user_id=98)


def _actor(user_id: int = 99) -> AuditActor:
    return AuditActor(actor_type=ActorType.USER, actor_id=str(user_id))


async def _record(svc: AuditService, count: int = 3, *, prefix: str = "student") -> None:
    actor = _actor()
    for i in range(count):
        await svc.record(
            action="CREATE",
            resource_type=prefix,
            resource_id=str(i),
            actor=actor,
            details={"i": i},
        )


def _codes(result) -> list[str]:
    return [f.code for f in result.findings]


# ---------------------------------------------------------------------------
# Normal verification
# ---------------------------------------------------------------------------


class TestNormalVerification:
    async def test_clean_chain_verifies(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = AuditService(db_session, tenant_a)
        await _record(svc)
        chain = AuditChainService(db_session, tenant_a, secret=SECRET)
        result = await chain.verify(secret=SECRET)
        assert result.chain_ok is True
        assert result.entries == 3
        assert result.signatures_checked is True
        assert result.findings == []

    async def test_signatures_invalid_with_wrong_secret(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = AuditService(db_session, tenant_a)
        await _record(svc)
        chain = AuditChainService(db_session, tenant_a, secret=SECRET)
        result = await chain.verify(secret="wrong-secret")
        assert result.chain_ok is False
        assert _codes(result).count(F_SIGNATURE_INVALID) == 3

    async def test_chain_entries_append_per_audit_event(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = AuditService(db_session, tenant_a)
        await _record(svc, count=3)
        rows = (await db_session.execute(select(AuditChainEntry))).scalars().all()
        assert len(rows) == 3
        assert [r.chain_index for r in rows] == [0, 1, 2]
        # prev linking.
        assert rows[0].prev_hash == ""
        assert rows[1].prev_hash == rows[0].current_hash
        assert rows[2].prev_hash == rows[1].current_hash

    async def test_checkpoint_verifies(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = AuditService(db_session, tenant_a)
        await _record(svc, count=4)
        chain = AuditChainService(db_session, tenant_a, secret=SECRET)
        cp = await chain.checkpoint()
        assert cp.up_to_chain_index == 3
        result = await chain.verify(secret=SECRET)
        assert result.chain_ok is True
        assert result.checkpoints == 1

    async def test_uncovered_audit_rows_reported_as_gap(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        # A row written WITHOUT a chain entry (e.g. before the chain was
        # enabled) must be reported as a coverage gap — never silently
        # claimed as chained, and not treated as a chain break.
        svc = AuditService(db_session, tenant_a)
        await _record(svc, count=2)
        raw = AuditLog(
            event_id="f" * 32,
            actor_type="system",
            actor_id="seed",
            action="SEED",
            resource_type="legacy",
            resource_id="1",
            campus_id=1,
            tenant_id=1,
            result="SUCCESS",
            details="{}",
        )
        db_session.add(raw)
        await db_session.flush()

        chain = AuditChainService(db_session, tenant_a, secret=SECRET)
        result = await chain.verify(secret=SECRET)
        assert result.chain_ok is True  # the gap is not a chain break
        assert result.entries == 2
        assert result.uncovered_audit_rows == 1


# ---------------------------------------------------------------------------
# Tampering
# ---------------------------------------------------------------------------


class TestTampering:
    async def test_modified_audit_row_detected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = AuditService(db_session, tenant_a)
        await _record(svc)
        row = (await db_session.execute(select(AuditLog))).scalars().first()
        await db_session.execute(
            update(AuditLog).where(AuditLog.id == row.id).values(details='{"i": 99999}')
        )
        await db_session.commit()
        db_session.expire_all()
        result = await AuditChainService(db_session, tenant_a, secret=SECRET).verify(secret=SECRET)
        assert result.chain_ok is False
        assert F_PAYLOAD_MISMATCH in _codes(result)

    async def test_modified_chain_link_detected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = AuditService(db_session, tenant_a)
        await _record(svc)
        entry = (await db_session.execute(select(AuditChainEntry))).scalars().first()
        await db_session.execute(
            update(AuditChainEntry)
            .where(AuditChainEntry.id == entry.id)
            .values(current_hash="0" * 64)
        )
        await db_session.commit()
        db_session.expire_all()
        result = await AuditChainService(db_session, tenant_a, secret=SECRET).verify(secret=SECRET)
        assert result.chain_ok is False
        assert F_LINK_BROKEN in _codes(result)

    async def test_deleted_middle_entry_detected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = AuditService(db_session, tenant_a)
        await _record(svc, count=3)
        await db_session.execute(delete(AuditChainEntry).where(AuditChainEntry.chain_index == 1))
        await db_session.commit()
        db_session.expire_all()
        result = await AuditChainService(db_session, tenant_a, secret=SECRET).verify(secret=SECRET)
        assert result.chain_ok is False
        codes = _codes(result)
        assert F_INDEX_GAP in codes
        assert F_PREV_MISMATCH in codes

    async def test_deleted_tail_after_checkpoint_detected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = AuditService(db_session, tenant_a)
        await _record(svc, count=4)
        chain = AuditChainService(db_session, tenant_a, secret=SECRET)
        await chain.checkpoint()
        # Delete the last two chain entries (tail).
        await db_session.execute(delete(AuditChainEntry).where(AuditChainEntry.chain_index >= 2))
        await db_session.commit()
        db_session.expire_all()
        result = await chain.verify(secret=SECRET)
        assert result.chain_ok is False
        assert F_CHECKPOINT_TAIL_DELETION in _codes(result)

    async def test_reordered_entries_detected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = AuditService(db_session, tenant_a)
        await _record(svc, count=3)
        # Swap chain_index 0 and 1 (and their payload bindings stay put —
        # a real reorder moves the whole row).
        rows = (await db_session.execute(select(AuditChainEntry))).scalars().all()
        e0, e1 = rows[0], rows[1]
        await db_session.execute(
            update(AuditChainEntry)
            .where(AuditChainEntry.id == e0.id)
            .values(
                chain_index=e1.chain_index, prev_hash=e1.prev_hash, current_hash=e1.current_hash
            )
        )
        await db_session.execute(
            update(AuditChainEntry)
            .where(AuditChainEntry.id == e1.id)
            .values(
                chain_index=e0.chain_index, prev_hash=e0.prev_hash, current_hash=e0.current_hash
            )
        )
        await db_session.commit()
        db_session.expire_all()
        result = await AuditChainService(db_session, tenant_a, secret=SECRET).verify(secret=SECRET)
        assert result.chain_ok is False
        codes = _codes(result)
        assert F_PREV_MISMATCH in codes or F_LINK_BROKEN in codes

    async def test_deleted_audit_row_detected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = AuditService(db_session, tenant_a)
        await _record(svc, count=2)
        row = (await db_session.execute(select(AuditLog))).scalars().first()
        await db_session.execute(delete(AuditLog).where(AuditLog.id == row.id))
        await db_session.commit()
        db_session.expire_all()
        result = await AuditChainService(db_session, tenant_a, secret=SECRET).verify(secret=SECRET)
        assert result.chain_ok is False
        assert F_MISSING_ENTRY_REF in _codes(result)


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    async def test_cross_tenant_chain_invisible(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = AuditService(db_session, tenant_a)
        await _record(svc_a, prefix="student")
        # B's chain is empty (per-campus chains).
        chain_b = AuditChainService(db_session, tenant_b, secret=SECRET)
        result_b = await chain_b.verify(secret=SECRET)
        assert result_b.entries == 0
        assert result_b.chain_ok is True

    async def test_tamper_in_campus_a_does_not_break_campus_b(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = AuditService(db_session, tenant_a)
        svc_b = AuditService(db_session, tenant_b)
        await _record(svc_a, prefix="student")
        await _record(svc_b, prefix="fee")

        # Tamper A's audit row.
        row_a = (
            (await db_session.execute(select(AuditLog).where(AuditLog.campus_id == 1)))
            .scalars()
            .first()
        )
        await db_session.execute(
            update(AuditLog).where(AuditLog.id == row_a.id).values(details='{"i": 999}')
        )
        await db_session.commit()
        db_session.expire_all()

        result_a = await AuditChainService(db_session, tenant_a, secret=SECRET).verify(
            secret=SECRET
        )
        result_b = await AuditChainService(db_session, tenant_b, secret=SECRET).verify(
            secret=SECRET
        )
        assert result_a.chain_ok is False
        assert result_b.chain_ok is True

    async def test_same_campus_different_user_sees_same_chain(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        # Two users in the same campus share the campus chain.
        svc = AuditService(db_session, tenant_a)
        await _record(svc)
        other = TenantContext(campus_id=1, institution_id=1, user_id=77)
        result = await AuditChainService(db_session, other, secret=SECRET).verify(secret=SECRET)
        assert result.entries == 3
        assert result.chain_ok is True

    async def test_platform_chain_separate_from_campus_chain(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = AuditService(db_session, tenant_a)
        await _record(svc)
        platform = TenantContext(user_id=1, platform=True)
        platform_svc = AuditService(db_session, platform)
        await platform_svc.record(
            action="PLATFORM_OP", resource_type="tenant", resource_id="1", actor=_actor()
        )
        campus_result = await AuditChainService(db_session, tenant_a, secret=SECRET).verify(
            secret=SECRET
        )
        platform_result = await AuditChainService(
            db_session, platform, secret=SECRET
        ).verify_campus(None, secret=SECRET)
        assert campus_result.entries == 3
        assert platform_result.entries == 1
        assert campus_result.chain_ok and platform_result.chain_ok
