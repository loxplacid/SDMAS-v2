"""Data lineage foundation — application service.

Owns the lineage lifecycle:

- register data sources / assets / transformations (idempotent
  get-or-create by stable identity)
- connect nodes with directed, polymorphic edges
- versioned calculation definitions (current-version supersession)
- attach evidence references (audit entries, files, migration runs)
- answer provenance: *"where did this value come from?"* by walking the
  edge graph upstream from a target node
- integration hook :meth:`register_migration_import` — called when the
  migration engine completes an import so every migrated value traces back
  to its source file and run

Every operation is tenant-scoped through the repository and audited through
the existing audit domain.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.domains.audit.actors import ActorType, AuditActor
from app.domains.audit.service import AuditService
from app.multi_tenant.models import TenantContext
from app.platform.lineage.models import (
    ASSET_TYPES,
    EDGE_EDGE_TYPES,
    EVIDENCE_TYPES,
    NODE_TYPES,
    SOURCE_TYPES,
    TRANSFORM_TYPES,
    CalculationVersion,
    DataAsset,
    DataSource,
    EvidenceReference,
    LineageEdge,
    Transformation,
)
from app.platform.lineage.repository import LineageRepository
from app.platform.lineage.schemas import (
    CalculationVersionCreate,
    DataAssetCreate,
    DataSourceCreate,
    EvidenceReferenceCreate,
    LineageEdgeCreate,
    ProvenanceEdge,
    ProvenanceNode,
    ProvenanceReport,
    TransformationCreate,
)

logger = logging.getLogger(__name__)


class LineageService:
    """Data lineage operations (one tenant per instance)."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: Optional[TenantContext] = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.repo = LineageRepository(session, tenant)
        self.audit = AuditService(session, tenant)

    # ------------------------------------------------------------------
    # Nodes (idempotent registration)
    # ------------------------------------------------------------------

    async def register_source(
        self, data: DataSourceCreate, actor: AuditActor | None = None
    ) -> DataSource:
        """Register a data source; returns the existing row when the
        ``(source_type, external_ref)`` identity already exists in this
        campus (idempotent)."""
        if data.source_type not in SOURCE_TYPES:
            raise ValidationError(f"source_type must be one of {sorted(SOURCE_TYPES)}")
        existing = await self.repo.find_source(data.source_type, data.external_ref or "")
        if existing is not None:
            return existing
        source = DataSource(
            campus_id=self.repo._effective_campus_id(),
            name=data.name,
            source_type=data.source_type,
            external_ref=data.external_ref,
            description=data.description,
            record_ref=data.record_ref,
        )
        source = await self.repo.create_source(source)
        await self.audit.record(
            action="CREATE",
            resource_type="lineage_data_source",
            resource_id=str(source.id),
            actor=actor,
            details={"name": data.name, "source_type": data.source_type},
        )
        return source

    async def register_asset(
        self, data: DataAssetCreate, actor: AuditActor | None = None
    ) -> DataAsset:
        """Register a data asset; idempotent on ``(asset_type, ref)``."""
        if data.asset_type not in ASSET_TYPES:
            raise ValidationError(f"asset_type must be one of {sorted(ASSET_TYPES)}")
        existing = await self.repo.find_asset(data.asset_type, data.ref or "")
        if existing is not None:
            return existing
        asset = DataAsset(
            campus_id=self.repo._effective_campus_id(),
            name=data.name,
            asset_type=data.asset_type,
            description=data.description,
            ref=data.ref,
            schema_info=data.schema_info,
        )
        asset = await self.repo.create_asset(asset)
        await self.audit.record(
            action="CREATE",
            resource_type="lineage_data_asset",
            resource_id=str(asset.id),
            actor=actor,
            details={"name": data.name, "asset_type": data.asset_type},
        )
        return asset

    async def register_transformation(
        self, data: TransformationCreate, actor: AuditActor | None = None
    ) -> Transformation:
        """Register a transformation; idempotent on ``(transform_type, name)``."""
        if data.transform_type not in TRANSFORM_TYPES:
            raise ValidationError(f"transform_type must be one of {sorted(TRANSFORM_TYPES)}")
        existing = await self.repo.find_transformation(data.transform_type, data.name)
        if existing is not None:
            return existing
        transform = Transformation(
            campus_id=self.repo._effective_campus_id(),
            name=data.name,
            transform_type=data.transform_type,
            description=data.description,
            definition=data.definition,
        )
        transform = await self.repo.create_transformation(transform)
        await self.audit.record(
            action="CREATE",
            resource_type="lineage_transformation",
            resource_id=str(transform.id),
            actor=actor,
            details={"name": data.name, "transform_type": data.transform_type},
        )
        return transform

    # ------------------------------------------------------------------
    # Edges
    # ------------------------------------------------------------------

    async def connect(
        self,
        data: LineageEdgeCreate,
        actor: AuditActor | None = None,
    ) -> LineageEdge:
        """Create a directed edge; idempotent (unique per pair + edge_type)."""
        for side in ("upstream", "downstream"):
            node_type = getattr(data, f"{side}_type")
            if node_type not in NODE_TYPES:
                raise ValidationError(f"{side}_type must be one of {sorted(NODE_TYPES)}")
        if data.edge_type not in EDGE_EDGE_TYPES:
            raise ValidationError(f"edge_type must be one of {sorted(EDGE_EDGE_TYPES)}")
        existing = await self.repo.find_edge(
            data.upstream_type,
            data.upstream_id,
            data.downstream_type,
            data.downstream_id,
            data.edge_type,
        )
        if existing is not None:
            return existing
        edge = LineageEdge(
            campus_id=self.repo._effective_campus_id(),
            upstream_type=data.upstream_type,
            upstream_id=data.upstream_id,
            downstream_type=data.downstream_type,
            downstream_id=data.downstream_id,
            edge_type=data.edge_type,
            transformation_id=data.transformation_id,
        )
        edge = await self.repo.create_edge(edge)
        await self.audit.record(
            action="LINK",
            resource_type="lineage_edge",
            resource_id=str(edge.id),
            actor=actor,
            details={
                "upstream": f"{data.upstream_type}:{data.upstream_id}",
                "downstream": f"{data.downstream_type}:{data.downstream_id}",
                "edge_type": data.edge_type,
            },
        )
        return edge

    # ------------------------------------------------------------------
    # Calculations (versioned)
    # ------------------------------------------------------------------

    async def add_calculation_version(
        self, data: CalculationVersionCreate, actor: AuditActor | None = None
    ) -> CalculationVersion:
        """Add a new version of a calculation; the previous current version
        is superseded (audit-trail friendly versioning)."""
        current = await self.repo.current_calculation(data.calc_name)
        next_version = (current.version + 1) if current else 1
        calc = CalculationVersion(
            campus_id=self.repo._effective_campus_id(),
            calc_name=data.calc_name,
            version=next_version,
            formula=data.formula,
            definition=data.definition,
            asset_id=data.asset_id,
            is_current=True,
        )
        calc = await self.repo.create_calculation(calc)
        if current is not None:
            current.is_current = False
            current.superseded_by = calc.id
            await self.session.flush()
        await self.audit.record(
            action="CREATE",
            resource_type="lineage_calculation_version",
            resource_id=str(calc.id),
            actor=actor,
            details={
                "calc_name": data.calc_name,
                "version": next_version,
                "supersedes": current.id if current else None,
            },
        )
        return calc

    async def current_calculation(self, calc_name: str) -> Optional[CalculationVersion]:
        return await self.repo.current_calculation(calc_name)

    async def calculation_history(self, calc_name: str) -> Sequence[CalculationVersion]:
        return await self.repo.list_calculations(calc_name)

    # ------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------

    async def attach_evidence(
        self, data: EvidenceReferenceCreate, actor: AuditActor | None = None
    ) -> EvidenceReference:
        """Attach an evidence pointer to a lineage node (audit entry, file,
        migration run, report, source record)."""
        if data.node_type not in NODE_TYPES:
            raise ValidationError(f"node_type must be one of {sorted(NODE_TYPES)}")
        if data.kind not in EVIDENCE_TYPES:
            raise ValidationError(f"kind must be one of {sorted(EVIDENCE_TYPES)}")
        evidence = EvidenceReference(
            campus_id=self.repo._effective_campus_id(),
            node_type=data.node_type,
            node_id=data.node_id,
            kind=data.kind,
            reference=data.reference,
            checksum=data.checksum,
            note=data.note,
        )
        evidence = await self.repo.create_evidence(evidence)
        await self.audit.record(
            action="ATTACH",
            resource_type="lineage_evidence",
            resource_id=str(evidence.id),
            actor=actor,
            details={
                "node": f"{data.node_type}:{data.node_id}",
                "kind": data.kind,
                "reference": data.reference,
            },
        )
        return evidence

    # ------------------------------------------------------------------
    # Provenance: "where did this value come from?"
    # ------------------------------------------------------------------

    async def provenance(
        self, node_type: str, node_id: int, *, max_depth: int = 5
    ) -> ProvenanceReport:
        """Walk the edge graph *upstream* from the target node and return
        every node, edge, and evidence reference on the path.

        Traversal is bounded (``max_depth``) and cycle-safe (visited set),
        and only visits nodes that exist in this campus — cross-tenant
        nodes simply are not reachable because the repository pins every
        query to the caller's campus.
        """
        if node_type not in NODE_TYPES:
            raise ValidationError(f"node_type must be one of {sorted(NODE_TYPES)}")

        target = await self._resolve_node(node_type, node_id)
        if target is None:
            raise NotFoundError(f"{node_type} node {node_id} not found")

        nodes: list[ProvenanceNode] = [self._to_provenance_node(node_type, target)]
        edges: list[ProvenanceEdge] = []
        evidence: list[EvidenceReference] = []

        frontier: list[tuple[str, int, int]] = [(node_type, node_id, 0)]
        visited: set[tuple[str, int]] = {(node_type, node_id)}

        while frontier:
            cur_type, cur_id, depth = frontier.pop(0)
            if depth >= max_depth:
                continue
            for edge in await self.repo.incoming_edges(cur_type, cur_id):
                up_type, up_id = edge.upstream_type, edge.upstream_id
                up_node = await self._resolve_node(up_type, up_id)
                if up_node is None:
                    # A node that no longer exists (or belongs to another
                    # campus) — keep the edge for the audit trail but skip
                    # further traversal.
                    edges.append(self._to_provenance_edge(edge))
                    continue
                edges.append(self._to_provenance_edge(edge))
                if (up_type, up_id) not in visited:
                    visited.add((up_type, up_id))
                    nodes.append(self._to_provenance_node(up_type, up_node))
                    frontier.append((up_type, up_id, depth + 1))

        # Evidence for every node on the path.
        for node in nodes:
            evidence.extend(await self.repo.list_evidence(node.node_type, node.node_id))

        return ProvenanceReport(
            target_type=node_type,
            target_id=node_id,
            target_name=target.name,
            nodes=nodes,
            edges=edges,
            evidence=evidence,
        )

    # ------------------------------------------------------------------
    # Integration hook: migration engine
    # ------------------------------------------------------------------

    async def register_migration_import(
        self,
        *,
        project_id: int,
        run_id: int,
        source_filename: str,
        file_key: str,
        entities: dict[str, int],
        operator_id: Optional[int] = None,
    ) -> ProvenanceReport:
        """Record lineage for a completed migration import.

        Registered graph::

            source file (data_source) ──> import transform (transformation)
                                           │
                                           ├──> asset per entity (data_asset)
                                           └── evidence: migration run

        Every migrated value can then be traced: asset → transformation →
        source file, with the run attached as evidence.
        """
        source = await self.register_source(
            DataSourceCreate(
                name=f"migration:{source_filename}",
                source_type="file",
                external_ref=file_key,
                description=f"Source file for migration project {project_id}",
            )
        )
        transform = await self.register_transformation(
            TransformationCreate(
                name=f"migration-import:{project_id}:{run_id}",
                transform_type="import",
                description=f"Import job for migration project {project_id}",
                definition={"project_id": project_id, "run_id": run_id},
            )
        )
        await self.connect(
            LineageEdgeCreate(
                upstream_type="data_source",
                upstream_id=source.id,
                downstream_type="transformation",
                downstream_id=transform.id,
                edge_type="feeds_into",
                transformation_id=transform.id,
            )
        )
        for entity, count in entities.items():
            asset = await self.register_asset(
                DataAssetCreate(
                    name=f"migration:{entity}:project-{project_id}",
                    asset_type="dataset",
                    ref=f"migration_projects:{project_id}:{entity}",
                    description=f"{count} {entity} records imported from {source_filename}",
                    schema_info={"entity": entity, "imported_count": count},
                )
            )
            await self.connect(
                LineageEdgeCreate(
                    upstream_type="transformation",
                    upstream_id=transform.id,
                    downstream_type="data_asset",
                    downstream_id=asset.id,
                    edge_type="derives_from",
                    transformation_id=transform.id,
                )
            )
            await self.attach_evidence(
                EvidenceReferenceCreate(
                    node_type="data_asset",
                    node_id=asset.id,
                    kind="migration_run",
                    reference=str(run_id),
                    note=f"Migration run {run_id} imported {entity}",
                )
            )
        await self.attach_evidence(
            EvidenceReferenceCreate(
                node_type="data_source",
                node_id=source.id,
                kind="migration_run",
                reference=str(run_id),
                note=f"Source for migration run {run_id}",
            )
        )
        await self.audit.record(
            action="REGISTER_LINEAGE",
            resource_type="migration_project",
            resource_id=str(project_id),
            actor=(
                AuditActor(actor_type=ActorType.USER, actor_id=str(operator_id))
                if operator_id is not None
                else None
            ),
            details={
                "run_id": run_id,
                "source": source_filename,
                "entities": entities,
            },
        )
        return await self._provenance_for_transform(transform.id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _provenance_for_transform(self, transform_id: int) -> ProvenanceReport:
        """Provenance from a transformation's first output asset (or the
        transformation itself when it has no outputs yet)."""
        outs = await self.repo.outgoing_edges("transformation", transform_id)
        if outs:
            first = outs[0]
            return await self.provenance(first.downstream_type, first.downstream_id)
        return await self.provenance("transformation", transform_id)

    async def _resolve_node(self, node_type: str, node_id: int) -> Optional[Any]:
        if node_type == "data_source":
            return await self.repo.get_source(node_id)
        if node_type == "data_asset":
            return await self.repo.get_asset(node_id)
        if node_type == "transformation":
            return await self.repo.get_transformation(node_id)
        return None

    def _to_provenance_node(self, node_type: str, node: Any) -> ProvenanceNode:
        kind = {
            "data_source": "source",
            "data_asset": "asset",
            "transformation": "transformation",
        }[node_type]
        details: dict[str, Any] = {}
        if node_type == "data_source":
            details = {
                "source_type": node.source_type,
                "external_ref": node.external_ref,
                "record_ref": node.record_ref,
            }
        elif node_type == "data_asset":
            details = {
                "asset_type": node.asset_type,
                "ref": node.ref,
            }
        else:
            details = {
                "transform_type": node.transform_type,
            }
        return ProvenanceNode(
            node_type=node_type,
            node_id=node.id,
            name=node.name,
            kind=kind,
            details=details,
        )

    @staticmethod
    def _to_provenance_edge(edge: LineageEdge) -> ProvenanceEdge:
        return ProvenanceEdge(
            upstream_type=edge.upstream_type,
            upstream_id=edge.upstream_id,
            downstream_type=edge.downstream_type,
            downstream_id=edge.downstream_id,
            edge_type=edge.edge_type,
            transformation_id=edge.transformation_id,
        )
