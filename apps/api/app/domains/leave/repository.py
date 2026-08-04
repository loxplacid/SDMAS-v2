from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domains.leave.models import LeaveRequest
from app.multi_tenant.models import TenantContext
from app.multi_tenant.repository import TenantScopedRepository


class LeaveRequestRepository(TenantScopedRepository):
    def __init__(self, session: AsyncSession, tenant: Optional[TenantContext] = None) -> None:
        super().__init__(session, tenant)

    async def get_by_id(self, leave_id: int) -> LeaveRequest:
        result = await self.session.execute(
            self.scoped_query(LeaveRequest).where(LeaveRequest.id == leave_id)
        )
        entity = result.scalar_one_or_none()
        if entity is None:
            raise NotFoundError(f"LeaveRequest with id {leave_id} not found")
        return entity

    async def get_by_id_allow_legacy_owner(
        self, leave_id: int, user_id: int
    ) -> LeaveRequest:
        """Fetch a leave request tenant-scoped, with one deliberate legacy
        exception: a request that carries **no** ``campus_id`` (pre-tenancy
        data) is visible to its owner.  A request explicitly tagged with
        another campus is never visible — cross-tenant access is closed at
        query construction time, not by a post-fetch guard.
        """
        query = self.scoped_query(LeaveRequest).where(LeaveRequest.id == leave_id)
        if self._effective_campus_id() is not None:
            query = query.where(
                or_(
                    LeaveRequest.campus_id == self._effective_campus_id(),
                    LeaveRequest.campus_id.is_(None) & (LeaveRequest.user_id == user_id),
                )
            )
        result = await self.session.execute(query)
        entity = result.scalar_one_or_none()
        if entity is None:
            raise NotFoundError(f"LeaveRequest with id {leave_id} not found")
        return entity

    async def list(
        self,
        user_id: Optional[int] = None,
        leave_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[LeaveRequest], int]:
        query = self.scoped_query(LeaveRequest)
        count_query = self.scoped_count(LeaveRequest)

        if user_id is not None:
            query = query.where(LeaveRequest.user_id == user_id)
            count_query = count_query.where(LeaveRequest.user_id == user_id)
        if leave_type is not None:
            query = query.where(LeaveRequest.leave_type == leave_type)
            count_query = count_query.where(LeaveRequest.leave_type == leave_type)

        query = query.offset(skip).limit(limit).order_by(LeaveRequest.created_at)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.session.execute(query)
        items = result.scalars().all()

        return items, total

    async def create(self, entity: LeaveRequest) -> LeaveRequest:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def update(self, entity: LeaveRequest) -> LeaveRequest:
        await self.session.flush()
        return entity

    async def delete(self, entity: LeaveRequest) -> None:
        await self.session.delete(entity)
