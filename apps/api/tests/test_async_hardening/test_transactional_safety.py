"""Transactional safety of job execution (partial-completion adversarial).

A job that mutates state and then raises — a crash *after* partial work —
must not leave its partial writes behind.  The job-execution boundary must
be transactional (a SAVEPOINT): a retry starts clean and side effects are
applied at most once.

Regression: ``JobService.execute_job`` caught the exception but never
rolled back, so a failed run's partial rows stayed in the session and were
committed by the worker session at the end of the poll cycle — leaking a
half-finished side effect (for a financial job: an orphan ledger row) that
the retry would then duplicate.
"""

from __future__ import annotations

import datetime

from sqlalchemy import select

from app.domains.jobs.models import Job
from app.domains.jobs.registry import BaseJob, register_job
from app.domains.jobs.repository import JobRepository
from app.domains.jobs.schemas import JobCreate
from app.domains.jobs.service import JobService
from app.domains.school_finance.models import TransactionLog
from app.domains.school_finance.service import TransactionLogService
from app.multi_tenant.models import platform_context

NOW = datetime.datetime.now(datetime.timezone.utc)


@register_job
class PartiallyAppliedLedgerJob(BaseJob):
    """Writes a ledger row, then raises when ``should_fail`` is set.

    Simulates a worker crash between the business mutation and job
    completion — the exact window where a naive implementation leaks a
    partial financial side effect that a retry would duplicate.
    """

    job_type = "test.partial_ledger"

    async def run(self, job, session):  # noqa: ANN001
        ledger = TransactionLogService(session)
        await ledger.record(
            transaction_type="payment",
            student_id=job.params.get("student_id", 9001),
            amount=1000,
            campus_id=job.campus_id,
            idempotency_key=job.params.get("idem_key", "partial:1"),
            description="partial-completion test",
        )
        if job.params.get("should_fail"):
            raise RuntimeError("boom after partial ledger write")
        return {"ledgered": True}


class TestPartialCompletionRollback:
    async def test_failed_job_does_not_leak_partial_ledger_write(
        self, db_session
    ) -> None:
        """A job that journals a ledger entry and then crashes must not
        leave the entry behind — the retry starts clean and the ledger
        ends up with exactly one row, not two."""
        svc = JobService(db_session, platform_context())
        repo = JobRepository(db_session, platform_context())

        job = await svc.create_job(
            JobCreate(
                job_type="test.partial_ledger",
                max_retries=2,
                params={
                    "should_fail": True,
                    "student_id": 9001,
                    "idem_key": "partial:1",
                },
            )
        )
        job_id = job.id
        claimed = await repo.acquire_next()
        assert claimed is not None
        await svc.execute_job(claimed.id)
        await db_session.commit()

        # The failed execution's partial write must have been rolled back.
        logs = (
            await db_session.execute(
                select(TransactionLog).where(TransactionLog.student_id == 9001)
            )
        ).scalars().all()
        assert logs == []

        # The job itself is pending for retry (failure bookkeeping kept).
        row = (await db_session.execute(select(Job).where(Job.id == job_id))).scalar_one()
        assert row.status == "pending"
        assert row.retry_count == 1
        assert "boom after partial ledger write" in (row.last_error or "")

    async def test_retry_after_partial_failure_applies_side_effect_once(
        self, db_session
    ) -> None:
        """After a partial failure, the retry applies the ledger entry
        exactly once — no duplicate financial row."""
        svc = JobService(db_session, platform_context())
        repo = JobRepository(db_session, platform_context())

        job = await svc.create_job(
            JobCreate(
                job_type="test.partial_ledger",
                max_retries=2,
                params={
                    "should_fail": True,
                    "student_id": 9002,
                    "idem_key": "partial:2",
                },
            )
        )
        job_id = job.id
        claimed = await repo.acquire_next()
        assert claimed is not None
        await svc.execute_job(claimed.id)
        await db_session.commit()

        # Allow the retry now, and make it succeed.
        row = (await db_session.execute(select(Job).where(Job.id == job_id))).scalar_one()
        assert row.status == "pending"
        row.scheduled_at = NOW
        row.params = {"should_fail": False, "student_id": 9002, "idem_key": "partial:2"}
        await db_session.commit()

        claimed2 = await repo.acquire_next()
        assert claimed2 is not None
        await svc.execute_job(claimed2.id)
        await db_session.commit()

        row = (await db_session.execute(select(Job).where(Job.id == job_id))).scalar_one()
        assert row.status == "completed"
        assert row.result == {"ledgered": True}

        logs = (
            await db_session.execute(
                select(TransactionLog).where(TransactionLog.student_id == 9002)
            )
        ).scalars().all()
        assert len(logs) == 1

    async def test_successful_job_still_commits_its_writes(self, db_session) -> None:
        """The savepoint boundary must not swallow a successful job's
        legitimate writes."""
        svc = JobService(db_session, platform_context())
        repo = JobRepository(db_session, platform_context())

        job = await svc.create_job(
            JobCreate(
                job_type="test.partial_ledger",
                max_retries=2,
                params={
                    "should_fail": False,
                    "student_id": 9003,
                    "idem_key": "partial:3",
                },
            )
        )
        job_id = job.id
        claimed = await repo.acquire_next()
        assert claimed is not None
        await svc.execute_job(claimed.id)
        await db_session.commit()

        row = (await db_session.execute(select(Job).where(Job.id == job_id))).scalar_one()
        assert row.status == "completed"
        logs = (
            await db_session.execute(
                select(TransactionLog).where(TransactionLog.student_id == 9003)
            )
        ).scalars().all()
        assert len(logs) == 1
