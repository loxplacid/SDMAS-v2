from __future__ import annotations

import datetime
import logging
from typing import Any, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.jobs.models import Job
from app.domains.jobs.registry import get_job_class
from app.domains.jobs.repository import JobRepository
from app.domains.jobs.schemas import JobCreate, JobUpdate

logger = logging.getLogger(__name__)


class JobService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = JobRepository(session)

    async def create_job(self, data: JobCreate) -> Job:
        now = datetime.datetime.now(datetime.timezone.utc)

        if data.identity_key:
            existing = await self.repo.get_by_identity_key(data.identity_key)
            if existing is not None and existing.status not in (
                "completed", "cancelled", "dead_letter",
            ):
                logger.debug(
                    "Returning existing job %d for identity_key '%s'",
                    existing.id, data.identity_key,
                )
                return existing

        job = Job(
            job_type=data.job_type,
            status="pending",
            params=data.params,
            priority=data.priority,
            max_retries=data.max_retries,
            scheduled_at=data.scheduled_at,
            identity_key=data.identity_key,
            user_id=data.user_id,
            campus_id=data.campus_id,
            progress=0.0,
            created_at=now,
            updated_at=now,
        )
        created = await self.repo.create(job)
        logger.info("Created job %d [type=%s]", created.id, created.job_type)
        return created

    async def get_job(self, job_id: int) -> Job | None:
        return await self.repo.get_by_id(job_id)

    async def update_job(self, job_id: int, data: JobUpdate) -> Job | None:
        job = await self.repo.get_by_id(job_id)
        if job is None:
            return None

        if data.status is not None:
            if data.status == "cancelled":
                await self.repo.cancel(job_id)
            elif data.status == "failed":
                await self.repo.fail(job_id, data.last_error or "Manually failed")
            return await self.repo.get_by_id(job_id)

        if data.progress is not None:
            await self.repo.update_progress(job_id, data.progress)
        if data.result is not None:
            await self.repo.complete(job_id, data.result)

        return await self.repo.get_by_id(job_id)

    async def cancel_job(self, job_id: int) -> Job | None:
        job = await self.repo.get_by_id(job_id)
        if job is None:
            return None
        if job.status in ("completed", "dead_letter"):
            return job
        await self.repo.cancel(job_id)
        return await self.repo.get_by_id(job_id)

    async def retry_job(self, job_id: int) -> Job | None:
        job = await self.repo.get_by_id(job_id)
        if job is None:
            return None
        if job.status not in ("failed", "dead_letter"):
            return job

        now = datetime.datetime.now(datetime.timezone.utc)
        job.status = "pending"
        job.retry_count = 0
        job.last_error = None
        job.scheduled_at = now
        job.updated_at = now
        await self.session.flush()
        return job

    async def list_jobs(
        self,
        *,
        status: str | None = None,
        job_type: str | None = None,
        user_id: int | None = None,
        campus_id: int | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[Job], int]:
        return await self.repo.list(
            status=status,
            job_type=job_type,
            user_id=user_id,
            campus_id=campus_id,
            skip=skip,
            limit=limit,
        )

    async def execute_job(self, job_id: int) -> None:
        """Run a job inline (called by the worker or manually)."""
        job = await self.repo.get_by_id(job_id)
        if job is None:
            logger.warning("Job %d not found — cannot execute", job_id)
            return
        if job.status != "running":
            logger.warning(
                "Job %d has status '%s' — can only execute running jobs",
                job_id, job.status,
            )
            return

        job_cls = get_job_class(job.job_type)
        if job_cls is None:
            error = f"No handler registered for job type '{job.job_type}'"
            logger.error(error)
            await self.repo.fail(job_id, error)
            return

        job_instance = job_cls()
        try:
            await job_instance.before_run(job, self.session)
            result = await job_instance.run(job, self.session)
            await job_instance.after_run(job, self.session, result)
            await self.repo.complete(job_id, result)
            logger.info("Job %d [type=%s] completed successfully", job_id, job.job_type)
        except Exception as exc:
            await job_instance.on_failure(job, self.session, exc)
            logger.warning("Job %d [type=%s] failed: %s", job_id, job.job_type, exc)
            await self._handle_failure(job_id, str(exc))

    async def _handle_failure(self, job_id: int, error: str) -> None:
        job = await self.repo.get_by_id(job_id)
        if job is None:
            return

        new_retry_count = (job.retry_count or 0) + 1
        if new_retry_count > job.max_retries:
            await self.repo.fail(job_id, error)
            logger.warning(
                "Job %d moved to dead_letter after %d/%d retries",
                job_id, job.max_retries, job.max_retries,
            )
        else:
            delay = min(60 * (2 ** (new_retry_count - 1)), 86400)
            retry_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=delay)
            await self.repo.fail(job_id, error, retry_at=retry_at)
            job.retry_count = new_retry_count
            await self.session.flush()
            logger.info(
                "Job %d scheduled for retry %d/%d in %ds",
                job_id, new_retry_count, job.max_retries, delay,
            )
