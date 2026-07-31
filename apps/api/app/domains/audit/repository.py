from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domains.audit.models import AuditLog


class AuditLogRepository:
    """Data access for audit log entries (read-only for queries,
    write-only for the service)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, entry: AuditLog) -> AuditLog:
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def get_by_id(self, entry_id: int) -> AuditLog:
        result = await self.session.execute(
            select(AuditLog).where(AuditLog.id == entry_id)
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

        query = select(AuditLog)
        count_query = select(func.count(AuditLog.id))

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
