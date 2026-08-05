"""Tests for the background job worker, the atomic job claim and the
stale-job reaper.

Covers:
  - ``JobRepository.acquire_next`` claims exactly one pending job and
    flips it to ``running`` (no double-claim in a single call).
  - The claim respects priority ordering and scheduled_at.
  - ``JobRepository.reclaim_stale_running`` requeues jobs stuck in
    ``running`` past a TTL and dead-letters those that exhausted retries.
  - The worker module exposes a runnable ``main`` entrypoint (the
    Dockerfile.worker CMD ``python -m app.domains.jobs.worker``).
"""

from __future__ import annotations

import datetime
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.jobs.models import Job
from app.domains.jobs.repository import JobRepository
from app.multi_tenant.models import platform_context

NOW = datetime.datetime.now(datetime.timezone.utc)


async def _make_job(
    session: AsyncSession,
    *,
    job_type: str = "test.job",
    status: str = "pending",
    priority: int = 100,
    scheduled_at: datetime.datetime | None = None,
    started_at: datetime.datetime | None = None,
    retry_count: int = 0,
    max_retries: int = 3,
    updated_at: datetime.datetime | None = None,
) -> Job:
    job = Job(
        job_type=job_type,
        status=status,
        priority=priority,
        scheduled_at=scheduled_at,
        started_at=started_at,
        retry_count=retry_count,
        max_retries=max_retries,
        created_at=NOW,
        updated_at=updated_at or NOW,
    )
    session.add(job)
    await session.flush()
    return job


# ---------------------------------------------------------------------------
# Atomic claim
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_acquire_next_claims_single_pending_job(db_session: AsyncSession):
    await _make_job(db_session)
    repo = JobRepository(db_session, platform_context())

    claimed = await repo.acquire_next()

    assert claimed is not None
    assert claimed.status == "running"
    assert claimed.started_at is not None


@pytest.mark.asyncio
async def test_acquire_next_does_not_reclaim_same_job(db_session: AsyncSession):
    """A second claim must not return the same (already running) job."""
    await _make_job(db_session)
    repo = JobRepository(db_session, platform_context())

    first = await repo.acquire_next()
    assert first is not None

    # Same session, same query — the row is already running, so nothing
    # pending remains. (In a multi-worker deployment the UPDATE…RETURNING
    # statement is race-safe even across processes.)
    second = await repo.acquire_next()
    assert second is None


@pytest.mark.asyncio
async def test_acquire_next_respects_priority_order(db_session: AsyncSession):
    await _make_job(db_session, priority=100)
    await _make_job(db_session, priority=50)
    repo = JobRepository(db_session, platform_context())

    claimed = await repo.acquire_next()

    # The job with the lowest priority value is claimed first.
    assert claimed is not None
    assert claimed.priority == 50


@pytest.mark.asyncio
async def test_acquire_next_skips_future_scheduled_jobs(db_session: AsyncSession):
    future = NOW + datetime.timedelta(hours=1)
    await _make_job(db_session, scheduled_at=future)
    repo = JobRepository(db_session, platform_context())

    assert await repo.acquire_next() is None


@pytest.mark.asyncio
async def test_acquire_next_filters_by_job_type(db_session: AsyncSession):
    await _make_job(db_session, job_type="other.job")
    repo = JobRepository(db_session, platform_context())

    assert await repo.acquire_next(job_types=["wanted.job"]) is None
    assert await repo.acquire_next(job_types=["other.job"]) is not None


@pytest.mark.asyncio
async def test_acquire_next_skips_dead_lettered_jobs(db_session: AsyncSession):
    await _make_job(db_session, status="dead_letter")
    repo = JobRepository(db_session, platform_context())

    assert await repo.acquire_next() is None


# ---------------------------------------------------------------------------
# Stale-job reaper
# ---------------------------------------------------------------------------


STALE = NOW - datetime.timedelta(minutes=45)
FRESH = NOW - datetime.timedelta(minutes=1)


@pytest.mark.asyncio
async def test_reclaim_requeues_stale_running_job(db_session: AsyncSession):
    job = await _make_job(db_session, status="running", started_at=STALE, updated_at=STALE)
    repo = JobRepository(db_session, platform_context())

    requeued, dead_lettered = await repo.reclaim_stale_running(
        NOW - datetime.timedelta(minutes=30)
    )

    assert requeued == 1
    assert dead_lettered == 0

    job_id = job.id  # capture before expire_all() (avoids async lazy-load)
    db_session.expire_all()
    fresh = (await db_session.execute(select(Job).where(Job.id == job_id))).scalar_one()
    assert fresh.status == "pending"
    assert fresh.started_at is None
    assert fresh.scheduled_at is not None
    assert fresh.retry_count == 1
    assert "stopped before completion" in (fresh.last_error or "")


@pytest.mark.asyncio
async def test_reclaim_dead_letters_job_past_max_retries(db_session: AsyncSession):
    job = await _make_job(
        db_session,
        status="running",
        started_at=STALE,
        updated_at=STALE,
        retry_count=3,
        max_retries=3,
    )
    repo = JobRepository(db_session, platform_context())

    requeued, dead_lettered = await repo.reclaim_stale_running(
        NOW - datetime.timedelta(minutes=30)
    )

    assert requeued == 0
    assert dead_lettered == 1

    job_id = job.id  # capture before expire_all() (avoids async lazy-load)
    db_session.expire_all()
    fresh = (await db_session.execute(select(Job).where(Job.id == job_id))).scalar_one()
    assert fresh.status == "dead_letter"
    assert fresh.completed_at is not None
    assert "max retries" in (fresh.last_error or "")


@pytest.mark.asyncio
async def test_reclaim_skips_fresh_running_job(db_session: AsyncSession):
    job = await _make_job(db_session, status="running", started_at=FRESH, updated_at=FRESH)
    repo = JobRepository(db_session, platform_context())

    requeued, dead_lettered = await repo.reclaim_stale_running(
        NOW - datetime.timedelta(minutes=30)
    )

    assert requeued == 0
    assert dead_lettered == 0

    job_id = job.id  # capture before expire_all() (avoids async lazy-load)
    db_session.expire_all()
    fresh = (await db_session.execute(select(Job).where(Job.id == job_id))).scalar_one()
    assert fresh.status == "running"


@pytest.mark.asyncio
async def test_reclaim_skips_pending_and_completed_jobs(db_session: AsyncSession):
    await _make_job(db_session, status="pending", updated_at=STALE)
    await _make_job(db_session, status="completed", updated_at=STALE)
    repo = JobRepository(db_session, platform_context())

    requeued, dead_lettered = await repo.reclaim_stale_running(
        NOW - datetime.timedelta(minutes=30)
    )

    assert requeued == 0
    assert dead_lettered == 0


@pytest.mark.asyncio
async def test_reclaim_empty_table(db_session: AsyncSession):
    repo = JobRepository(db_session, platform_context())
    assert await repo.reclaim_stale_running(
        NOW - datetime.timedelta(minutes=30)
    ) == (0, 0)


@pytest.mark.asyncio
async def test_worker_reap_pass_reclaims_stale_jobs(db_session: AsyncSession, monkeypatch):
    """``JobWorker._maybe_reap`` reclaims stale running jobs end-to-end."""
    import app.domains.jobs.worker as worker_module

    job = await _make_job(db_session, status="running", started_at=STALE, updated_at=STALE)

    @asynccontextmanager
    async def _fake_worker_session():
        yield db_session

    monkeypatch.setattr(worker_module, "_worker_session", _fake_worker_session)

    worker = worker_module.JobWorker(reap_interval=0.0, stale_after=60)
    await worker._maybe_reap()

    job_id = job.id  # capture before expire_all() (avoids async lazy-load)
    db_session.expire_all()
    fresh = (await db_session.execute(select(Job).where(Job.id == job_id))).scalar_one()
    assert fresh.status == "pending"


@pytest.mark.asyncio
async def test_worker_reap_pass_respects_cadence(db_session: AsyncSession, monkeypatch):
    """``_maybe_reap`` skips when called within ``reap_interval``.

    We spy on the worker session (a side effect that only happens *past*
    the gate) instead of counting invocations, and control the gate state
    explicitly so the test is deterministic regardless of host uptime.
    """
    import time

    import app.domains.jobs.worker as worker_module

    await _make_job(db_session, status="running", started_at=STALE, updated_at=STALE)
    opens = {"count": 0}

    @asynccontextmanager
    async def _spy_session():
        opens["count"] += 1
        yield db_session

    monkeypatch.setattr(worker_module, "_worker_session", _spy_session)

    worker = worker_module.JobWorker(reap_interval=60, stale_after=60)

    # Force the gate closed deterministically → the pass must be skipped
    # entirely, so no worker session is ever opened.
    worker._last_reap_at = time.monotonic()
    await worker._maybe_reap()
    assert opens["count"] == 0

    # Reopen the gate → the pass runs and opens the session.  Using an
    # offset older than reap_interval (rather than 0.0) keeps this
    # deterministic even on hosts booted less than 60s ago.
    worker._last_reap_at = time.monotonic() - 120
    await worker._maybe_reap()
    assert opens["count"] == 1


# ---------------------------------------------------------------------------
# Worker entrypoint
# ---------------------------------------------------------------------------


def test_worker_module_exposes_main_entrypoint():
    """``python -m app.domains.jobs.worker`` must actually run something.

    Regression guard: the module previously had no ``__main__`` block, so
    the ``Dockerfile.worker`` CMD exited immediately (crash-looping the
    dedicated worker container in production).
    """
    import app.domains.jobs.worker as worker_module

    assert callable(getattr(worker_module, "main", None))


def test_worker_main_constructs_worker_and_starts_it(monkeypatch):
    """``main()`` must start a JobWorker (and keep running until stopped)."""
    import app.domains.jobs.worker as worker_module

    started = {"called": False}

    class _FakeWorker:
        def __init__(self, *, poll_interval: float, reap_interval: float, stale_after: float):
            self.poll_interval = poll_interval
            self.reap_interval = reap_interval
            self.stale_after = stale_after

        def start(self) -> None:
            started["called"] = True

        async def stop(self) -> None:
            started["stopped"] = True

    monkeypatch.setattr(worker_module, "JobWorker", _FakeWorker)

    # Simulate the shutdown-signal path: make signal registration a no-op
    # (the real signal.signal call is harmless in tests but noisy) and make
    # the internal stop Event resolve as soon as the worker has started so
    # main() returns promptly instead of blocking forever.
    import asyncio
    import signal

    monkeypatch.setattr(signal, "signal", lambda *a, **k: None)

    original_wait = asyncio.Event.wait

    async def _immediate_wait(self, *a, **k):
        if started.get("called"):
            return True
        return await original_wait(self, *a, **k)

    monkeypatch.setattr(asyncio.Event, "wait", _immediate_wait)

    worker_module.main()

    assert started["called"] is True
    assert started.get("stopped") is True
