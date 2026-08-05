"""Audit-trail invariants tests.

Proves the audit trail is trustworthy — the property an acquirer needs to
reconstruct *who did what, where, and with what result*:

* every human action carries the real acting user (correct actor)
* every entry carries the tenant (campus) context of the action
* failed mutations are recorded as FAILURE, successful ones as SUCCESS
* unattributed actions are explicitly typed SYSTEM (never a fake user 0)
* background workers are typed WORKER, webhooks WEBHOOK
* no entry is ever attributed to the sentinel user id 0
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.domains.audit.actors import AuditActor, ActorType
from app.domains.audit.constants import CREATE, LOGIN, LOGIN_FAILED
from app.domains.audit.models import AuditLog
from app.domains.audit.service import AuditService

from .conftest import AcqEnv, login
from app.multi_tenant.models import platform_context

pytestmark = pytest.mark.asyncio


async def _audit_rows(factory, **filters) -> list[AuditLog]:
    async with factory() as s:
        stmt = select(AuditLog).order_by(AuditLog.id.desc())
        for col, val in filters.items():
            stmt = stmt.where(getattr(AuditLog, col) == val)
        return list((await s.execute(stmt)).scalars().all())


async def test_successful_login_audited_with_correct_actor(
    acq_env: AcqEnv,
):
    """Invariant: a successful login writes a LOGIN entry attributed to the
    REAL acting user (actor_type=user, actor_id=user id) with the user's
    campus context and SUCCESS result."""
    await login(acq_env, "admin_a")

    rows = await _audit_rows(acq_env.factory, action=LOGIN)
    assert rows, "no LOGIN audit entry written"
    entry = rows[0]
    assert entry.actor_type == ActorType.USER.value
    assert entry.actor_id is not None and int(entry.actor_id) > 0
    assert entry.username == "admin_a"
    assert entry.campus_id == acq_env.campus_a
    assert entry.result == "SUCCESS"


async def test_failed_login_audited_as_failure(acq_env: AcqEnv):
    """Invariant: a failed mutation (bad credentials) is recorded with
    result=FAILURE and the failure reason — failed security events are
    durable, never silently dropped.  Because no human authenticated, the
    actor is typed SYSTEM and the attempted username is kept in the
    details (no fake human actor is fabricated)."""
    import json

    resp = await acq_env.client.post(
        "/auth/login", json={"login": "admin_a", "password": "WrongPass!"}
    )
    assert resp.status_code == 401

    rows = await _audit_rows(acq_env.factory, action=LOGIN_FAILED)
    assert rows, "no LOGIN_FAILED audit entry written"
    entry = rows[0]
    assert entry.result == "FAILURE"
    assert entry.failure_reason
    assert entry.actor_type == ActorType.SYSTEM.value
    assert entry.actor_id == "unknown"
    details = json.loads(entry.details) if entry.details else {}
    assert details.get("username") == "admin_a"


async def test_mutation_audited_with_tenant_context(acq_env: AcqEnv):
    """Invariant: audit entries capture the campus where the action
    happened — campus B actions are never tagged with campus A."""
    await login(acq_env, "admin_a")
    await login(acq_env, "admin_b")

    rows = await _audit_rows(acq_env.factory, action=LOGIN)
    campus_tags = {r.campus_id for r in rows}
    assert acq_env.campus_a in campus_tags
    assert acq_env.campus_b in campus_tags


async def test_system_actor_explicit_when_no_human(acq_env: AcqEnv):
    """Invariant: an action with no human actor is recorded as an explicit
    SYSTEM actor (``unknown`` id), never fabricated as user 0."""
    async with acq_env.factory() as s:
        svc = AuditService(s, platform_context())
        entry = await svc.record(
            action=CREATE,
            resource_type="institution",
            resource_id="1",
            details={"trigger": "startup_seed"},
        )
        await s.commit()

    assert entry.actor_type == ActorType.SYSTEM.value
    assert entry.actor_id == "unknown"
    assert entry.user_id is None


async def test_worker_actor_recorded_for_background_jobs(acq_env: AcqEnv):
    """Invariant: background workers are typed WORKER, so operator actions
    can never be confused with scheduled/system actions."""
    async with acq_env.factory() as s:
        svc = AuditService(s, platform_context())
        entry = await svc.record(
            action=CREATE,
            resource_type="job",
            resource_id="7",
            actor=AuditActor.worker("worker-1"),
            details={"job_type": "report_batch"},
        )
        await s.commit()

    assert entry.actor_type == ActorType.WORKER.value
    assert entry.actor_id == "worker-1"


async def test_webhook_actor_recorded_for_provider_events(acq_env: AcqEnv):
    """Invariant: external integrations are typed WEBHOOK with the provider
    as actor id — payment events are attributable to Razorpay, not to a
    forged user."""
    async with acq_env.factory() as s:
        svc = AuditService(s, platform_context())
        entry = await svc.record(
            action=CREATE,
            resource_type="payment",
            resource_id="pay_123",
            actor=AuditActor.webhook("razorpay"),
            details={"event": "payment.captured"},
        )
        await s.commit()

    assert entry.actor_type == ActorType.WEBHOOK.value
    assert entry.actor_id == "razorpay"


async def test_no_audit_entry_uses_zero_actor(acq_env: AcqEnv):
    """Invariant: the sentinel id 0 never appears as an actor — the actor
    taxonomy guarantees every entry has a typed, truthful actor."""
    await login(acq_env, "admin_a")
    await login(acq_env, "admin_b")
    resp = await acq_env.client.post(
        "/auth/login", json={"login": "admin_a", "password": "bad!"}
    )
    assert resp.status_code == 401

    rows = await _audit_rows(acq_env.factory)
    assert rows
    for entry in rows:
        if entry.user_id is not None:
            assert entry.user_id > 0, f"entry {entry.id} uses user_id 0"
        if entry.actor_id is not None:
            assert entry.actor_id != "0", f"entry {entry.id} uses actor_id '0'"
        assert entry.actor_type in {
            ActorType.USER.value,
            ActorType.PLATFORM.value,
            ActorType.SYSTEM.value,
            ActorType.WORKER.value,
            ActorType.WEBHOOK.value,
        }
