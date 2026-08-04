"""Tests for the canonical audit actor model and service actor resolution.

Covers the explicit actor taxonomy (USER/PLATFORM/SYSTEM/WORKER/WEBHOOK),
the guarantee that no actor is ever fabricated as a bare ``0`` user, actor
resolution precedence, secret stripping, and the canonical audit-event
fields (event_id, result, before/after state, tenant/correlation ids).
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import select

from app.domains.audit.actors import (
    UNKNOWN,
    ActorType,
    AuditActor,
    actor_for_user,
)
from app.domains.audit.constants import VERIFY, WEBHOOK_RECEIVED
from app.domains.audit.models import AuditLog
from app.domains.audit.repository import AuditLogRepository
from app.domains.audit.service import (
    RESULT_FAILURE,
    RESULT_SUCCESS,
    AuditService,
)


# ======================================================================
# Actor model
# ======================================================================


class TestAuditActor:
    def test_user_factory(self):
        actor = AuditActor.user(user_id=7, username="alice")
        assert actor.actor_type == ActorType.USER
        assert actor.actor_id == "7"
        assert actor.actor_label == "alice"
        assert actor.is_human is True

    def test_platform_factory(self):
        actor = AuditActor.platform(user_id=9, username="ops")
        assert actor.actor_type == ActorType.PLATFORM
        assert actor.is_human is True

    def test_system_factory_has_reason(self):
        actor = AuditActor.system(reason="migration")
        assert actor.actor_type == ActorType.SYSTEM
        assert actor.actor_id is None
        assert actor.actor_label == "migration"
        assert actor.is_human is False

    def test_worker_factory(self):
        actor = AuditActor.worker(worker_id="w-1")
        assert actor.actor_type == ActorType.WORKER
        assert actor.actor_id == "w-1"
        assert actor.is_human is False

    def test_webhook_factory(self):
        actor = AuditActor.webhook(provider="razorpay")
        assert actor.actor_type == ActorType.WEBHOOK
        assert actor.actor_id == "razorpay"
        assert actor.actor_label == "razorpay"
        assert actor.metadata == {"provider": "razorpay"}
        assert actor.is_human is False

    def test_to_dict(self):
        actor = AuditActor.user(user_id=3, username="bob")
        assert actor.to_dict() == {
            "actor_type": "user",
            "actor_id": "3",
            "actor_label": "bob",
        }

    def test_actor_for_user(self):
        class FakeUser:
            id = 11
            username = "carol"

        actor = actor_for_user(FakeUser())
        assert actor.actor_type == ActorType.USER
        assert actor.actor_id == "11"

    def test_no_bare_zero_actor(self):
        """A bare ``0`` must never represent an actor."""
        with pytest.raises(ValueError):
            AuditActor.user(user_id=0)

    def test_actor_for_user_without_id_raises(self):
        class NoId:
            username = "ghost"

        with pytest.raises(ValueError):
            actor_for_user(NoId())


# ======================================================================
# Service actor resolution
# ======================================================================


class TestActorResolution:
    async def test_explicit_actor_wins(self, db_session):
        svc = AuditService(db_session)
        entry = await svc.record(
            action="VERIFY",
            resource_type="document",
            resource_id="5",
            actor=AuditActor.user(user_id=4, username="verifier"),
            user_id=99,  # legacy field should be ignored for actor
            username="legacy",
        )
        assert entry.actor_type == "user"
        assert entry.actor_id == "4"
        assert entry.username == "legacy"

    async def test_user_id_maps_to_user_actor(self, db_session):
        svc = AuditService(db_session)
        entry = await svc.record(
            action="CREATE",
            resource_type="student",
            user_id=42,
            username="someone",
        )
        assert entry.actor_type == "user"
        assert entry.actor_id == "42"

    async def test_no_actor_is_system_unattributed(self, db_session):
        """No actor supplied → explicit SYSTEM "unattributed", never 0."""
        svc = AuditService(db_session)
        entry = await svc.record(action="CREATE", resource_type="student")
        assert entry.actor_type == "system"
        assert entry.actor_id == UNKNOWN
        assert entry.user_id is None

    async def test_webhook_actor_round_trip(self, db_session):
        svc = AuditService(db_session)
        entry = await svc.record(
            action=WEBHOOK_RECEIVED,
            resource_type="billing",
            resource_id="pay_123",
            actor=AuditActor.webhook(provider="razorpay"),
        )
        assert entry.actor_type == "webhook"
        assert entry.actor_id == "razorpay"


# ======================================================================
# Canonical event fields
# ======================================================================


class TestCanonicalEventFields:
    async def test_event_id_auto_generated_and_unique(self, db_session):
        svc = AuditService(db_session)
        first = await svc.record(action="CREATE", resource_type="student")
        second = await svc.record(action="CREATE", resource_type="student")
        assert len(first.event_id) == 32
        assert first.event_id != second.event_id
        # 32-hex = 16 random bytes
        uuid.UUID(hex=first.event_id)  # raises if not valid hex

    async def test_result_and_failure_reason(self, db_session):
        svc = AuditService(db_session)
        entry = await svc.record(
            action="CREATE",
            resource_type="payment",
            result=RESULT_FAILURE,
            failure_reason="provider declined",
        )
        assert entry.result == RESULT_FAILURE
        assert entry.failure_reason == "provider declined"

    async def test_success_result_default(self, db_session):
        svc = AuditService(db_session)
        entry = await svc.record(action="CREATE", resource_type="student")
        assert entry.result == RESULT_SUCCESS

    async def test_before_after_state_serialized(self, db_session):
        svc = AuditService(db_session)
        entry = await svc.record(
            action="VERIFY",
            resource_type="document",
            before_state={"status": "pending"},
            after_state={"status": "verified", "verified_by": 4},
        )
        assert json.loads(entry.before_state) == {"status": "pending"}
        assert json.loads(entry.after_state) == {"status": "verified", "verified_by": 4}

    async def test_tenant_and_correlation_ids(self, db_session):
        svc = AuditService(db_session)
        entry = await svc.record(
            action="CREATE",
            resource_type="student",
            tenant_id=100,
            campus_id=101,
            request_id="req-1",
            correlation_id="corr-1",
        )
        assert entry.tenant_id == 100
        assert entry.campus_id == 101
        assert entry.request_id == "req-1"
        assert entry.correlation_id == "corr-1"

    async def test_request_id_falls_back_to_correlation_id(self, db_session):
        svc = AuditService(db_session)
        entry = await svc.record(
            action="CREATE",
            resource_type="student",
            correlation_id="corr-2",
        )
        assert entry.request_id == "corr-2"


# ======================================================================
# Secret stripping
# ======================================================================


class TestSecretStripping:
    async def test_secrets_never_stored_in_payloads(self, db_session):
        svc = AuditService(db_session)
        entry = await svc.record(
            action="CREATE",
            resource_type="user",
            details={
                "password": "hunter2",
                "access_token": "eyJ...",
                "refresh_token": "r-123",
                "api_key": "sk-abc",
                "authorization": "Bearer x",
                "secret": "s",
                "email": "ok@example.com",
            },
            before_state={"password_hash": "x", "name": "a"},
            after_state={"token": "y", "name": "b"},
            metadata={"client_secret": "z", "safe": 1},
        )
        details = json.loads(entry.details)
        assert "email" in details
        for k in ("password", "access_token", "refresh_token", "api_key",
                  "authorization", "secret"):
            assert k not in details

        for state in (entry.before_state, entry.after_state):
            parsed = json.loads(state)
            assert "password_hash" not in parsed
            assert "token" not in parsed
            assert "name" in parsed

        meta = json.loads(entry.metadata_json)
        assert "client_secret" not in meta
        assert meta["safe"] == 1

    async def test_actor_metadata_not_leaked(self, db_session):
        svc = AuditService(db_session)
        entry = await svc.record(
            action="CREATE",
            resource_type="user",
            actor=AuditActor.user(user_id=1, username="admin"),
        )
        assert "password" not in json.dumps(entry.details or {})
        assert entry.actor_id == "1"


# ======================================================================
# Repository filters
# ======================================================================


class TestRepositoryActorFilters:
    async def test_filter_by_actor_type(self, db_session):
        repo = AuditLogRepository(db_session)
        await repo.create(
            AuditLog(action="CREATE", resource_type="student", actor_type="user", actor_id="1")
        )
        await repo.create(
            AuditLog(action="CREATE", resource_type="student", actor_type="system", actor_id=UNKNOWN)
        )
        await db_session.flush()

        items, total = await repo.list(actor_type="system")
        assert total == 1
        assert items[0].actor_id == UNKNOWN

    async def test_filter_by_actor_id(self, db_session):
        repo = AuditLogRepository(db_session)
        await repo.create(
            AuditLog(action="VERIFY", resource_type="document", actor_type="user", actor_id="4")
        )
        await repo.create(
            AuditLog(action="VERIFY", resource_type="document", actor_type="user", actor_id="5")
        )
        await db_session.flush()

        items, total = await repo.list(actor_id="4")
        assert total == 1
        assert items[0].actor_id == "4"

    async def test_filter_by_result(self, db_session):
        repo = AuditLogRepository(db_session)
        await repo.create(
            AuditLog(action="CREATE", resource_type="payment", result=RESULT_SUCCESS)
        )
        await repo.create(
            AuditLog(action="CREATE", resource_type="payment", result=RESULT_FAILURE)
        )
        await db_session.flush()

        items, total = await repo.list(result=RESULT_FAILURE)
        assert total == 1
        assert items[0].result == RESULT_FAILURE
