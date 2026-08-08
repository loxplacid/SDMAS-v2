"""Worker-side periodic scheduler.

The scheduler is the *only* component that knows about calendar time.  It
runs **inside the worker process only** (never the API), and on each cycle
enqueues the periodic maintenance jobs into the durable job queue with
deterministic identity keys scoped to the current cycle::

    billing.period_end:{YYYY-MM-DD}
    billing.expire_past_due:{YYYY-MM-DD}
    communications.scheduled:{YYYY-MM-DD-HH-MM (5-min bucket)}

Because ``Job.identity_key`` is UNIQUE and ``JobService.create_job`` is
idempotent, the enqueue is safe under:

* **multiple scheduler instances** — two workers both enqueue the same key;
  the unique constraint collapses them into one row;
* **worker restart mid-cycle** — re-enqueueing an already-created key
  returns the existing job instead of duplicating it;
* **cycle rollover** — the next day / 5-minute window naturally gets a new
  key, so a fresh job is created while the previous cycle's job stays
  completed in the audit trail.

Execution itself is delegated to the normal job pipeline (atomic claim,
retry, dead-letter, tenant restoration, WORKER actor) — the scheduler does
not run any business logic and never bypasses job safety.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Any, Callable

from app.domains.jobs.models import Job
from app.domains.jobs.schemas import JobCreate
from app.domains.jobs.service import JobService
from app.infrastructure.database import async_session_factory
from app.multi_tenant.models import platform_context

logger = logging.getLogger(__name__)


#: ``() -> datetime`` clock used for cycle-key generation.  A module-level
#: indirection keeps production on wall-clock time while letting tests
#: inject a fixed clock for deterministic cycle keys.
def _default_clock() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


#: Type of the async session factory callable used by the scheduler loop.
SessionFactory = Callable[[], Any]


def _default_session_factory() -> SessionFactory:
    return async_session_factory


def _daily_key(prefix: str, now: datetime.datetime) -> str:
    return f"{prefix}:{now:%Y-%m-%d}"


def _five_min_bucket_key(prefix: str, now: datetime.datetime) -> str:
    """Bucket the current instant to a 5-minute window for the identity key."""
    bucket = now.replace(minute=(now.minute // 5) * 5, second=0, microsecond=0)
    return f"{prefix}:{bucket:%Y-%m-%d-%H-%M}"


#: (job_type, identity key factory, max_retries, priority)
PeriodicJobSpec = tuple[str, Callable[[datetime.datetime], str], int, int]

_PERIODIC_JOBS: tuple[PeriodicJobSpec, ...] = (
    ("billing.period_end", lambda now: _daily_key("billing.period_end", now), 2, 10),
    ("billing.expire_past_due", lambda now: _daily_key("billing.expire_past_due", now), 2, 10),
    ("cases.escalation", lambda now: _five_min_bucket_key("cases.escalation", now), 2, 20),
    (
        "communications.scheduled",
        lambda now: _five_min_bucket_key("communications.scheduled", now),
        2,
        20,
    ),
)


class Scheduler:
    """Periodically enqueues the periodic maintenance jobs (worker only)."""

    def __init__(
        self,
        poll_interval: float = 60.0,
        session_factory: SessionFactory | None = None,
        clock: Callable[[], datetime.datetime] | None = None,
    ) -> None:
        self._poll_interval = poll_interval
        self._session_factory: SessionFactory = session_factory or async_session_factory
        self._clock = clock or _default_clock
        self._task: asyncio.Task[None] | None = None
        self._shutdown_event = asyncio.Event()

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        self._shutdown_event.clear()
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Scheduler started (poll=%ss)", self._poll_interval)

    async def stop(self) -> None:
        task = self._task
        if task is None or task.done():
            return
        logger.info("Scheduler stopping…")
        self._shutdown_event.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("Scheduler stopped")

    async def _run_loop(self) -> None:
        while not self._shutdown_event.is_set():
            try:
                await self._enqueue_cycle()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Scheduler cycle failed")
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=self._poll_interval)
            except asyncio.TimeoutError:
                pass

    async def _enqueue_cycle(self) -> None:
        """Enqueue every periodic job for the current cycle (idempotent)."""
        now = self._clock()
        async with self._session_factory() as session:
            # Scheduler cycles are platform-level: they enqueue jobs for
            # every campus, so an explicit platform context is required
            # (tenant=None would fail closed on tenant-owned Job rows).
            service = JobService(session, platform_context())
            created: list[Job] = []
            for job_type, key_factory, max_retries, priority in _PERIODIC_JOBS:
                identity_key = str(key_factory(now))
                job = await service.create_job(
                    JobCreate(
                        job_type=job_type,
                        identity_key=identity_key,
                        max_retries=max_retries,
                        priority=priority,
                    )
                )
                created.append(job)
                logger.debug(
                    "Scheduler ensured job %d [%s] key=%s",
                    job.id,
                    job_type,
                    identity_key,
                )
            await session.commit()
            # Only report jobs that were created fresh this cycle.
            fresh = [j for j in created if j.status == "pending"]
            if fresh:
                logger.info(
                    "Scheduler enqueued %d new periodic job(s): %s",
                    len(fresh),
                    ", ".join(f"{j.job_type} (id={j.id})" for j in fresh),
                )
