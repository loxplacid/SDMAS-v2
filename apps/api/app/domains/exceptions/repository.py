"""Universal Exception Management — repository.

Tenant-scoped CRUD and query helpers for ``SystemException`` and
``SystemExceptionEvent``.  Every query is pinned to the current campus
via the ``TenantContext``.
"""

from __future__ import annotations

import datetime
from typing import Sequence

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.exceptions.models import (
    EXCEPTION_TERMINAL_STATUSES,
    SystemException,
    SystemExceptionEvent,
)
from app.multi_tenant.models import TenantContext


class ExceptionRepository:
    """Repository for system exceptions with tenant scoping."""

    def __init__(self, session: AsyncSession, tenant: TenantContext):
        self.session = session
        self.tenant = tenant

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(self, exception: SystemException) -> SystemException:
        """Persist a new exception (campus_id is set from tenant context)."""
        exception.campus_id = self.tenant.campus_id
        self.session.add(exception)
        await self.session.flush()
        return exception

    async def create_event(self, event: SystemExceptionEvent) -> SystemExceptionEvent:
        """Persist an immutable timeline event."""
        self.session.add(event)
        await self.session.flush()
        return event

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_by_id(self, exception_id: int) -> SystemException | None:
        """Fetch a single exception by ID, with events eagerly loaded."""
        stmt = (
            select(SystemException)
            .options(selectinload(SystemException.events))
            .where(
                SystemException.id == exception_id,
                SystemException.campus_id == self.tenant.campus_id,
            )
            # Always re-read the timeline from the DB so a caller holding
            # an earlier reference sees newly recorded events.
            .execution_options(populate_existing=True)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_source(
        self,
        source_domain: str,
        source_type: str,
        source_id: int,
    ) -> SystemException | None:
        """Fetch an exception by its source triple (for deduplication)."""
        stmt = select(SystemException).where(
            SystemException.campus_id == self.tenant.campus_id,
            SystemException.source_domain == source_domain,
            SystemException.source_type == source_type,
            SystemException.source_id == source_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_exceptions(
        self,
        *,
        exception_type: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        student_id: int | None = None,
        owner_id: int | None = None,
        case_id: int | None = None,
        source_domain: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[SystemException], int]:
        """List exceptions with filtering and pagination."""
        filters = [
            SystemException.campus_id == self.tenant.campus_id,
        ]
        if exception_type:
            filters.append(SystemException.exception_type == exception_type)
        if severity:
            filters.append(SystemException.severity == severity)
        if status:
            filters.append(SystemException.status == status)
        if entity_type:
            filters.append(SystemException.entity_type == entity_type)
        if entity_id is not None:
            filters.append(SystemException.entity_id == entity_id)
        if student_id is not None:
            filters.append(SystemException.student_id == student_id)
        if owner_id is not None:
            filters.append(SystemException.owner_id == owner_id)
        if case_id is not None:
            filters.append(SystemException.case_id == case_id)
        if source_domain:
            filters.append(SystemException.source_domain == source_domain)

        where = and_(*filters) if filters else True

        # Count
        count_stmt = select(func.count(SystemException.id)).where(where)
        total = (await self.session.execute(count_stmt)).scalar_one()

        # Fetch
        stmt = (
            select(SystemException)
            .where(where)
            .order_by(SystemException.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        items = result.scalars().all()

        return items, total

    async def list_open_for_student(
        self,
        student_id: int,
        *,
        include_resolved: bool = False,
    ) -> Sequence[SystemException]:
        """List exceptions for a specific student (Student 360 view)."""
        filters = [
            SystemException.campus_id == self.tenant.campus_id,
            SystemException.student_id == student_id,
        ]
        if not include_resolved:
            filters.append(SystemException.status.notin_(EXCEPTION_TERMINAL_STATUSES))
        stmt = (
            select(SystemException)
            .where(and_(*filters))
            .order_by(SystemException.severity, SystemException.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_by_status(self) -> dict[str, int]:
        """Count exceptions grouped by status (dashboard metrics)."""
        stmt = (
            select(SystemException.status, func.count(SystemException.id))
            .where(SystemException.campus_id == self.tenant.campus_id)
            .group_by(SystemException.status)
        )
        result = await self.session.execute(stmt)
        return dict(result.all())

    async def count_by_severity(self) -> dict[str, int]:
        """Count exceptions grouped by severity (dashboard metrics)."""
        stmt = (
            select(SystemException.severity, func.count(SystemException.id))
            .where(
                SystemException.campus_id == self.tenant.campus_id,
                SystemException.status.notin_(EXCEPTION_TERMINAL_STATUSES),
            )
            .group_by(SystemException.severity)
        )
        result = await self.session.execute(stmt)
        return dict(result.all())

    async def count_overdue(self) -> int:
        """Count open exceptions past their due date."""
        now = datetime.datetime.now(datetime.timezone.utc)
        stmt = select(func.count(SystemException.id)).where(
            SystemException.campus_id == self.tenant.campus_id,
            SystemException.status.notin_(EXCEPTION_TERMINAL_STATUSES),
            SystemException.due_at.isnot(None),
            SystemException.due_at < now,
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def get_next_event_seq(self, exception_id: int) -> int:
        """Get the next event sequence number for an exception."""
        stmt = select(func.max(SystemExceptionEvent.event_seq)).where(
            SystemExceptionEvent.exception_id == exception_id
        )
        result = await self.session.execute(stmt)
        max_seq = result.scalar_one()
        return (max_seq or 0) + 1

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update_status(
        self,
        exception_id: int,
        new_status: str,
        *,
        version: int,
    ) -> bool:
        """Update status with optimistic concurrency check."""
        stmt = (
            update(SystemException)
            .where(
                SystemException.id == exception_id,
                SystemException.campus_id == self.tenant.campus_id,
                SystemException.version == version,
            )
            .values(
                status=new_status,
                version=SystemException.version + 1,
            )
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def update_fields(
        self,
        exception_id: int,
        **fields,
    ) -> bool:
        """Update arbitrary fields with optimistic concurrency."""
        if "version" in fields:
            old_version = fields.pop("version")
            fields["version"] = SystemException.version + 1
            where = [
                SystemException.id == exception_id,
                SystemException.campus_id == self.tenant.campus_id,
                SystemException.version == old_version,
            ]
        else:
            where = [
                SystemException.id == exception_id,
                SystemException.campus_id == self.tenant.campus_id,
            ]
        stmt = update(SystemException).where(and_(*where)).values(**fields)
        result = await self.session.execute(stmt)
        return result.rowcount > 0
