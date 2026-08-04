from __future__ import annotations

import datetime
from typing import Any, Optional, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.jobs.models import Job
from app.multi_tenant.models import TenantContext
from app.multi_tenant.repository import TenantScopedRepository


class JobRepository(TenantScopedRepository):
    """Job data access.

    Routers construct this repository with the caller's ``TenantContext``
    so listing / fetching jobs is pinned to the caller's campus at query
    construction time.  The background :class:`JobWorker` constructs it
    without a tenant — that is an explicit platform operation.
    """

    def __init__(self, session: AsyncSession, tenant: Optional[TenantContext] = None) -> None:
        super().__init__(session, tenant)

    async def create(self, job: Job) -> Job:
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_by_id(self, job_id: int) -> Job | None:
        result = await self.session.execute(
            self.scoped_query(Job).where(Job.id == job_id)
        )
        return result.scalar_one_or_none()

    async def get_by_identity_key(self, key: str) -> Job | None:
        result = await self.session.execute(
            self.scoped_query(Job).where(Job.identity_key == key)
        )
        return result.scalar_one_or_none()

    async def acquire_next(
        self,
        job_types: list[str] | None = None,
    ) -> Job | None:
        """Atomically claim the next pending job.

        The claim is a single ``UPDATE … WHERE id = (SELECT …) AND
        status = 'pending' … RETURNING`` statement, so it is race-safe
        even when multiple worker processes (or the in-process worker
        plus dedicated worker replicas) poll the same table: the
        row-level lock plus the ``status = 'pending'`` predicate ensure
        exactly one worker wins each job. Works on PostgreSQL (row lock
        + re-checked predicate) and SQLite (serialised writer).
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        conditions = [
            Job.status == "pending",
            (Job.scheduled_at.is_(None)) | (Job.scheduled_at <= now),
        ]
        if job_types:
            conditions.append(Job.job_type.in_(job_types))

        # Pick the next candidate in a subquery, then flip it in the same
        # atomic statement.  The subquery is evaluated inside the UPDATE,
        # so two concurrent claimants both see the same candidate — but
        # only the first ``UPDATE … WHERE status = 'pending'`` matches;
        # the loser re-checks the predicate on the locked row, finds it
        # ``running``, and claims nothing.
        candidate = (
            select(Job.id)
            .where(*conditions)
            .order_by(Job.priority.asc(), Job.created_at.asc())
            .limit(1)
            .scalar_subquery()
        )
        claimed_id = await self.session.scalar(
            update(Job)
            .where(Job.id == candidate, Job.status == "pending")
            .values(status="running", started_at=now, updated_at=now)
            .returning(Job.id)
            .execution_options(synchronize_session=False)
        )
        if claimed_id is None:
            return None

        job = await self.session.get(Job, claimed_id)
        if job is not None:
            # The row was updated via a core statement; make sure the
            # in-memory object reflects ``status``/``started_at``.
            await self.session.refresh(job)
        return job

    async def reclaim_stale_running(
        self,
        stale_before: datetime.datetime,
    ) -> tuple[int, int]:
        """Reclaim jobs stuck in ``running`` past *stale_before*.

        A worker that dies (crash, OOM, or shutdown-cancel mid-job) leaves
        its claimed job in ``running`` forever — nothing else ever picks it
        up again, wedging the queue.  This pass finds those stale rows and,
        in a single atomic statement per branch:

        * jobs with retry budget remaining → back to ``pending`` (immediately
          re-runnable; ``retry_count`` bumped so a repeatedly-stuck job
          eventually exhausts its budget and stops looping);
        * jobs that have exhausted ``max_retries`` → ``dead_letter`` with a
          clear ``last_error``.

        The ``status = 'running'`` predicate plus the row lock makes this
        race-safe when several workers run the reaper concurrently (same
        reasoning as ``acquire_next``).  Returns ``(requeued, dead_lettered)``.

        **Heartbeat contract:** staleness is measured against ``updated_at``
        (last activity).  A job must finish within ``stale_after`` *or*
        refresh its activity by calling ``update_progress`` as it works —
        otherwise a slow-but-alive job gets requeued while its original
        worker is still processing it, risking double execution.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        stale_conditions = [
            Job.status == "running",
            Job.updated_at < stale_before,
        ]

        requeued = await self.session.scalars(
            update(Job)
            .where(*stale_conditions, Job.retry_count < Job.max_retries)
            .values(
                status="pending",
                started_at=None,
                scheduled_at=now,
                retry_count=Job.retry_count + 1,
                last_error="Reclaimed: worker stopped before completion",
                updated_at=now,
            )
            .returning(Job.id)
            .execution_options(synchronize_session=False)
        )
        requeued_ids = list(requeued.all())

        dead_lettered = await self.session.scalars(
            update(Job)
            .where(*stale_conditions, Job.retry_count >= Job.max_retries)
            .values(
                status="dead_letter",
                started_at=None,
                completed_at=now,
                last_error=(
                    "Reclaimed after max retries: worker stopped before "
                    "completion"
                ),
                updated_at=now,
            )
            .returning(Job.id)
            .execution_options(synchronize_session=False)
        )
        dead_lettered_ids = list(dead_lettered.all())

        return len(requeued_ids), len(dead_lettered_ids)

    async def complete(self, job_id: int, result: dict[str, Any] | None = None) -> None:
        now = datetime.datetime.now(datetime.timezone.utc)
        await self.session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                status="completed",
                progress=100.0,
                result=result,
                completed_at=now,
                updated_at=now,
            )
        )
        await self.session.flush()

    async def fail(
        self,
        job_id: int,
        error: str,
        retry_at: datetime.datetime | None = None,
    ) -> None:
        now = datetime.datetime.now(datetime.timezone.utc)
        values: dict[str, Any] = {
            "last_error": error,
            "updated_at": now,
        }

        if retry_at is not None:
            values["status"] = "pending"
            values["scheduled_at"] = retry_at
        else:
            values["status"] = "dead_letter"
            values["completed_at"] = now

        await self.session.execute(
            update(Job).where(Job.id == job_id).values(**values)
        )
        await self.session.flush()

    async def cancel(self, job_id: int) -> None:
        now = datetime.datetime.now(datetime.timezone.utc)
        await self.session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(status="cancelled", completed_at=now, updated_at=now)
        )
        await self.session.flush()

    async def update_progress(self, job_id: int, progress: float) -> None:
        await self.session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(progress=progress, updated_at=datetime.datetime.now(datetime.timezone.utc))
        )
        await self.session.flush()

    async def list(
        self,
        *,
        status: str | None = None,
        job_type: str | None = None,
        user_id: int | None = None,
        campus_id: int | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[Job], int]:
        query = self.scoped_query(Job)
        count_query = self.scoped_count(Job)

        filters = []
        if status is not None:
            filters.append(Job.status == status)
        if job_type is not None:
            filters.append(Job.job_type == job_type)
        if user_id is not None:
            filters.append(Job.user_id == user_id)
        if campus_id is not None:
            filters.append(Job.campus_id == campus_id)

        if filters:
            query = query.where(*filters)
            count_query = count_query.where(*filters)

        query = query.order_by(Job.created_at.desc()).offset(skip).limit(limit)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def count_pending(self, job_type: str | None = None) -> int:
        now = datetime.datetime.now(datetime.timezone.utc)
        conditions = [
            Job.status == "pending",
            (Job.scheduled_at.is_(None)) | (Job.scheduled_at <= now),
        ]
        if job_type:
            conditions.append(Job.job_type == job_type)

        result = await self.session.execute(
            self.scoped_count(Job).where(*conditions)
        )
        return result.scalar() or 0
