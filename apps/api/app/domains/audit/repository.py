from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domains.audit.models import AuditLog
from app.multi_tenant.models import TenantContext
from app.multi_tenant.repository import TenantScopedRepository


class AuditLogRepository(TenantScopedRepository):
    """Data access for audit log entries (read-only for queries,
    write-only for the service).  Tenant-scoped at query construction."""

    def __init__(self, session: AsyncSession, tenant: Optional[TenantContext] = None) -> None:
        super().__init__(session, tenant)

    async def create(self, entry: AuditLog) -> AuditLog:
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def get_by_id(self, entry_id: int) -> AuditLog:
        result = await self.session.execute(
            self.scoped_query(AuditLog).where(AuditLog.id == entry_id)
        )
        entry = result.scalar_one_or_none()
        if entry is None:
            raise NotFoundError(f"AuditLog with id {entry_id} not found")
        return entry

    async def list(
        self,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        campus_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        actor_type: Optional[str] = None,
        actor_id: Optional[str] = None,
        result: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[AuditLog], int]:
        """Paginated audit log listing with optional filters."""
        conditions: list = []

        if user_id is not None:
            conditions.append(AuditLog.user_id == user_id)
        if action is not None:
            conditions.append(AuditLog.action == action)
        if resource_type is not None:
            conditions.append(AuditLog.resource_type == resource_type)
        if resource_id is not None:
            conditions.append(AuditLog.resource_id == resource_id)
        if campus_id is not None:
            conditions.append(AuditLog.campus_id == campus_id)
        if start_date is not None:
            conditions.append(AuditLog.created_at >= start_date)
        if end_date is not None:
            conditions.append(AuditLog.created_at <= end_date)
        if actor_type is not None:
            conditions.append(AuditLog.actor_type == actor_type)
        if actor_id is not None:
            conditions.append(AuditLog.actor_id == actor_id)
        if result is not None:
            conditions.append(AuditLog.result == result)

        query = self.scoped_query(AuditLog)
        count_query = self.scoped_count(AuditLog)

        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        query = (
            query.order_by(desc(AuditLog.created_at), desc(AuditLog.id))
            .offset(skip)
            .limit(limit)
        )

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.session.execute(query)
        items = result.scalars().all()

        return items, total
