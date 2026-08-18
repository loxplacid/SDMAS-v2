"""Data lineage foundation — tenant-scoped repository.

Every query is built through :class:`TenantScopedRepository`, which pins
``campus_id`` at query-construction time — a caller from campus A can never
read or mutate a lineage node, edge, calculation version, or evidence
reference belonging to campus B.
"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.multi_tenant.models import TenantContext
from app.multi_tenant.repository import TenantScopedRepository
from app.platform.lineage.models import (
    CalculationVersion,
    DataAsset,
    DataSource,
    EvidenceReference,
    LineageEdge,
    Transformation,
)


class LineageRepository(TenantScopedRepository):
    """Tenant-scoped data access for the data lineage layer."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: Optional[TenantContext] = None,
    ) -> None:
        super().__init__(session, tenant)

    # ------------------------------------------------------------------
    # DataSource
    # ------------------------------------------------------------------

    async def create_source(self, source: DataSource) -> DataSource:
        self.session.add(source)
        await self.session.flush()
        return source

    async def find_source(self, source_type: str, external_ref: str) -> Optional[DataSource]:
        query = self.scoped_query(DataSource).where(
            DataSource.source_type == source_type,
            DataSource.external_ref == external_ref,
        )
        result = await self.session.execute(query.limit(1))
        return result.scalars().first()

    async def get_source(self, source_id: int) -> Optional[DataSource]:
        return await self.get_by_id(DataSource, source_id)

    async def get_source_or_404(self, source_id: int) -> DataSource:
        return await self.get_by_id_or_404(DataSource, source_id, resource="data source")

    async def list_sources(
        self, *, skip: int = 0, limit: int = 100
    ) -> tuple[Sequence[DataSource], int]:
        return await self._list_by_tenant(DataSource, order_by_attr="id", skip=skip, limit=limit)

    # ------------------------------------------------------------------
    # DataAsset
    # ------------------------------------------------------------------

    async def create_asset(self, asset: DataAsset) -> DataAsset:
        self.session.add(asset)
        await self.session.flush()
        return asset

    async def find_asset(self, asset_type: str, ref: str) -> Optional[DataAsset]:
        query = self.scoped_query(DataAsset).where(
            DataAsset.asset_type == asset_type,
            DataAsset.ref == ref,
        )
        result = await self.session.execute(query.limit(1))
        return result.scalars().first()

    async def get_asset(self, asset_id: int) -> Optional[DataAsset]:
        return await self.get_by_id(DataAsset, asset_id)

    async def get_asset_or_404(self, asset_id: int) -> DataAsset:
        return await self.get_by_id_or_404(DataAsset, asset_id, resource="data asset")

    async def list_assets(
        self, *, skip: int = 0, limit: int = 100
    ) -> tuple[Sequence[DataAsset], int]:
        return await self._list_by_tenant(DataAsset, order_by_attr="id", skip=skip, limit=limit)

    # ------------------------------------------------------------------
    # Transformation
    # ------------------------------------------------------------------

    async def create_transformation(self, transform: Transformation) -> Transformation:
        self.session.add(transform)
        await self.session.flush()
        return transform

    async def find_transformation(self, transform_type: str, name: str) -> Optional[Transformation]:
        query = self.scoped_query(Transformation).where(
            Transformation.transform_type == transform_type,
            Transformation.name == name,
        )
        result = await self.session.execute(query.limit(1))
        return result.scalars().first()

    async def get_transformation(self, transformation_id: int) -> Optional[Transformation]:
        return await self.get_by_id(Transformation, transformation_id)

    # ------------------------------------------------------------------
    # LineageEdge
    # ------------------------------------------------------------------

    async def create_edge(self, edge: LineageEdge) -> LineageEdge:
        self.session.add(edge)
        await self.session.flush()
        return edge

    async def find_edge(
        self,
        upstream_type: str,
        upstream_id: int,
        downstream_type: str,
        downstream_id: int,
        edge_type: str,
    ) -> Optional[LineageEdge]:
        query = self.scoped_query(LineageEdge).where(
            LineageEdge.upstream_type == upstream_type,
            LineageEdge.upstream_id == upstream_id,
            LineageEdge.downstream_type == downstream_type,
            LineageEdge.downstream_id == downstream_id,
            LineageEdge.edge_type == edge_type,
        )
        result = await self.session.execute(query.limit(1))
        return result.scalars().first()

    async def incoming_edges(self, node_type: str, node_id: int) -> Sequence[LineageEdge]:
        """Edges whose *downstream* is the node (its direct inputs)."""
        query = self.scoped_query(LineageEdge).where(
            LineageEdge.downstream_type == node_type,
            LineageEdge.downstream_id == node_id,
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def outgoing_edges(self, node_type: str, node_id: int) -> Sequence[LineageEdge]:
        """Edges whose *upstream* is the node (its direct outputs)."""
        query = self.scoped_query(LineageEdge).where(
            LineageEdge.upstream_type == node_type,
            LineageEdge.upstream_id == node_id,
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # CalculationVersion
    # ------------------------------------------------------------------

    async def create_calculation(self, calc: CalculationVersion) -> CalculationVersion:
        self.session.add(calc)
        await self.session.flush()
        return calc

    async def current_calculation(self, calc_name: str) -> Optional[CalculationVersion]:
        query = self.scoped_query(CalculationVersion).where(
            CalculationVersion.calc_name == calc_name,
            CalculationVersion.is_current.is_(True),
        )
        result = await self.session.execute(query.limit(1))
        return result.scalars().first()

    async def list_calculations(self, calc_name: str) -> Sequence[CalculationVersion]:
        query = self.scoped_query(CalculationVersion).where(
            CalculationVersion.calc_name == calc_name
        )
        result = await self.session.execute(query.order_by(CalculationVersion.version.desc()))
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # EvidenceReference
    # ------------------------------------------------------------------

    async def create_evidence(self, evidence: EvidenceReference) -> EvidenceReference:
        self.session.add(evidence)
        await self.session.flush()
        return evidence

    async def list_evidence(self, node_type: str, node_id: int) -> Sequence[EvidenceReference]:
        query = self.scoped_query(EvidenceReference).where(
            EvidenceReference.node_type == node_type,
            EvidenceReference.node_id == node_id,
        )
        result = await self.session.execute(query.order_by(EvidenceReference.created_at.desc()))
        return list(result.scalars().all())
