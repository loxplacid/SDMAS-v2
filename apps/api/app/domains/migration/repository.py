from __future__ import annotations

import datetime
from typing import Any, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.migration.models import MigrationLog, MigrationMapping, MigrationRun


class MigrationRunRepository:
    """Migration-run repository with optional tenant (``campus_id``) pinning.

    Every read endpoint must scope by ``campus_id`` so one tenant can never
    list, read or roll back another tenant's migration runs.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, run: MigrationRun) -> MigrationRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_by_id(
        self, run_id: int, campus_id: int | None = None
    ) -> MigrationRun | None:
        query = select(MigrationRun).where(MigrationRun.id == run_id)
        if campus_id is not None:
            query = query.where(MigrationRun.campus_id == campus_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_status(self, run_id: int, status: str, **extra: Any) -> None:
        values: dict[str, Any] = {
            "status": status,
        }
        values.update(extra)
        await self.session.execute(
            update(MigrationRun).where(MigrationRun.id == run_id).values(**values)
        )
        await self.session.flush()

    async def list_runs(
        self,
        entity_type: str | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
        campus_id: int | None = None,
    ) -> tuple[Sequence[MigrationRun], int]:
        query = select(MigrationRun)
        count_query = select(func.count(MigrationRun.id))
        filters = []
        if campus_id is not None:
            filters.append(MigrationRun.campus_id == campus_id)
        if entity_type:
            filters.append(MigrationRun.entity_type == entity_type)
        if status:
            filters.append(MigrationRun.status == status)
        if filters:
            query = query.where(*filters)
            count_query = count_query.where(*filters)
        query = query.order_by(MigrationRun.created_at.desc()).offset(skip).limit(limit)

        total = (await self.session.execute(count_query)).scalar() or 0
        result = await self.session.execute(query)
        return list(result.scalars().all()), total


class MigrationLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log(
        self,
        run_id: int,
        level: str,
        entity_type: str,
        legacy_id: str | None = None,
        entity_subtype: str | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> MigrationLog:
        entry = MigrationLog(
            run_id=run_id,
            level=level,
            legacy_id=legacy_id,
            entity_type=entity_type,
            entity_subtype=entity_subtype,
            message=message,
            details=details,
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def entry_exists(self, run_id: int, legacy_id: str, entity_subtype: str | None) -> bool:
        """True when a log entry already exists for (run, record, subtype).

        ``migration_logs`` allows exactly one entry per record per run
        (unique constraint), so callers that may re-run a stream must check
        before logging to stay idempotent.
        """
        result = await self.session.execute(
            select(MigrationLog.id)
            .where(
                MigrationLog.run_id == run_id,
                MigrationLog.legacy_id == str(legacy_id),
                MigrationLog.entity_subtype == entity_subtype,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def list_by_run(
        self,
        run_id: int,
        level: str | None = None,
        skip: int = 0,
        limit: int = 500,
    ) -> tuple[Sequence[MigrationLog], int]:
        query = select(MigrationLog).where(MigrationLog.run_id == run_id)
        count_query = select(func.count(MigrationLog.id)).where(MigrationLog.run_id == run_id)
        if level:
            query = query.where(MigrationLog.level == level)
            count_query = count_query.where(MigrationLog.level == level)
        query = query.order_by(MigrationLog.created_at.asc()).offset(skip).limit(limit)

        total = (await self.session.execute(count_query)).scalar() or 0
        result = await self.session.execute(query)
        return list(result.scalars().all()), total


class MigrationMappingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        run_id: int,
        entity_type: str,
        legacy_id: str,
        sdmas_id: int,
    ) -> MigrationMapping:
        mapping = MigrationMapping(
            run_id=run_id,
            entity_type=entity_type,
            legacy_id=str(legacy_id),
            sdmas_id=sdmas_id,
        )
        self.session.add(mapping)
        await self.session.flush()
        return mapping

    async def resolve(
        self,
        entity_type: str,
        legacy_id: str,
    ) -> int | None:
        result = await self.session.execute(
            select(MigrationMapping.sdmas_id).where(
                MigrationMapping.entity_type == entity_type,
                MigrationMapping.legacy_id == str(legacy_id),
            )
        )
        return result.scalar_one_or_none()

    async def list_by_entity(
        self,
        entity_type: str,
        run_id: int | None = None,
    ) -> Sequence[MigrationMapping]:
        query = select(MigrationMapping).where(
            MigrationMapping.entity_type == entity_type,
        )
        if run_id:
            query = query.where(MigrationMapping.run_id == run_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def delete_by_run(self, run_id: int) -> None:
        from sqlalchemy import delete

        await self.session.execute(
            delete(MigrationMapping).where(MigrationMapping.run_id == run_id)
        )
        await self.session.flush()
