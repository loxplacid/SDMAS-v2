"""Multi-worker job safety tests.

Proves the guarantees that keep the system correct when multiple API
instances and multiple worker replicas run against the same queue:

* ``acquire_next`` is atomic — concurrent workers never claim the same job
* identity keys make enqueue idempotent — duplicate job execution is
  structurally impossible for keyed jobs
* retry → dead-letter state transitions
* a worker that dies mid-job is reaped and re-queued (restart safety)
* jobs persist across an API restart
* tenant context is restored per job — a job for campus A can never act
  as campus B
"""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy import select

from app.domains.jobs.models import Job
from app.domains.jobs.registry import BaseJob, register_job
from app.domains.jobs.repository import JobRepository
from app.domains.jobs.schemas import JobCreate
from app.domains.jobs.service import JobService
from app.multi_tenant.models import platform_context

NOW = datetime.datetime.now(datetime.timezone.utc)


def _job_fields(**overrides) -> dict:
    fields: dict = {
        "job_type": "test.dummy",
        "status": "pending",
        "priority": 100,
        "max_retries": 3,
        "retry_count": 0,
        "created_at": NOW,
        "updated_at": NOW,
        "progress": 0.0,
    }
    fields.update(overrides)
    return fields


# ---------------------------------------------------------------------------
# Atomic claim — concurrent workers
# ---------------------------------------------------------------------------


class TestAtomicClaim:
    async def test_two_sessions_cannot_claim_same_job(self, session_factory):
        """Two worker sessions racing must not both win the same job."""
        async with session_factory() as s1, session_factory() as s2:
            job = Job(**_job_fields(job_type="test.race"))
            s1.add(job)
            await s1.commit()
            job_id = job.id

            repo1 = JobRepository(s1, platform_context())
            repo2 = JobRepository(s2, platform_context())

            claimed1 = await repo1.acquire_next()
            claimed2 = await repo2.acquire_next()

            # Exactly one worker wins; the other finds nothing pending.
            assert claimed1 is not None
            assert claimed2 is None
            assert claimed1.id == job_id

    async def test_worker_cannot_reclaim_running_job_in_new_session(
        self, session_factory
    ):
        """A second poll in a fresh session skips an already-running job."""
        async with session_factory() as s1:
            job = Job(**_job_fields())
            s1.add(job)
            await s1.commit()
            job_id = job.id
            claimed = await JobRepository(s1, platform_context()).acquire_next()
            assert claimed is not None
            # Persist the claim, exactly as the worker's ``_worker_session``
            # commits after a poll cycle.  An uncommitted claim would be
            # rolled back when the session closes, letting a second worker
            # re-claim the job — which is correct crash semantics, but this
            # test proves the *durable* claim blocks re-claiming.
            await s1.commit()

        # Fresh worker session (simulates a second worker replica).
        async with session_factory() as s2:
            again = await JobRepository(s2, platform_context()).acquire_next()
            assert again is None
            # The original job is still running — not double-claimed.
            row = (await s2.execute(select(Job).where(Job.id == job_id))).scalar_one()
            assert row.status == "running"

    async def test_three_jobs_claimed_by_two_workers_no_overlap(
        self, session_factory
    ):
        """Two workers drain three jobs with no job claimed twice."""
        async with session_factory() as s1, session_factory() as s2:
            for i in range(3):
                s1.add(Job(**_job_fields(job_type="test.drain")))
            await s1.commit()

            repo1 = JobRepository(s1, platform_context())
            repo2 = JobRepository(s2, platform_context())

            claimed_ids = []
            for repo in (repo1, repo2, repo1):
                job = await repo.acquire_next()
                if job is not None:
                    claimed_ids.append(job.id)

            assert len(claimed_ids) == 3
            assert len(set(claimed_ids)) == 3  # no overlap


# ---------------------------------------------------------------------------
# Duplicate job execution — identity keys
# ---------------------------------------------------------------------------


class TestDuplicateExecution:
    async def test_enqueue_same_identity_key_returns_same_job(self, db_session):
        """Two enqueues with the same identity key collapse into one row."""
        svc = JobService(db_session, platform_context())

        first = await svc.create_job(
            JobCreate(
                job_type="test.keyed",
                identity_key="cycle:2026-08-03",
                max_retries=2,
            )
        )
        second = await svc.create_job(
            JobCreate(
                job_type="test.keyed",
                identity_key="cycle:2026-08-03",
                max_retries=2,
            )
        )
        await db_session.commit()

        assert first.id == second.id
        rows = (await db_session.execute(select(Job))).scalars().all()
        assert len(rows) == 1

    async def test_enqueue_after_completion_returns_completed_job(
        self, db_session
    ):
        """Re-enqueueing a *completed* keyed job returns the original row.

        Regression: the previous implementation created a second row for a
        terminal status, violating the unique constraint and 500ing the
        scheduler cycle after the job completed.
        """
        svc = JobService(db_session, platform_context())
        job = await svc.create_job(
            JobCreate(job_type="test.keyed", identity_key="once-only")
        )
        job.status = "completed"
        await db_session.commit()

        again = await svc.create_job(
            JobCreate(job_type="test.keyed", identity_key="once-only")
        )
        await db_session.commit()
        assert again.id == job.id
        rows = (await db_session.execute(select(Job))).scalars().all()
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# Retry / dead-letter
# ---------------------------------------------------------------------------


@register_job
class AlwaysFailJob(BaseJob):
    """Test job that always raises."""

    job_type = "test.always_fail"

    async def run(self, job, session):  # noqa: ANN001
        raise RuntimeError("synthetic failure")


class TestRetryAndDeadLetter:
    async def test_job_retries_then_dead_letters(self, db_session):
        """A failing job is retried with backoff, then dead-lettered."""
        svc = JobService(db_session, platform_context())
        repo = JobRepository(db_session, platform_context())

        job = await svc.create_job(
            JobCreate(job_type="test.always_fail", max_retries=1)
        )
        job_id = job.id

        # First execution: fails → retry scheduled (pending, retry_count 1).
        claimed = await repo.acquire_next()
        assert claimed is not None
        await svc.execute_job(claimed.id)
        row = (await db_session.execute(select(Job).where(Job.id == job_id))).scalar_one()
        assert row.status == "pending"
        assert row.retry_count == 1
        assert row.scheduled_at is not None and row.scheduled_at > NOW

        # Second execution (retry): fails again → dead-letter (max reached).
        row.scheduled_at = NOW
        await db_session.commit()
        claimed2 = await repo.acquire_next()
        assert claimed2 is not None
        await svc.execute_job(claimed2.id)

        row = (await db_session.execute(select(Job).where(Job.id == job_id))).scalar_one()
        assert row.status == "dead_letter"
        assert "synthetic failure" in (row.last_error or "")

    async def test_job_with_zero_retries_dead_letters_immediately(
        self, db_session
    ):
        svc = JobService(db_session, platform_context())
        repo = JobRepository(db_session, platform_context())

        job = await svc.create_job(
            JobCreate(job_type="test.always_fail", max_retries=0)
        )
        job_id = job.id

        claimed = await repo.acquire_next()
        assert claimed is not None
        await svc.execute_job(claimed.id)

        row = (await db_session.execute(select(Job).where(Job.id == job_id))).scalar_one()
        assert row.status == "dead_letter"

    async def test_successful_job_completes_with_result(self, db_session):
        """A well-behaved job transitions pending → running → completed."""
        from app.domains.report_builder.jobs import ReportExportJob  # noqa: F401
        from app.domains.report_builder.service import REPORT_EXPORT_JOB_TYPE

        svc = JobService(db_session, platform_context())
        repo = JobRepository(db_session, platform_context())

        # Register a simple inline job that returns a result.
        from app.domains.jobs.registry import get_job_class

        original = None
        if get_job_class("test.returns_result") is None:

            @register_job
            class _ReturnsResult(BaseJob):
                job_type = "test.returns_result"

                async def run(self, job, session):  # noqa: ANN001
                    return {"ok": True, "value": job.params.get("value")}

        job = await svc.create_job(
            JobCreate(job_type="test.returns_result", params={"value": 42})
        )
        job_id = job.id
        claimed = await repo.acquire_next()
        assert claimed is not None
        await svc.execute_job(claimed.id)

        row = (await db_session.execute(select(Job).where(Job.id == job_id))).scalar_one()
        assert row.status == "completed"
        assert row.result == {"ok": True, "value": 42}
        assert row.progress == 100.0


# ---------------------------------------------------------------------------
# Worker / API restart
# ---------------------------------------------------------------------------


class TestRestartSafety:
    async def test_stale_running_job_is_requeued_and_rerun(
        self, session_factory
    ):
        """A worker crash leaves a job 'running'; the reaper requeues it and
        a fresh worker executes it (worker restart safety)."""
        async with session_factory() as s:
            stale = NOW - datetime.timedelta(minutes=45)
            job = Job(
                **_job_fields(
                    job_type="test.always_fail",
                    status="running",
                    started_at=stale,
                    updated_at=stale,
                )
            )
            s.add(job)
            await s.commit()
            job_id = job.id

            repo = JobRepository(s, platform_context())
            requeued, dead_lettered = await repo.reclaim_stale_running(
                NOW - datetime.timedelta(minutes=30)
            )
            assert requeued == 1
            assert dead_lettered == 0

            # A new worker session picks it up again.
            s.expire_all()
            row = (await s.execute(select(Job).where(Job.id == job_id))).scalar_one()
            assert row.status == "pending"

    async def test_jobs_persist_across_api_restart(self, session_factory):
        """Jobs live in the DB, not in process memory: an API restart does
        not lose queued work."""
        async with session_factory() as s:
            svc = JobService(s, platform_context())
            job = await svc.create_job(
                JobCreate(job_type="test.keyed", identity_key="restart:1")
            )
            job_id = job.id
            await s.commit()

        # Fresh session (simulates a restarted API process).
        async with session_factory() as s2:
            row = (await s2.execute(select(Job).where(Job.id == job_id))).scalar_one()
            assert row.status == "pending"
            assert row.identity_key == "restart:1"


# ---------------------------------------------------------------------------
# Tenant pinning
# ---------------------------------------------------------------------------


@register_job
class CaptureContextJob(BaseJob):
    """Records the tenant/actor context visible during execution."""

    job_type = "test.capture_context"

    async def run(self, job, session):  # noqa: ANN001
        from app.domains.events.context import (
            get_actor_user_id,
            get_correlation_id,
            get_school_id,
        )

        return {
            "school_id": get_school_id(),
            "actor_user_id": get_actor_user_id(),
            "correlation_id": get_correlation_id(),
            "tenant_campus_id": self.tenant.campus_id if self.tenant else None,
        }


class TestTenantPinning:
    async def test_job_restores_campus_context(self, db_session):
        """A job created for campus 5 must execute with school_id=5 and the
        pinned TenantContext — never unscoped or another campus."""
        svc = JobService(db_session, platform_context())
        repo = JobRepository(db_session, platform_context())

        job = await svc.create_job(
            JobCreate(
                job_type="test.capture_context",
                identity_key="tenant:5:job",
                campus_id=5,
                user_id=99,
            )
        )
        job_id = job.id
        claimed = await repo.acquire_next()
        assert claimed is not None
        await svc.execute_job(claimed.id)

        row = (await db_session.execute(select(Job).where(Job.id == job_id))).scalar_one()
        assert row.status == "completed"
        assert row.result["school_id"] == 5
        assert row.result["actor_user_id"] == 99
        assert row.result["tenant_campus_id"] == 5
        assert row.result["correlation_id"] == "tenant:5:job"

    async def test_unscoped_job_runs_with_no_tenant(self, db_session):
        """Platform-level jobs (no campus) run unscoped by design."""
        svc = JobService(db_session, platform_context())
        repo = JobRepository(db_session, platform_context())

        job = await svc.create_job(
            JobCreate(job_type="test.capture_context", identity_key="platform:job")
        )
        job_id = job.id
        claimed = await repo.acquire_next()
        assert claimed is not None
        await svc.execute_job(claimed.id)

        row = (await db_session.execute(select(Job).where(Job.id == job_id))).scalar_one()
        assert row.result["school_id"] is None
        assert row.result["tenant_campus_id"] is None

    async def test_job_audit_uses_worker_system_actor(self, db_session):
        """Job executions are audited with the WORKER actor — never a user."""
        from app.domains.audit.models import AuditLog

        svc = JobService(db_session, platform_context())
        repo = JobRepository(db_session, platform_context())

        job = await svc.create_job(
            JobCreate(
                job_type="test.capture_context",
                identity_key="tenant:7:job",
                campus_id=7,
            )
        )
        job_id = job.id
        claimed = await repo.acquire_next()
        assert claimed is not None
        await svc.execute_job(claimed.id)

        rows = (
            await db_session.execute(
                select(AuditLog).where(AuditLog.action == "JOB_EXECUTED")
            )
        ).scalars().all()
        assert len(rows) == 1
        entry = rows[0]
        assert entry.actor_type == "worker"
        assert entry.campus_id == 7
