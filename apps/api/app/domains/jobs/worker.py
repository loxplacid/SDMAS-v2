from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.jobs.repository import JobRepository
from app.domains.jobs.service import JobService
from app.infrastructure.database import async_session_factory

logger = logging.getLogger(__name__)


class JobWorker:
    """Background worker that polls the database for pending jobs.

    Designed for single-process deployments. For horizontal scaling,
    replace the ``acquire_next`` logic with a distributed lock or
    switch to Redis/Postgres advisory locks.
    """

    def __init__(
        self,
        *,
        poll_interval: float = 5.0,
        batch_size: int = 1,
        job_types: list[str] | None = None,
    ) -> None:
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._job_types = job_types
        self._task: asyncio.Task[None] | None = None
        self._shutdown_event = asyncio.Event()

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
            "JobWorker started (poll=%ss batch=%d types=%s)",
            self._poll_interval, self._batch_size, self._job_types or "all",
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
            await self._wait_or_shutdown()

    async def _poll(self) -> None:
        async for session in _worker_session():
            repo = JobRepository(session)
            for _ in range(self._batch_size):
                job = await repo.acquire_next(job_types=self._job_types)
                if job is None:
                    return

                service = JobService(session)
                await service.execute_job(job.id)

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
