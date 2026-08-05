"""Integration tests for the explicit-actor audit contract at real call sites.

Verifies that:
  - failed logins produce ``LOGIN_FAILED`` with the SYSTEM "unattributed"
    actor (there is no authenticated user to blame) and ``result=FAILURE``
  - successful logins produce ``LOGIN`` attributed to the real user
  - background job execution is attributed to the WORKER actor
  - migration engine runs are attributed to the SYSTEM actor
  - the audit middleware resolves actors correctly for authenticated and
    unauthenticated requests
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.domains.audit.models import AuditLog
from app.multi_tenant.models import platform_context


# ======================================================================
# Login audit integration (via the real API)
# ======================================================================


class TestLoginAuditIntegration:
    async def test_failed_login_is_attributed_to_system(
        self, api_client, admin_headers
    ) -> None:
        """A failed login has no authenticated actor → SYSTEM/unattributed
        with result=FAILURE, and the attempted identity is captured."""
        resp = await api_client.post(
            "/auth/login",
            json={"login": "admin", "password": "definitely-wrong-pass"},
        )
        assert resp.status_code == 401

        entries_resp = await api_client.get(
            "/api/admin/audit-logs?action=LOGIN_FAILED",
            headers=admin_headers,
        )
        assert entries_resp.status_code == 200, entries_resp.text
        body = entries_resp.json()
        assert body["total"] >= 1

        entry = body["items"][0]
        assert entry["actor_type"] == "system"
        assert entry["actor_id"] == "unknown"
        assert entry["user_id"] is None
        assert entry["result"] == "FAILURE"
        assert entry["failure_reason"] in (
            "invalid_password", "user_not_found",
        )

    async def test_successful_login_is_attributed_to_real_user(
        self, api_client, admin_headers
    ) -> None:
        resp = await api_client.post(
            "/auth/login",
            json={"login": "admin", "password": "AdminPass123!"},
        )
        assert resp.status_code == 200, resp.text

        # Resolve the seeded admin's id so the actor id can be asserted.
        me_resp = await api_client.get("/auth/me", headers=admin_headers)
        assert me_resp.status_code == 200
        admin_id = me_resp.json()["id"]

        entries_resp = await api_client.get(
            "/api/admin/audit-logs?action=LOGIN",
            headers=admin_headers,
        )
        assert entries_resp.status_code == 200, entries_resp.text
        body = entries_resp.json()
        assert body["total"] >= 1

        entry = body["items"][0]
        assert entry["actor_type"] == "user"
        assert entry["actor_id"] == str(admin_id)
        assert entry["result"] == "SUCCESS"

    async def test_unauthorized_mutating_request_leaves_no_success_audit(
        self, api_client, admin_headers
    ) -> None:
        """An unauthorized action must not produce a misleading SUCCESS
        audit entry."""
        # DELETE a student without any auth token → 401 (auth gate).
        resp = await api_client.delete("/students/1")
        assert resp.status_code in (401, 403), resp.text

        entries_resp = await api_client.get(
            "/api/admin/audit-logs?action=DELETE&result=SUCCESS",
            headers=admin_headers,
        )
        assert entries_resp.status_code == 200, entries_resp.text
        body = entries_resp.json()
        # No success audit entries (none should exist for this unauthenticated
        # action; and even if a middleware entry existed it would be FAILURE).
        assert body["total"] == 0


# ======================================================================
# Job worker audit integration
# ======================================================================


class TestWorkerAuditIntegration:
    async def test_job_execution_is_attributed_to_worker(
        self, db_session
    ) -> None:
        import datetime

        from app.domains.jobs.models import Job
        from app.domains.jobs.registry import BaseJob, register_job
        from app.domains.jobs import registry as _job_registry_module
        from app.domains.jobs.repository import JobRepository
        from app.domains.jobs.service import JobService

        class _TestJob(BaseJob):
            job_type = "audit.test_job"

            async def run(self, job, session):
                return {"ok": True}

        # Snapshot the global registry and restore it afterwards.  A naive
        # ``clear_registry()`` would wipe job types registered earlier in
        # the same process (e.g. ``report_builder.export`` imported by an
        # earlier suite), and re-importing modules cannot re-run their
        # ``@register_job`` decorators because Python caches them in
        # ``sys.modules`` — leaving later suites with an empty registry.
        snapshot = dict(_job_registry_module._registry)
        try:
            register_job(_TestJob)
            now = datetime.datetime.now(datetime.timezone.utc)
            job = Job(
                job_type="audit.test_job",
                status="pending",
                params={},
                priority=100,
                max_retries=3,
                retry_count=0,
                created_at=now,
                updated_at=now,
                progress=0.0,
            )
            db_session.add(job)
            await db_session.flush()

            claimed = await JobRepository(db_session, platform_context()).acquire_next(
                job_types=["audit.test_job"]
            )
            assert claimed is not None, "test job was not claimed"
            await JobService(db_session, platform_context()).execute_job(claimed.id)
            await db_session.flush()

            result = await db_session.execute(
                select(AuditLog).where(AuditLog.action == "JOB_EXECUTED")
            )
            entries = result.scalars().all()
            assert len(entries) >= 1

            entry = entries[-1]
            assert entry.actor_type == "worker"
            assert entry.actor_id is None  # no worker id supplied
            assert entry.resource_type == "job"
            assert entry.result == "SUCCESS"
        finally:
            _job_registry_module._registry.clear()
            _job_registry_module._registry.update(snapshot)


# ======================================================================
# Migration engine audit integration
# ======================================================================


class TestMigrationAuditIntegration:
    async def test_migration_run_is_attributed_to_system(
        self, db_session
    ) -> None:
        from app.domains.migration.base import BaseMigrator, MigratorResult
        from app.domains.migration.engine import (
            MigrationEngine,
            _registry,
        )

        class FakeMigrator(BaseMigrator):
            entity_type = "audit.test_entities"

            async def validate(self, records, session, run_id, log_repo):
                return records

            async def migrate(self, records, session, run_id, mapping_repo, log_repo):
                return MigratorResult(
                    entity_type=self.entity_type,
                    total=len(records),
                    imported=len(records),
                )

        migrator = FakeMigrator()
        prev = _registry.get(migrator.entity_type)
        _registry[migrator.entity_type] = migrator
        try:
            await MigrationEngine(db_session).run(
                "audit.test_entities",
                [{"id": 1}, {"id": 2}],
                is_dry_run=False,
                source="test",
            )
            await db_session.flush()

            result = await db_session.execute(
                select(AuditLog).where(AuditLog.action == "MIGRATION_RUN")
            )
            entries = result.scalars().all()
            assert len(entries) >= 1

            entry = entries[-1]
            assert entry.actor_type == "system"
            assert entry.resource_type == "migration"
            assert entry.result == "SUCCESS"
            details = json.loads(entry.details)
            assert details["entity_type"] == "audit.test_entities"
            assert details["imported"] == 2
        finally:
            if prev is None:
                _registry.pop(migrator.entity_type, None)
            else:
                _registry[migrator.entity_type] = prev


# ======================================================================
# Middleware actor resolution (pure-function level)
# ======================================================================


class TestMiddlewareActorResolution:
    def test_unauthenticated_request_maps_to_system_unattributed(self):
        from app.domains.audit.middleware import _extract_audit_metadata

        request = _make_mock_request(method="POST", path="/auth/register")
        meta = _extract_audit_metadata(request)
        assert meta["actor_type"] == "system"
        assert meta["actor_id"] == "unattributed"
        assert meta["user_id"] is None

    def test_authenticated_request_maps_to_user(self):
        from app.domains.audit.middleware import _extract_audit_metadata
        from app.domains.auth.security import create_access_token

        token = create_access_token({"sub": "7", "username": "alice"})
        request = _make_mock_request(
            method="PATCH",
            path="/students/1",
            headers={"Authorization": f"Bearer {token}"},
        )
        meta = _extract_audit_metadata(request)
        assert meta["actor_type"] == "user"
        assert meta["actor_id"] == "7"
        assert meta["username"] == "alice"

    def test_semantic_action_mapping(self):
        from app.domains.audit.middleware import _semantic_action

        assert _semantic_action("POST", "/students/123/approve") == "APPROVE"
        assert _semantic_action("POST", "/documents/1/verify") == "VERIFY"
        assert _semantic_action("POST", "/fees/payments") == "CREATE"
        assert _semantic_action("DELETE", "/students/1") == "DELETE"
        assert _semantic_action("PATCH", "/students/1") == "UPDATE"

    def test_build_actor_user(self):
        from app.domains.audit.actors import ActorType
        from app.domains.audit.middleware import _build_actor

        actor = _build_actor("user", "7", "alice")
        assert actor.actor_type == ActorType.USER
        assert actor.actor_id == "7"

    def test_build_actor_unattributed_system(self):
        from app.domains.audit.actors import ActorType
        from app.domains.audit.middleware import _build_actor

        actor = _build_actor("system", "unattributed", None)
        assert actor.actor_type == ActorType.SYSTEM


def _make_mock_request(method: str = "GET", path: str = "/", headers=None) -> object:
    class _MockURL:
        def __init__(self, path: str):
            self.path = path

    class _MockScope:
        def __init__(self, headers):
            self.headers = headers or {}

    class _MockHeaders:
        def __init__(self, headers: dict):
            self._headers = headers

        def get(self, key: str, default=None):
            return self._headers.get(key, default)

    class _MockRequest:
        def __init__(self, method: str, path: str, headers=None):
            self.method = method
            self.url = _MockURL(path)
            self.headers = _MockHeaders(headers or {})
            self.client = type("C", (), {"host": "127.0.0.1"})()
            self.state = type("S", (), {})()
            self.state.tenant = None

    return _MockRequest(method=method, path=path, headers=headers)
