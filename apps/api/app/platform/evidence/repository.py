"""Enterprise evidence foundation — tenant-scoped repository.

Every query is built through :class:`TenantScopedRepository`, which pins
``campus_id`` at query-construction time — a caller from campus A can never
read or mutate an evidence package, item, reference, snapshot, hash, or
approval belonging to campus B.
"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.multi_tenant.models import TenantContext
from app.multi_tenant.repository import TenantScopedRepository
from app.platform.evidence.models import (
    EvidenceApproval,
    EvidenceHash,
    EvidenceItem,
    EvidencePackage,
    EvidenceReference,
    EvidenceSnapshot,
)


class EvidenceRepository(TenantScopedRepository):
    """Tenant-scoped data access for the evidence foundation."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: Optional[TenantContext] = None,
    ) -> None:
        super().__init__(session, tenant)

    # ------------------------------------------------------------------
    # Packages
    # ------------------------------------------------------------------

    async def create_package(self, package: EvidencePackage) -> EvidencePackage:
        self.session.add(package)
        await self.session.flush()
        return package

    async def get_package(self, package_id: int) -> Optional[EvidencePackage]:
        return await self.get_by_id(EvidencePackage, package_id)

    async def get_package_or_404(self, package_id: int) -> EvidencePackage:
        return await self.get_by_id_or_404(EvidencePackage, package_id, resource="evidence package")

    async def find_by_key(self, package_key: str) -> Optional[EvidencePackage]:
        query = self.scoped_query(EvidencePackage).where(EvidencePackage.package_key == package_key)
        result = await self.session.execute(query.limit(1))
        return result.scalars().first()

    async def list_packages(
        self,
        *,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[EvidencePackage], int]:
        extra = [EvidencePackage.status == status] if status else None
        return await self._list_by_tenant(
            EvidencePackage,
            order_by_attr="id",
            skip=skip,
            limit=limit,
            extra_filters=extra,
        )

    # ------------------------------------------------------------------
    # Items
    # ------------------------------------------------------------------

    async def create_item(self, item: EvidenceItem) -> EvidenceItem:
        self.session.add(item)
        await self.session.flush()
        return item

    async def get_item(self, item_id: int) -> Optional[EvidenceItem]:
        return await self.get_by_id(EvidenceItem, item_id)

    async def list_items(self, package_id: int) -> Sequence[EvidenceItem]:
        package = await self.get_package_or_404(package_id)
        query = self.scoped_query(EvidenceItem).where(EvidenceItem.package_id == package.id)
        result = await self.session.execute(query.order_by(EvidenceItem.id))
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # References
    # ------------------------------------------------------------------

    async def create_reference(self, reference: EvidenceReference) -> EvidenceReference:
        self.session.add(reference)
        await self.session.flush()
        return reference

    async def list_references(self, package_id: int) -> Sequence[EvidenceReference]:
        package = await self.get_package_or_404(package_id)
        query = self.scoped_query(EvidenceReference).where(
            EvidenceReference.package_id == package.id
        )
        result = await self.session.execute(query.order_by(EvidenceReference.id))
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    async def create_snapshot(self, snapshot: EvidenceSnapshot) -> EvidenceSnapshot:
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot

    async def get_snapshot(self, snapshot_id: int) -> Optional[EvidenceSnapshot]:
        return await self.get_by_id(EvidenceSnapshot, snapshot_id)

    async def list_snapshots(self, package_id: int) -> Sequence[EvidenceSnapshot]:
        package = await self.get_package_or_404(package_id)
        query = self.scoped_query(EvidenceSnapshot).where(EvidenceSnapshot.package_id == package.id)
        result = await self.session.execute(query.order_by(EvidenceSnapshot.id))
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Hash chain
    # ------------------------------------------------------------------

    async def create_hash(self, entry: EvidenceHash) -> EvidenceHash:
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def list_hashes(self, package_id: int) -> Sequence[EvidenceHash]:
        package = await self.get_package_or_404(package_id)
        query = self.scoped_query(EvidenceHash).where(EvidenceHash.package_id == package.id)
        result = await self.session.execute(query.order_by(EvidenceHash.chain_index))
        return list(result.scalars().all())

    async def last_hash(self, package_id: int) -> Optional[EvidenceHash]:
        package = await self.get_package_or_404(package_id)
        query = self.scoped_query(EvidenceHash).where(EvidenceHash.package_id == package.id)
        result = await self.session.execute(
            query.order_by(EvidenceHash.chain_index.desc()).limit(1)
        )
        return result.scalars().first()

    # ------------------------------------------------------------------
    # Approvals
    # ------------------------------------------------------------------

    async def create_approval(self, approval: EvidenceApproval) -> EvidenceApproval:
        self.session.add(approval)
        await self.session.flush()
        return approval

    async def list_approvals(self, package_id: int) -> Sequence[EvidenceApproval]:
        package = await self.get_package_or_404(package_id)
        query = self.scoped_query(EvidenceApproval).where(EvidenceApproval.package_id == package.id)
        result = await self.session.execute(query.order_by(EvidenceApproval.id))
        return list(result.scalars().all())
