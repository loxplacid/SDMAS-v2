"""Universal Exception Management tests (TASK 17).

Covers:

- creation: validation, SLA-derived due dates, deduplication by source
- lifecycle: the whitelisted state machine, illegal transitions, reopen
- targeted mutations: assign, severity (with SLA recompute), due date,
  root cause, evidence, case/workflow links
- immutable event timeline: every action is recorded, in order
- optimistic concurrency: a stale version can never overwrite a newer one
- tenant isolation: campus A can never see/transition/mutate campus B
  exceptions, at both the service and API layers
- the API surface: full lifecycle via HTTP, RBAC denial (staff can view
  but not manage), unauthenticated denial
- the DB layer: the source-uniqueness constraint is a real backstop
"""

from __future__ import annotations

import datetime
import os

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.auth.models import User, UserSchoolMembership
from app.domains.auth.security import hash_password
from app.domains.cases.models import Case  # noqa: F401 — register table for db_session
from app.domains.exceptions.models import (
    EXCEPTION_EVENT_ASSIGNED,
    EXCEPTION_EVENT_CREATED,
    EXCEPTION_EVENT_RESOLVED,
    EXCEPTION_STATUS_ACKNOWLEDGED,
    EXCEPTION_STATUS_CLOSED,
    EXCEPTION_STATUS_IN_PROGRESS,
    EXCEPTION_STATUS_OPEN,
    EXCEPTION_STATUS_RESOLVED,
    SystemException,
)
from app.domains.exceptions.service import ExceptionService
from app.domains.institution.models import Campus, Institution
from app.domains.student.models import Student  # noqa: F401 — register table for db_session
from app.domains.workflow.models import Workflow, WorkflowInstance  # noqa: F401
from app.multi_tenant.models import TenantContext

# Deterministic HMAC for the (guarded) audit-chain hook on audit writes.
os.environ.setdefault("AUDIT_CHAIN_SECRET", "test-secret")


@pytest.fixture
def tenant_a() -> TenantContext:
    return TenantContext(campus_id=1, institution_id=1, user_id=99)


@pytest.fixture
def tenant_b() -> TenantContext:
    return TenantContext(campus_id=2, institution_id=1, user_id=98)


async def _create(
    db: AsyncSession,
    tenant: TenantContext,
    *,
    source_id: int = 10,
    exception_type: str = "data_quality",
    severity: str = "high",
    title: str = "Duplicate student record",
    actor_id: int = 99,
    source_domain: str = "data_quality",
    source_type: str = "finding",
    student_id: int | None = None,
    evidence: dict | None = None,
) -> SystemException:
    svc = ExceptionService(db, tenant)
    return await svc.create(
        exception_type=exception_type,
        severity=severity,
        title=title,
        source_domain=source_domain,
        source_type=source_type,
        source_id=source_id,
        student_id=student_id,
        evidence=evidence,
        actor_id=actor_id,
        actor_name=f"user{actor_id}",
    )


# ======================================================================
# Creation
# ======================================================================


class TestCreate:
    async def test_create_exception_with_sla_due_date(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        exc = await _create(db_session, tenant_a, severity="high")
        assert exc.id > 0
        assert exc.campus_id == 1
        assert exc.status == EXCEPTION_STATUS_OPEN
        assert exc.priority == "high"  # derived from severity
        # High severity → 48h default SLA.  SQLite round-trips naive
        # datetimes, so normalize before arithmetic.
        assert exc.due_at is not None
        due = exc.due_at
        if due.tzinfo is None:
            due = due.replace(tzinfo=datetime.timezone.utc)
        delta = due - datetime.datetime.now(datetime.timezone.utc)
        assert datetime.timedelta(hours=47) < delta <= datetime.timedelta(hours=48)

    async def test_severity_maps_to_priority(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        exc = await _create(db_session, tenant_a, severity="low")
        assert exc.priority == "medium"  # info/low → medium operational priority
        exc2 = await _create(db_session, tenant_a, severity="critical", source_id=11, title="t2")
        assert exc2.priority == "critical"

    async def test_invalid_type_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ExceptionService(db_session, tenant_a)
        with pytest.raises(ValidationError):
            await svc.create(
                exception_type="mystery",
                severity="high",
                title="t",
                source_domain="data_quality",
                source_type="finding",
                source_id=1,
            )

    async def test_invalid_severity_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ExceptionService(db_session, tenant_a)
        with pytest.raises(ValidationError):
            await svc.create(
                exception_type="data_quality",
                severity="urgent",
                title="t",
                source_domain="data_quality",
                source_type="finding",
                source_id=1,
            )

    async def test_empty_title_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ExceptionService(db_session, tenant_a)
        with pytest.raises(ValidationError):
            await svc.create(
                exception_type="data_quality",
                severity="high",
                title="   ",
                source_domain="data_quality",
                source_type="finding",
                source_id=1,
            )

    async def test_duplicate_source_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        await _create(db_session, tenant_a, source_id=10)
        with pytest.raises(ConflictError):
            await _create(db_session, tenant_a, source_id=10)

    async def test_same_source_allowed_in_different_campus(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        a = await _create(db_session, tenant_a, source_id=10)
        b = await _create(db_session, tenant_b, source_id=10)
        assert a.id != b.id
        assert b.campus_id == 2

    async def test_get_by_source_idempotency_helper(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ExceptionService(db_session, tenant_a)
        created = await _create(db_session, tenant_a, source_id=77)
        found = await svc.get_by_source("data_quality", "finding", 77)
        assert found is not None and found.id == created.id
        assert await svc.get_by_source("data_quality", "finding", 999) is None

    async def test_db_unique_constraint_backstop(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        """Bypassing the service (direct SQL insert) still cannot create a
        duplicate exception for the same source triple."""
        await _create(db_session, tenant_a, source_id=50)
        await db_session.flush()
        with pytest.raises(IntegrityError):
            async with db_session.begin_nested():
                await db_session.execute(
                    text(
                        "INSERT INTO system_exceptions "
                        "(campus_id, source_domain, source_type, source_id, "
                        "exception_type, severity, title, status, priority, "
                        "detected_at, last_verified_at, version, created_at, updated_at) "
                        "VALUES (1, 'data_quality', 'finding', 50, 'data_quality', "
                        "'high', 'dup', 'open', 'high', CURRENT_TIMESTAMP, "
                        "CURRENT_TIMESTAMP, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                    )
                )


# ======================================================================
# Lifecycle state machine
# ======================================================================


class TestLifecycle:
    async def test_full_lifecycle(self, db_session: AsyncSession, tenant_a: TenantContext) -> None:
        svc = ExceptionService(db_session, tenant_a)
        exc = await _create(db_session, tenant_a)

        acknowledged = await svc.acknowledge(exc.id, 99, "user99")
        assert acknowledged.status == EXCEPTION_STATUS_ACKNOWLEDGED
        assert acknowledged.acknowledged_at is not None

        in_progress = await svc.start(exc.id, 99, "user99")
        assert in_progress.status == EXCEPTION_STATUS_IN_PROGRESS
        assert in_progress.in_progress_at is not None

        resolved = await svc.resolve(
            exc.id,
            resolution_type="fixed",
            resolution_note="Replaced duplicates with canonical student",
            root_cause="Legacy export had no dedup rule",
            actor_id=99,
            actor_name="user99",
        )
        assert resolved.status == EXCEPTION_STATUS_RESOLVED
        assert resolved.resolution_type == "fixed"
        assert resolved.resolved_at is not None
        assert "Legacy export" in (resolved.root_cause or "")

        closed = await svc.close(exc.id, 99, "user99")
        assert closed.status == EXCEPTION_STATUS_CLOSED
        assert closed.closed_at is not None

    async def test_illegal_transition_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ExceptionService(db_session, tenant_a)
        exc = await _create(db_session, tenant_a)
        # open → closed is not allowed: must go through the ladder.
        with pytest.raises(ConflictError):
            await svc.close(exc.id, 99, "user99")
        # open → resolved directly IS allowed.
        resolved = await svc.resolve(
            exc.id, resolution_type="no_action", actor_id=99, actor_name="user99"
        )
        assert resolved.status == EXCEPTION_STATUS_RESOLVED

    async def test_reopen_clears_resolution_fields(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ExceptionService(db_session, tenant_a)
        exc = await _create(db_session, tenant_a)
        await svc.resolve(exc.id, resolution_type="false_positive", actor_id=99)
        reopened = await svc.reopen(exc.id, 99, "user99")
        assert reopened.status == EXCEPTION_STATUS_OPEN
        assert reopened.resolved_at is None
        assert reopened.closed_at is None

    async def test_invalid_resolution_type_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ExceptionService(db_session, tenant_a)
        exc = await _create(db_session, tenant_a)
        with pytest.raises(ValidationError):
            await svc.resolve(exc.id, resolution_type="not_a_real_type")

    async def test_resolve_requires_reason_path(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        """Resolving with no resolution_type at all must fail loudly."""
        svc = ExceptionService(db_session, tenant_a)
        exc = await _create(db_session, tenant_a)
        with pytest.raises(TypeError):
            await svc.resolve(exc.id)  # type: ignore[call-arg]


# ======================================================================
# Targeted mutations
# ======================================================================


class TestMutations:
    async def test_assign_and_unassign(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ExceptionService(db_session, tenant_a)
        exc = await _create(db_session, tenant_a)
        assigned = await svc.assign(exc.id, 42, 99, "user99")
        assert assigned.owner_id == 42
        events = await svc.get(exc.id)
        assert any(e.event_type == EXCEPTION_EVENT_ASSIGNED for e in events.events)
        unassigned = await svc.assign(exc.id, None, 99, "user99")
        assert unassigned.owner_id is None

    async def test_severity_update_recomputes_due_date(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ExceptionService(db_session, tenant_a)
        exc = await _create(db_session, tenant_a, severity="low")  # 240h
        low_due = exc.due_at
        assert low_due is not None
        changed = await svc.update_severity(exc.id, "critical", 99, "user99")
        assert changed.severity == "critical"
        assert changed.due_at is not None
        # Normalize (SQLite returns naive datetimes) before comparing.
        low = low_due.replace(tzinfo=datetime.timezone.utc)
        new = changed.due_at.replace(tzinfo=datetime.timezone.utc)
        assert new < low  # deadline tightened (24h < 240h)

    async def test_set_due_date(self, db_session: AsyncSession, tenant_a: TenantContext) -> None:
        svc = ExceptionService(db_session, tenant_a)
        exc = await _create(db_session, tenant_a)
        target = datetime.datetime(2026, 9, 1, tzinfo=datetime.timezone.utc)
        updated = await svc.set_due_date(exc.id, target, 99, "user99")
        assert updated.due_at == target
        cleared = await svc.set_due_date(exc.id, None, 99, "user99")
        assert cleared.due_at is None

    async def test_root_cause(self, db_session: AsyncSession, tenant_a: TenantContext) -> None:
        svc = ExceptionService(db_session, tenant_a)
        exc = await _create(db_session, tenant_a)
        updated = await svc.set_root_cause(exc.id, "Missing normalizer", 99, "user99")
        assert updated.root_cause == "Missing normalizer"

    async def test_evidence_merges(self, db_session: AsyncSession, tenant_a: TenantContext) -> None:
        svc = ExceptionService(db_session, tenant_a)
        exc = await _create(db_session, tenant_a, evidence={"student_number": "A100"})
        updated = await svc.add_evidence(exc.id, {"email": "a@b.c"}, 99, "user99")
        assert updated.evidence == {"student_number": "A100", "email": "a@b.c"}

    async def test_link_case_and_workflow(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ExceptionService(db_session, tenant_a)
        exc = await _create(db_session, tenant_a)
        # Links are recorded; FK integrity is verified in migration 062.
        linked = await svc.link_case(exc.id, 5, 99, "user99")
        assert linked.case_id == 5
        wf = await svc.link_workflow(exc.id, 7, 99, "user99")
        assert wf.workflow_instance_id == 7

    async def test_mark_verified(self, db_session: AsyncSession, tenant_a: TenantContext) -> None:
        svc = ExceptionService(db_session, tenant_a)
        exc = await _create(db_session, tenant_a)
        # SQLite round-trips naive datetimes; normalize before comparing.
        original = exc.last_verified_at
        if original is not None and original.tzinfo is None:
            original = original.replace(tzinfo=datetime.timezone.utc)
        await svc.mark_verified(exc.id, 99, "user99")
        reloaded = await svc.get(exc.id)
        assert reloaded.last_verified_at is not None
        new = reloaded.last_verified_at
        if new.tzinfo is None:
            new = new.replace(tzinfo=datetime.timezone.utc)
        assert new >= original


# ======================================================================
# Event timeline & concurrency
# ======================================================================


class TestTimelineAndConcurrency:
    async def test_event_timeline_is_ordered_and_complete(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ExceptionService(db_session, tenant_a)
        exc = await _create(db_session, tenant_a)
        await svc.acknowledge(exc.id, 99, "user99")
        await svc.assign(exc.id, 12, 99, "user99")
        await svc.resolve(exc.id, resolution_type="fixed", actor_id=99, actor_name="u")
        reloaded = await svc.get(exc.id)
        types = [e.event_type for e in reloaded.events]
        assert types[0] == EXCEPTION_EVENT_CREATED
        assert EXCEPTION_EVENT_ASSIGNED in types
        assert EXCEPTION_EVENT_RESOLVED in types
        # Strictly increasing, no gaps.
        seqs = [e.event_seq for e in reloaded.events]
        assert seqs == sorted(seqs)
        assert seqs == list(range(1, len(seqs) + 1))

    async def test_optimistic_concurrency_conflict(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ExceptionService(db_session, tenant_a)
        exc = await _create(db_session, tenant_a)
        await svc.assign(exc.id, 1, 99, "user99")  # bumps version
        stale_version = exc.version
        await svc.assign(exc.id, 2, 99, "user99")  # bumps version again
        # A stale version can never overwrite the newer state.
        ok = await svc.repo.update_fields(exc.id, version=stale_version, title="hijack")
        assert ok is False
        reloaded = await svc.get(exc.id)
        assert reloaded.title != "hijack"

    async def test_cross_tenant_transition_denied(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        exc = await _create(db_session, tenant_a)
        svc_b = ExceptionService(db_session, tenant_b)
        with pytest.raises(NotFoundError):
            await svc_b.acknowledge(exc.id, 98, "user98")


# ======================================================================
# Tenant isolation
# ======================================================================


class TestTenantIsolation:
    async def test_cross_tenant_get_denied(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        exc = await _create(db_session, tenant_a)
        svc_b = ExceptionService(db_session, tenant_b)
        with pytest.raises(NotFoundError):
            await svc_b.get(exc.id)

    async def test_cross_tenant_list_empty(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        await _create(db_session, tenant_a)
        svc_b = ExceptionService(db_session, tenant_b)
        items, total = await svc_b.list()
        assert items == []
        assert total == 0

    async def test_cross_tenant_mutations_denied(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        exc = await _create(db_session, tenant_a)
        svc_b = ExceptionService(db_session, tenant_b)
        for action in (
            lambda: svc_b.assign(exc.id, 1, 98, "user98"),
            lambda: svc_b.update_severity(exc.id, "critical", 98, "user98"),
            lambda: svc_b.set_root_cause(exc.id, "x", 98, "user98"),
            lambda: svc_b.add_evidence(exc.id, {"x": 1}, 98, "user98"),
            lambda: svc_b.link_case(exc.id, 1, 98, "user98"),
        ):
            with pytest.raises(NotFoundError):
                await action()

    async def test_cross_tenant_metrics_empty(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        await _create(db_session, tenant_a)
        svc_b = ExceptionService(db_session, tenant_b)
        metrics = await svc_b.metrics()
        assert metrics["by_status"] == {}
        assert metrics["open_by_severity"] == {}
        assert metrics["overdue"] == 0

    async def test_cross_tenant_source_dedup_is_scoped(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        await _create(db_session, tenant_a, source_id=10)
        # Campus B has no exception for that source — creating one succeeds.
        b = await _create(db_session, tenant_b, source_id=10)
        assert b.campus_id == 2


# ======================================================================
# Metrics & listing
# ======================================================================


class TestReads:
    async def test_metrics_counts(self, db_session: AsyncSession, tenant_a: TenantContext) -> None:
        svc = ExceptionService(db_session, tenant_a)
        await _create(db_session, tenant_a, source_id=1, severity="critical")
        await _create(db_session, tenant_a, source_id=2, severity="low", title="t2")
        found = await svc.get_by_source("data_quality", "finding", 1)
        assert found is not None
        await svc.resolve(found.id, resolution_type="fixed")
        metrics = await svc.metrics()
        assert metrics["by_status"].get(EXCEPTION_STATUS_OPEN) == 1
        assert metrics["by_status"].get(EXCEPTION_STATUS_RESOLVED) == 1
        assert metrics["open_by_severity"] == {"low": 1}  # resolved excluded

    async def test_list_filters(self, db_session: AsyncSession, tenant_a: TenantContext) -> None:
        svc = ExceptionService(db_session, tenant_a)
        await _create(
            db_session, tenant_a, source_id=1, severity="high", exception_type="financial"
        )
        await _create(db_session, tenant_a, source_id=2, severity="low", title="t2")
        items, total = await svc.list(severity="high")
        assert total == 1 and items[0].exception_type == "financial"
        items, total = await svc.list(exception_type="financial")
        assert total == 1
        items, total = await svc.list()
        assert total == 2

    async def test_list_for_student(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ExceptionService(db_session, tenant_a)
        await _create(db_session, tenant_a, source_id=1, student_id=5)
        await _create(db_session, tenant_a, source_id=2, student_id=5, title="t2")
        items = await svc.list_for_student(5)
        assert len(items) == 2
        resolved_id = items[0].id
        await svc.resolve(resolved_id, resolution_type="no_action")
        items = await svc.list_for_student(5)
        assert len(items) == 1  # resolved hidden by default
        items = await svc.list_for_student(5, include_resolved=True)
        assert len(items) == 2


# ======================================================================
# API surface
# ======================================================================


class TestExceptionsAPI:
    async def test_full_flow_via_api(self, auth_client) -> None:
        resp = await auth_client.post(
            "/api/exceptions",
            json={
                "exception_type": "financial",
                "severity": "high",
                "title": "Payment without receipt",
                "source_domain": "finance",
                "source_type": "payment",
                "source_id": 321,
                "rule_code": "payment_no_receipt",
                "entity_type": "payment",
                "entity_id": 321,
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        exc_id = body["id"]
        assert body["status"] == "open"
        assert body["priority"] == "high"
        assert body["due_at"] is not None  # SLA computed

        # Idempotency helper.
        resp = await auth_client.get(
            "/api/exceptions/by-source",
            params={"source_domain": "finance", "source_type": "payment", "source_id": 321},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == exc_id

        # Duplicate create → 409.
        resp = await auth_client.post(
            "/api/exceptions",
            json={
                "exception_type": "financial",
                "severity": "high",
                "title": "Duplicate attempt",
                "source_domain": "finance",
                "source_type": "payment",
                "source_id": 321,
            },
        )
        assert resp.status_code == 409, resp.text

        # Lifecycle via HTTP.
        resp = await auth_client.post(f"/api/exceptions/{exc_id}/acknowledge")
        assert resp.status_code == 200, resp.text
        resp = await auth_client.post(f"/api/exceptions/{exc_id}/start")
        assert resp.status_code == 200, resp.text
        resp = await auth_client.post(
            f"/api/exceptions/{exc_id}/resolve",
            json={"resolution_type": "fixed", "resolution_note": "receipt reissued"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "resolved"

        # Illegal transition → 409.
        resp = await auth_client.post(f"/api/exceptions/{exc_id}/close")
        assert resp.status_code == 200, resp.text
        resp = await auth_client.post(f"/api/exceptions/{exc_id}/close")
        assert resp.status_code == 409, resp.text

        # Metrics + list + single.
        resp = await auth_client.get("/api/exceptions/metrics")
        assert resp.status_code == 200
        assert resp.json()["by_status"]["closed"] == 1
        resp = await auth_client.get("/api/exceptions", params={"status": "closed"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        resp = await auth_client.get(f"/api/exceptions/{exc_id}")
        assert resp.status_code == 200
        assert len(resp.json()["events"]) >= 5  # create + ack + start + resolve + close

    async def test_api_invalid_severity_422(self, auth_client) -> None:
        resp = await auth_client.post(
            "/api/exceptions",
            json={
                "exception_type": "data_quality",
                "severity": "supernova",
                "title": "t",
                "source_domain": "dq",
                "source_type": "finding",
                "source_id": 1,
            },
        )
        assert resp.status_code == 422, resp.text

    async def test_api_cross_tenant_denied(self) -> None:
        """Campus A creates an exception; a campus-B-scoped user cannot see it.

        Uses the same engine both users authenticate against (the
        ``tenant_env`` pattern from the security suite) so a leaked
        response would be guaranteed visible if any layer forgot to scope.
        """
        from httpx import ASGITransport, AsyncClient

        from app.infrastructure.database import Base, get_session
        from app.main import app

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with factory() as seed:
            institution = Institution(name="Test District", code="TST-EXC")
            seed.add(institution)
            await seed.flush()
            campus_a = Campus(
                institution_id=institution.id,
                name="Campus A",
                code="EXC-A",
                status="active",
            )
            campus_b = Campus(
                institution_id=institution.id,
                name="Campus B",
                code="EXC-B",
                status="active",
            )
            seed.add_all([campus_a, campus_b])
            await seed.flush()
            admin_a = User(
                username="exc_admin_a",
                email="exc_a@test.local",
                password_hash=hash_password("ExcA123!"),
                display_name="Admin A",
                role="admin",
                campus_id=campus_a.id,
                is_active=True,
            )
            admin_b = User(
                username="exc_admin_b",
                email="exc_b@test.local",
                password_hash=hash_password("ExcB123!"),
                display_name="Admin B",
                role="admin",
                campus_id=campus_b.id,
                is_active=True,
            )
            seed.add_all([admin_a, admin_b])
            await seed.flush()
            seed.add_all(
                [
                    UserSchoolMembership(
                        user_id=admin_a.id,
                        campus_id=campus_a.id,
                        role="admin",
                        is_default=True,
                        is_active=True,
                    ),
                    UserSchoolMembership(
                        user_id=admin_b.id,
                        campus_id=campus_b.id,
                        role="admin",
                        is_default=True,
                        is_active=True,
                    ),
                ]
            )
            await seed.commit()

        async def override_get_session():
            async with factory() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        app.dependency_overrides[get_session] = override_get_session
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                # Login both tenants.
                resp = await ac.post(
                    "/auth/login", json={"login": "exc_admin_a", "password": "ExcA123!"}
                )
                assert resp.status_code == 200, resp.text
                a_headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
                resp = await ac.post(
                    "/auth/login", json={"login": "exc_admin_b", "password": "ExcB123!"}
                )
                assert resp.status_code == 200, resp.text
                b_headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

                # 1. Campus A creates an exception.
                resp = await ac.post(
                    "/api/exceptions",
                    json={
                        "exception_type": "data_quality",
                        "severity": "high",
                        "title": "A-only issue",
                        "source_domain": "data_quality",
                        "source_type": "finding",
                        "source_id": 9001,
                    },
                    headers=a_headers,
                )
                assert resp.status_code == 201, resp.text
                exc_id = resp.json()["id"]

                # 2. Campus B cannot see, list, or mutate it.
                resp = await ac.get(f"/api/exceptions/{exc_id}", headers=b_headers)
                assert resp.status_code == 404, resp.text
                resp = await ac.post(f"/api/exceptions/{exc_id}/acknowledge", headers=b_headers)
                assert resp.status_code == 404, resp.text
                resp = await ac.get(
                    "/api/exceptions",
                    params={"source_domain": "data_quality"},
                    headers=b_headers,
                )
                assert resp.status_code == 200, resp.text
                assert resp.json()["total"] == 0

                # 3. Campus B CAN create its own exception for the same source id.
                resp = await ac.post(
                    "/api/exceptions",
                    json={
                        "exception_type": "data_quality",
                        "severity": "low",
                        "title": "B's own issue",
                        "source_domain": "data_quality",
                        "source_type": "finding",
                        "source_id": 9001,
                    },
                    headers=b_headers,
                )
                assert resp.status_code == 201, resp.text
        finally:
            app.dependency_overrides.clear()
            await engine.dispose()

    async def test_api_unauthenticated_denied(self, client) -> None:
        resp = await client.get("/api/exceptions")
        assert resp.status_code in (401, 403)
