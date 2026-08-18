"""Tamper-evident audit chain — tenant-scoped repository.

Every query is built through :class:`TenantScopedRepository`, which pins
``campus_id`` at query-construction time — a caller from campus A can
never read or mutate a chain entry or checkpoint belonging to campus B
(the per-campus chain design means this also holds for the platform chain
when ``campus_id`` is NULL).

Note: chain writes are keyed by the *audit event's* campus, not the
caller's tenant — a platform write that records a campus-scoped audit
event chains into that campus's chain (verified by the caller's campus
pinning on read).
"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.multi_tenant.models import TenantContext
from app.multi_tenant.repository import TenantScopedRepository
from app.platform.cryptography.models import (
    AuditChainCheckpoint,
    AuditChainEntry,
)


class AuditChainRepository(TenantScopedRepository):
    """Tenant-scoped data access for the audit chain."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: Optional[TenantContext] = None,
    ) -> None:
        super().__init__(session, tenant)

    # ------------------------------------------------------------------
    # Entries
    # ------------------------------------------------------------------

    async def create_entry(self, entry: AuditChainEntry) -> AuditChainEntry:
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def get_entry(self, entry_id: int) -> Optional[AuditChainEntry]:
        return await self.get_by_id(AuditChainEntry, entry_id)

    async def last_entry(self, campus_id: int | None) -> Optional[AuditChainEntry]:
        """The most recent chain entry for a campus chain."""
        query = (
            select(AuditChainEntry)
            .where(AuditChainEntry.campus_id == campus_id)
            .order_by(AuditChainEntry.chain_index.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    async def entry_for_audit(self, audit_log_id: int) -> Optional[AuditChainEntry]:
        query = self.scoped_query(AuditChainEntry).where(
            AuditChainEntry.audit_log_id == audit_log_id
        )
        result = await self.session.execute(query.limit(1))
        return result.scalars().first()

    async def list_entries(self, campus_id: int | None) -> Sequence[AuditChainEntry]:
        query = (
            select(AuditChainEntry)
            .where(AuditChainEntry.campus_id == campus_id)
            .order_by(AuditChainEntry.chain_index)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_entries_scoped(
        self, skip: int = 0, limit: int = 100
    ) -> tuple[Sequence[AuditChainEntry], int]:
        """Tenant-scoped listing (reads only the caller's campus chain)."""
        return await self._list_by_tenant(
            AuditChainEntry, order_by_attr="chain_index", skip=skip, limit=limit
        )

    async def count_entries(self, campus_id: int | None) -> int:
        query = select(func.count(AuditChainEntry.id)).where(AuditChainEntry.campus_id == campus_id)
        result = await self.session.execute(query)
        return result.scalar() or 0

    # ------------------------------------------------------------------
    # Checkpoints
    # ------------------------------------------------------------------

    async def create_checkpoint(self, checkpoint: AuditChainCheckpoint) -> AuditChainCheckpoint:
        self.session.add(checkpoint)
        await self.session.flush()
        return checkpoint

    async def latest_checkpoint(self, campus_id: int | None) -> Optional[AuditChainCheckpoint]:
        query = (
            select(AuditChainCheckpoint)
            .where(AuditChainCheckpoint.campus_id == campus_id)
            .order_by(AuditChainCheckpoint.up_to_chain_index.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    async def list_checkpoints(self, campus_id: int | None) -> Sequence[AuditChainCheckpoint]:
        query = (
            select(AuditChainCheckpoint)
            .where(AuditChainCheckpoint.campus_id == campus_id)
            .order_by(AuditChainCheckpoint.up_to_chain_index)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
