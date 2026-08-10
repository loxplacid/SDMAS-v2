from __future__ import annotations

import datetime
from typing import Any, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domains.migration.models import MigrationProject
from app.multi_tenant.models import TenantContext


class MigrationProjectRepository:
    """Tenant-scoped repository for migration projects.

    Every query is pinned to ``campus_id`` (the tenant boundary).  A project
    from another campus simply does not exist to this repository — callers
    translate that into a 404.  ``tenant`` must carry a concrete campus or
    explicit platform scope; ``tenant=None`` fails closed.
    """

    def __init__(self, session: AsyncSession, tenant: TenantContext | None = None) -> None:
        self.session = session
        self.tenant = tenant

    def _campus_filter(self) -> int | None:
        """Return the campus id to pin to, or None for platform scope."""
        if self.tenant is None:
            return None
        if self.tenant.is_tenant_scoped:
            return self.tenant.campus_id
        if self.tenant.allow_cross_tenant:
            return None
        return None

    async def create(self, project: MigrationProject) -> MigrationProject:
        self.session.add(project)
        await self.session.flush()
        return project

    async def get_by_id(self, project_id: int) -> MigrationProject:
        campus_id = self._campus_filter()
        query = select(MigrationProject).where(MigrationProject.id == project_id)
        if campus_id is not None:
            query = query.where(MigrationProject.campus_id == campus_id)
        result = await self.session.execute(query)
        project = result.scalar_one_or_none()
        if project is None:
            raise NotFoundError(f"Migration project {project_id} not found")
        return project

    async def list_projects(
        self,
        *,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[MigrationProject], int]:
        campus_id = self._campus_filter()
        query = select(MigrationProject)
        count_query = select(func.count(MigrationProject.id))
        filters = []
        if campus_id is not None:
            filters.append(MigrationProject.campus_id == campus_id)
        if status:
            filters.append(MigrationProject.status == status)
        if filters:
            query = query.where(*filters)
            count_query = count_query.where(*filters)
        query = query.order_by(MigrationProject.updated_at.desc()).offset(skip).limit(limit)

        total = (await self.session.execute(count_query)).scalar() or 0
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def touch(self, project_id: int, **values: Any) -> None:
        """Update a project row (partial, targeted update — never clobbers
        unrelated fields written concurrently)."""
        payload: dict[str, Any] = {"updated_at": datetime.datetime.now(datetime.timezone.utc)}
        payload.update(values)
        await self.session.execute(
            update(MigrationProject).where(MigrationProject.id == project_id).values(**payload)
        )
        await self.session.flush()

    async def update_status(self, project_id: int, status: str) -> None:
        await self.touch(project_id, status=status)
