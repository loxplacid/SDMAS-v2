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
    and by local dev invocations. Polls the database for pending jobs
    and periodically reclaims stale ``running`` jobs (reaper), looping
    until the process receives SIGTERM/SIGINT.
    """
    import signal

    def _env_float(name: str, default: float) -> float:
        try:
            return float(os.environ.get(name, default))
        except (TypeError, ValueError):
            logger.warning("Invalid %s, falling back to %s", name, default)
            return default

    poll_interval = _env_float("WORKER_POLL_INTERVAL", 5.0)
    reap_interval = _env_float("WORKER_REAP_INTERVAL", _DEFAULT_REAP_INTERVAL_S)
    stale_after = _env_float("WORKER_STALE_AFTER", _DEFAULT_STALE_AFTER_S)
    worker = JobWorker(
        poll_interval=poll_interval,
        reap_interval=reap_interval,
        stale_after=stale_after,
    )

    async def _run() -> None:
        # start() schedules the poll task with asyncio.create_task, so it
        # must run while the event loop is active.
        worker.start()
        logger.info(
            "Worker entrypoint started (poll=%ss reap=%ss stale=%ss)",
            poll_interval, reap_interval, stale_after,
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
            # Cancel the poll task and let the worker clean up.
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
            repo = JobRepository(session)
            for _ in range(self._batch_size):
                job = await repo.acquire_next(job_types=self._job_types)
                if job is None:
                    return

                service = JobService(session)
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
                repo = JobRepository(session)
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
