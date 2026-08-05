from __future__ import annotations

import asyncio
import datetime
import logging
import os
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.jobs.repository import JobRepository
from app.domains.jobs.service import JobService
from app.multi_tenant.models import platform_context
from app.infrastructure.database import async_session_factory

logger = logging.getLogger(__name__)

# Default reaper cadence: reclaim jobs stuck in ``running`` for longer than
# 30 minutes, checked every 60 seconds.  Both are overridable per process
# via env vars (see ``main``) or constructor kwargs.
_DEFAULT_REAP_INTERVAL_S = 60.0
_DEFAULT_STALE_AFTER_S = 30 * 60.0


def main() -> None:
    """Entrypoint for the standalone worker process.

    Used by ``Dockerfile.worker`` (``python -m app.domains.jobs.worker``)
    and by local dev invocations.  This process is the **only** consumer of
    the job queue and the durable event outbox:

    1. ``JobWorker`` polls the database for pending jobs and periodically
       reclaims stale ``running`` jobs (reaper).
    2. ``OutboxWorker`` delivers durable integration events from the outbox
       with retry / dead-letter semantics.
    3. ``Scheduler`` enqueues the periodic maintenance jobs (billing
       period-end, past-due expiration, scheduled-message dispatch) with
       cycle-scoped identity keys so they run exactly once per cycle.

    The API process never starts a worker (see ``app.main``), so scaling API
    replicas never creates competing workers against the same queue.  All
    loops claim work with atomic ``UPDATE ... RETURNING`` statements, so
    multiple worker replicas are safe too.
    """
    import signal

    def _env_float(name: str, default: float) -> float:
        try:
            return float(os.environ.get(name, default))
        except (TypeError, ValueError):
            logger.warning("Invalid %s, falling back to %s", name, default)
            return default

    def _env_int(name: str, default: int) -> int:
        try:
            return int(os.environ.get(name, default))
        except (TypeError, ValueError):
            logger.warning("Invalid %s, falling back to %s", name, default)
            return default

    poll_interval = _env_float("WORKER_POLL_INTERVAL", 5.0)
    reap_interval = _env_float("WORKER_REAP_INTERVAL", _DEFAULT_REAP_INTERVAL_S)
    stale_after = _env_float("WORKER_STALE_AFTER", _DEFAULT_STALE_AFTER_S)

    # Load every job implementation so the registry resolves all job types.
    from app.domains.jobs.loader import load_all_jobs
    load_all_jobs()

    # Register durable outbox handlers (delivery happens only here).
    from app.domains.events.outbox import OutboxWorker, outbox_dispatcher
    from app.domains.events.outbox_handlers import register_outbox_handlers
    register_outbox_handlers(outbox_dispatcher)

    outbox_poll = _env_float("OUTBOX_POLL_INTERVAL", 2.0)
    outbox_batch = _env_int("OUTBOX_BATCH_SIZE", 10)
    outbox_max_attempts = _env_int("OUTBOX_MAX_ATTEMPTS", 10)
    outbox_reap = _env_float("OUTBOX_REAP_INTERVAL", 60.0)
    outbox_stale = _env_float("OUTBOX_STALE_AFTER", 600.0)

    worker = JobWorker(
        poll_interval=poll_interval,
        reap_interval=reap_interval,
        stale_after=stale_after,
    )

    # Scheduler enqueues the periodic maintenance jobs.  Disable via
    # ``SCHEDULER_ENABLED=false`` if a deployment wants to run it in its
    # own process instead (enqueue is idempotent, so running multiple is
    # safe, but a single scheduler is the default posture).
    scheduler_enabled = os.environ.get("SCHEDULER_ENABLED", "true").lower() not in (
        "0", "false", "no",
    )
    scheduler = None
    if scheduler_enabled:
        from app.domains.jobs.scheduler import Scheduler
        scheduler = Scheduler(poll_interval=_env_float("SCHEDULER_POLL_INTERVAL", 60.0))

    outbox_worker = OutboxWorker(
        poll_interval=outbox_poll,
        batch_size=outbox_batch,
        max_attempts=outbox_max_attempts,
        reap_interval=outbox_reap,
        stale_after=outbox_stale,
    )

    async def _run() -> None:
        # start() schedules the poll tasks with asyncio.create_task, so they
        # must run while the event loop is active.
        worker.start()
        if scheduler is not None:
            scheduler.start()
        outbox_worker.start()
        logger.info(
            "Worker entrypoint started (poll=%ss reap=%ss stale=%ss; "
            "scheduler=%s; outbox poll=%ss batch=%d max_attempts=%d)",
            poll_interval, reap_interval, stale_after,
            "enabled" if scheduler is not None else "disabled",
            outbox_poll, outbox_batch, outbox_max_attempts,
        )

        stop = asyncio.Event()

        def _request_shutdown(signum, _frame) -> None:
            logger.info("Received signal %s — requesting shutdown", signum)
            stop.set()

        # signal.signal works on both Unix and Windows (unlike
        # loop.add_signal_handler, which is Unix-only).
        signal.signal(signal.SIGTERM, _request_shutdown)
        signal.signal(signal.SIGINT, _request_shutdown)

        try:
            await stop.wait()
        finally:
            # Cancel the poll tasks and let the workers clean up.
            await outbox_worker.stop()
            if scheduler is not None:
                await scheduler.stop()
            await worker.stop()
            logger.info("Worker entrypoint exited cleanly")

    asyncio.run(_run())


if __name__ == "__main__":
    main()


class JobWorker:
    """Background worker that polls the database for pending jobs and
    periodically reclaims jobs stuck in ``running`` (stale-job reaper).

    Designed for single-process deployments. For horizontal scaling,
    replace the ``acquire_next`` logic with a distributed lock or
    switch to Redis/Postgres advisory locks. The reaper itself is
    race-safe across multiple workers (see ``reclaim_stale_running``),
    so every worker may run it on its own cadence.

    Long-running jobs must heartbeat via ``update_progress`` or finish
    within ``stale_after`` — see the reaper's heartbeat contract.
    """

    def __init__(
        self,
        *,
        poll_interval: float = 5.0,
        batch_size: int = 1,
        job_types: list[str] | None = None,
        reap_interval: float | None = None,
        stale_after: float | None = None,
    ) -> None:
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._job_types = job_types
        self._reap_interval = (
            reap_interval if reap_interval is not None else _DEFAULT_REAP_INTERVAL_S
        )
        self._stale_after = stale_after if stale_after is not None else _DEFAULT_STALE_AFTER_S
        self._task: asyncio.Task[None] | None = None
        self._shutdown_event = asyncio.Event()
        self._last_reap_at = 0.0

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if self.is_running:
            logger.warning("JobWorker is already running")
            return
        self._shutdown_event.clear()
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "JobWorker started (poll=%ss batch=%d types=%s reap=%ss stale=%ss)",
            self._poll_interval, self._batch_size, self._job_types or "all",
            self._reap_interval, self._stale_after,
        )

    async def stop(self) -> None:
        if not self.is_running:
            return
        logger.info("JobWorker stopping…")
        self._shutdown_event.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("JobWorker stopped")

    async def _run_loop(self) -> None:
        while not self._shutdown_event.is_set():
            try:
                await self._poll()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("JobWorker poll cycle failed")
            await self._maybe_reap()
            await self._wait_or_shutdown()

    async def _poll(self) -> None:
        async with _worker_session() as session:
            # The worker is a platform-level operation: it must claim and
            # execute jobs across every campus, so it uses an explicit
            # platform context (tenant=None would fail closed).
            repo = JobRepository(session, platform_context())
            for _ in range(self._batch_size):
                job = await repo.acquire_next(job_types=self._job_types)
                if job is None:
                    return

                service = JobService(session, platform_context())
                await service.execute_job(job.id)

    async def _maybe_reap(self) -> None:
        """Reclaim stale ``running`` jobs, at most every ``reap_interval``.

        Runs on its own cadence (independent of the poll interval) so a
        dead worker's jobs are put back on the queue without waiting for
        the poll loop. Exceptions are swallowed — reaping is best-effort
        and must never take down the worker.
        """
        now = time.monotonic()
        if now - self._last_reap_at < self._reap_interval:
            return
        self._last_reap_at = now

        stale_before = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            seconds=self._stale_after
        )
        try:
            async with _worker_session() as session:
                repo = JobRepository(session, platform_context())
                requeued, dead_lettered = await repo.reclaim_stale_running(stale_before)
                if requeued or dead_lettered:
                    logger.warning(
                        "Stale-job reaper reclaimed %d running job(s): "
                        "%d requeued, %d dead-lettered",
                        requeued + dead_lettered, requeued, dead_lettered,
                    )
        except Exception:
            logger.exception("Stale-job reaper pass failed (non-fatal)")

    async def _wait_or_shutdown(self) -> None:
        try:
            await asyncio.wait_for(
                self._shutdown_event.wait(),
                timeout=self._poll_interval,
            )
        except asyncio.TimeoutError:
            pass


# ---------------------------------------------------------------------------
# Worker session — open a new session outside the request lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _worker_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
