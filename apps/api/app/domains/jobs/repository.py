from __future__ import annotations

import datetime
from typing import Any, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.jobs.models import Job


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, job: Job) -> Job:
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_by_id(self, job_id: int) -> Job | None:
        result = await self.session.execute(
            select(Job).where(Job.id == job_id)
        )
        return result.scalar_one_or_none()

    async def get_by_identity_key(self, key: str) -> Job | None:
        result = await self.session.execute(
            select(Job).where(Job.identity_key == key)
        )
        return result.scalar_one_or_none()

    async def acquire_next(
        self,
        job_types: list[str] | None = None,
    ) -> Job | None:
        now = datetime.datetime.now(datetime.timezone.utc)
        conditions = [
            Job.status == "pending",
            (Job.scheduled_at.is_(None)) | (Job.scheduled_at <= now),
        ]
        if job_types:
            conditions.append(Job.job_type.in_(job_types))

        result = await self.session.execute(
            select(Job)
            .where(*conditions)
            .order_by(Job.priority.asc(), Job.created_at.asc())
            .limit(1)
        )
        job = result.scalar_one_or_none()
        if job is None:
            return None

        job.status = "running"
        job.started_at = now
        await self.session.flush()
        return job

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
        query = select(Job)
        count_query = select(func.count(Job.id))

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
            select(func.count(Job.id)).where(*conditions)
        )
        return result.scalar() or 0
