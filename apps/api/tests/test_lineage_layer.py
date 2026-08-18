"""Data lineage foundation tests (TASK 9).

Covers:

- idempotent node registration (sources / assets / transformations)
- directed polymorphic edges (derives_from / feeds_into) + uniqueness
- versioned calculation definitions (current-version supersession)
- evidence references
- provenance traversal: "where did this value come from?"
- migration-import integration hook (lineage recorded on import)
- tenant isolation (campus A can never see / mutate campus B lineage)
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.domains.audit.actors import ActorType, AuditActor
from app.domains.audit.models import AuditLog
from app.multi_tenant.models import TenantContext
from app.platform.lineage.repository import LineageRepository
from app.platform.lineage.schemas import (
    CalculationVersionCreate,
    DataAssetCreate,
    DataSourceCreate,
    EvidenceReferenceCreate,
    LineageEdgeCreate,
    TransformationCreate,
)
from app.platform.lineage.service import LineageService


@pytest.fixture
def tenant_a() -> TenantContext:
    return TenantContext(campus_id=1, institution_id=1, user_id=99)


@pytest.fixture
def tenant_b() -> TenantContext:
    return TenantContext(campus_id=2, institution_id=1, user_id=98)


def _actor(user_id: int = 99) -> AuditActor:
    return AuditActor(actor_type=ActorType.USER, actor_id=str(user_id))


def _source(**overrides) -> DataSourceCreate:
    base = {
        "name": "legacy_erp.students",
        "source_type": "table",
        "external_ref": "legacy_erp.students",
        "description": "Legacy ERP students table",
    }
    base.update(overrides)
    return DataSourceCreate(**base)


def _asset(**overrides) -> DataAssetCreate:
    base = {
        "name": "Fee Collection Rate",
        "asset_type": "metric",
        "ref": "analytics.fee_collection_rate",
    }
    base.update(overrides)
    return DataAssetCreate(**base)


def _transform(**overrides) -> TransformationCreate:
    base = {
        "name": "aggregate-fee-collection",
        "transform_type": "aggregation",
        "description": "Aggregates payments into the collection rate",
    }
    base.update(overrides)
    return TransformationCreate(**base)


# ---------------------------------------------------------------------------
# Node registration (idempotent)
# ---------------------------------------------------------------------------


class TestNodeRegistration:
    async def test_register_source_creates_and_is_idempotent(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LineageService(db_session, tenant_a)
        src = await svc.register_source(_source(), actor=_actor())
        assert src.id is not None
        assert src.campus_id == 1
        assert src.source_type == "table"

        again = await svc.register_source(_source(), actor=_actor())
        assert again.id == src.id  # idempotent — no duplicate row

        sources, total = await LineageRepository(db_session, tenant_a).list_sources()
        assert total == 1

    async def test_register_asset_and_transformation_idempotent(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LineageService(db_session, tenant_a)
        asset = await svc.register_asset(_asset(), actor=_actor())
        assert await svc.register_asset(_asset(), actor=_actor()) is not None
        assert asset.asset_type == "metric"

        tf = await svc.register_transformation(_transform(), actor=_actor())
        again = await svc.register_transformation(_transform(), actor=_actor())
        assert again.id == tf.id

    async def test_rejects_invalid_types(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LineageService(db_session, tenant_a)
        with pytest.raises(ValidationError):
            await svc.register_source(_source(source_type="spaceship"))
        with pytest.raises(ValidationError):
            await svc.register_asset(_asset(asset_type="hologram"))
        with pytest.raises(ValidationError):
            await svc.register_transformation(_transform(transform_type="magic"))

    async def test_registration_is_audited(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LineageService(db_session, tenant_a)
        await svc.register_source(_source(), actor=_actor())
        entries = (await db_session.execute(select(AuditLog))).scalars().all()
        assert [e.action for e in entries] == ["CREATE"]
        assert entries[0].resource_type == "lineage_data_source"
        assert entries[0].campus_id == 1


# ---------------------------------------------------------------------------
# Edges
# ---------------------------------------------------------------------------


class TestEdges:
    async def test_connect_creates_directed_edge(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LineageService(db_session, tenant_a)
        src = await svc.register_source(_source(), actor=_actor())
        tf = await svc.register_transformation(_transform(), actor=_actor())
        edge = await svc.connect(
            LineageEdgeCreate(
                upstream_type="data_source",
                upstream_id=src.id,
                downstream_type="transformation",
                downstream_id=tf.id,
                edge_type="feeds_into",
                transformation_id=tf.id,
            ),
            actor=_actor(),
        )
        assert edge.campus_id == 1
        assert edge.upstream_type == "data_source"

        # Idempotent: same pair + edge_type returns the same row.
        again = await svc.connect(
            LineageEdgeCreate(
                upstream_type="data_source",
                upstream_id=src.id,
                downstream_type="transformation",
                downstream_id=tf.id,
                edge_type="feeds_into",
                transformation_id=tf.id,
            ),
            actor=_actor(),
        )
        assert again.id == edge.id

    async def test_rejects_bad_node_or_edge_type(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LineageService(db_session, tenant_a)
        with pytest.raises(ValidationError):
            await svc.connect(
                LineageEdgeCreate(
                    upstream_type="dashboard",  # not a node type
                    upstream_id=1,
                    downstream_type="data_asset",
                    downstream_id=2,
                )
            )
        with pytest.raises(ValidationError):
            await svc.connect(
                LineageEdgeCreate(
                    upstream_type="data_source",
                    upstream_id=1,
                    downstream_type="data_asset",
                    downstream_id=2,
                    edge_type="teleports",
                )
            )

    async def test_incoming_and_outgoing_edges(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LineageService(db_session, tenant_a)
        src = await svc.register_source(_source(), actor=_actor())
        asset = await svc.register_asset(_asset(), actor=_actor())
        await svc.connect(
            LineageEdgeCreate(
                upstream_type="data_source",
                upstream_id=src.id,
                downstream_type="data_asset",
                downstream_id=asset.id,
            ),
            actor=_actor(),
        )
        repo = LineageRepository(db_session, tenant_a)
        incoming = await repo.incoming_edges("data_asset", asset.id)
        outgoing = await repo.outgoing_edges("data_source", src.id)
        assert len(incoming) == 1
        assert len(outgoing) == 1
        assert incoming[0].upstream_id == src.id


# ---------------------------------------------------------------------------
# Calculation versioning
# ---------------------------------------------------------------------------


class TestCalculationVersioning:
    async def test_versions_supersede_previous(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LineageService(db_session, tenant_a)
        v1 = await svc.add_calculation_version(
            CalculationVersionCreate(
                calc_name="fee_collection_rate",
                formula="collected / billed",
            ),
            actor=_actor(),
        )
        assert v1.version == 1
        assert v1.is_current is True

        v2 = await svc.add_calculation_version(
            CalculationVersionCreate(
                calc_name="fee_collection_rate",
                formula="collected_this_period / billed_this_period",
                definition={"numerator": "collected", "denominator": "billed"},
            ),
            actor=_actor(),
        )
        assert v2.version == 2
        assert v2.is_current is True

        # v1 superseded.
        v1_ref = (await svc.calculation_history("fee_collection_rate"))[1]
        assert v1_ref.is_current is False
        assert v1_ref.superseded_by == v2.id

        current = await svc.current_calculation("fee_collection_rate")
        assert current is not None
        assert current.version == 2

    async def test_history_ordered_newest_first(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LineageService(db_session, tenant_a)
        await svc.add_calculation_version(
            CalculationVersionCreate(calc_name="attendance_rate", formula="a"), actor=_actor()
        )
        await svc.add_calculation_version(
            CalculationVersionCreate(calc_name="attendance_rate", formula="b"), actor=_actor()
        )
        history = await svc.calculation_history("attendance_rate")
        versions = [h.version for h in history]
        assert versions == [2, 1]  # newest first


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


class TestEvidence:
    async def test_attach_and_list_evidence(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LineageService(db_session, tenant_a)
        asset = await svc.register_asset(_asset(), actor=_actor())
        ev = await svc.attach_evidence(
            EvidenceReferenceCreate(
                node_type="data_asset",
                node_id=asset.id,
                kind="audit",
                reference="42",
                note="Audit entry for the underlying calculation",
            ),
            actor=_actor(),
        )
        assert ev.campus_id == 1
        listed = await LineageRepository(db_session, tenant_a).list_evidence("data_asset", asset.id)
        assert [e.id for e in listed] == [ev.id]

    async def test_rejects_bad_kind(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LineageService(db_session, tenant_a)
        with pytest.raises(ValidationError):
            await svc.attach_evidence(
                EvidenceReferenceCreate(
                    node_type="data_asset",
                    node_id=1,
                    kind="gossip",
                    reference="x",
                )
            )


# ---------------------------------------------------------------------------
# Provenance: "where did this value come from?"
# ---------------------------------------------------------------------------


class TestProvenance:
    async def test_full_lineage_path(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LineageService(db_session, tenant_a)
        # Dashboard metric -> analytic dataset -> transformation -> source table.
        metric = await svc.register_asset(_asset(asset_type="metric"), actor=_actor())
        dataset = await svc.register_asset(
            _asset(name="fee_analytics", asset_type="dataset", ref="analytics.fee_dataset"),
            actor=_actor(),
        )
        tf = await svc.register_transformation(_transform(), actor=_actor())
        source = await svc.register_source(_source(), actor=_actor())

        # metric derives_from dataset
        await svc.connect(
            LineageEdgeCreate(
                upstream_type="data_asset",
                upstream_id=dataset.id,
                downstream_type="data_asset",
                downstream_id=metric.id,
            ),
            actor=_actor(),
        )
        # dataset derives_from transformation
        await svc.connect(
            LineageEdgeCreate(
                upstream_type="transformation",
                upstream_id=tf.id,
                downstream_type="data_asset",
                downstream_id=dataset.id,
                transformation_id=tf.id,
            ),
            actor=_actor(),
        )
        # transformation feeds from source
        await svc.connect(
            LineageEdgeCreate(
                upstream_type="data_source",
                upstream_id=source.id,
                downstream_type="transformation",
                downstream_id=tf.id,
                edge_type="feeds_into",
                transformation_id=tf.id,
            ),
            actor=_actor(),
        )
        # evidence on the source
        await svc.attach_evidence(
            EvidenceReferenceCreate(
                node_type="data_source",
                node_id=source.id,
                kind="source_record",
                reference="legacy_erp.students:REC-1",
            ),
            actor=_actor(),
        )

        report = await svc.provenance("data_asset", metric.id)
        assert report.target_name == "Fee Collection Rate"

        kinds = {n.kind for n in report.nodes}
        assert kinds == {"asset", "transformation", "source"}
        assert len(report.edges) == 3
        # Evidence surfaced on the path.
        assert any(e.kind == "source_record" for e in report.evidence)

        # The source table appears in the walk.
        source_nodes = [n for n in report.nodes if n.kind == "source"]
        assert len(source_nodes) == 1
        assert source_nodes[0].name == "legacy_erp.students"

    async def test_provenance_missing_target_404(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LineageService(db_session, tenant_a)
        with pytest.raises(NotFoundError):
            await svc.provenance("data_asset", 9999)

    async def test_provenance_bad_type(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LineageService(db_session, tenant_a)
        with pytest.raises(ValidationError):
            await svc.provenance("planets", 1)

    async def test_provenance_cycle_safe(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        """A graph cycle must not hang the walk (visited set bounds it)."""
        svc = LineageService(db_session, tenant_a)
        a = await svc.register_asset(
            _asset(name="A", asset_type="dataset", ref="a"), actor=_actor()
        )
        b = await svc.register_asset(
            _asset(name="B", asset_type="dataset", ref="b"), actor=_actor()
        )
        # a <-> b cycle
        await svc.connect(
            LineageEdgeCreate(
                upstream_type="data_asset",
                upstream_id=a.id,
                downstream_type="data_asset",
                downstream_id=b.id,
            )
        )
        await svc.connect(
            LineageEdgeCreate(
                upstream_type="data_asset",
                upstream_id=b.id,
                downstream_type="data_asset",
                downstream_id=a.id,
            )
        )
        report = await svc.provenance("data_asset", a.id, max_depth=10)
        assert report.target_id == a.id
        assert len(report.nodes) == 2  # a + b, no infinite growth


# ---------------------------------------------------------------------------
# Migration-import integration
# ---------------------------------------------------------------------------


class TestMigrationIntegration:
    async def test_register_migration_import_records_lineage(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LineageService(db_session, tenant_a)
        report = await svc.register_migration_import(
            project_id=7,
            run_id=12,
            source_filename="students_2024.csv",
            file_key="1/students_2024.csv",
            entities={"students": 120, "fees": 340},
            operator_id=99,
        )

        # Provenance from the first output asset reaches the source file.
        kinds = {n.kind for n in report.nodes}
        assert "source" in kinds and "transformation" in kinds and "asset" in kinds
        sources = [n for n in report.nodes if n.kind == "source"]
        assert sources
        assert sources[0].name == "migration:students_2024.csv"

        # Both entities registered as assets.
        repo = LineageRepository(db_session, tenant_a)
        assets, total = await repo.list_assets()
        assert total == 2
        refs = {a.ref for a in assets}
        assert "migration_projects:7:students" in refs
        assert "migration_projects:7:fees" in refs

        # Evidence references to the migration run exist.
        evidence = await repo.list_evidence("data_source", sources[0].node_id)
        assert any(e.kind == "migration_run" and e.reference == "12" for e in evidence)

        # Audit recorded the registration.
        entries = (await db_session.execute(select(AuditLog))).scalars().all()
        assert any(e.action == "REGISTER_LINEAGE" for e in entries)

    async def test_migration_import_repeat_is_idempotent(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LineageService(db_session, tenant_a)
        await svc.register_migration_import(
            project_id=7,
            run_id=12,
            source_filename="students_2024.csv",
            file_key="1/students_2024.csv",
            entities={"students": 120},
        )
        await svc.register_migration_import(
            project_id=7,
            run_id=12,
            source_filename="students_2024.csv",
            file_key="1/students_2024.csv",
            entities={"students": 120},
        )
        repo = LineageRepository(db_session, tenant_a)
        sources, _ = await repo.list_sources()
        assets, _ = await repo.list_assets()
        assert len(sources) == 1  # idempotent
        assert len(assets) == 1


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    async def test_cross_tenant_nodes_invisible(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = LineageService(db_session, tenant_a)
        svc_b = LineageService(db_session, tenant_b)
        src = await svc_a.register_source(_source(), actor=_actor())
        assert src.campus_id == 1

        # Campus B cannot resolve campus A's source.
        with pytest.raises(NotFoundError):
            await svc_b.provenance("data_source", src.id)

        # And B's list only sees B's own nodes.
        b_src = await svc_b.register_source(
            _source(name="b_source", external_ref="b"), actor=_actor()
        )
        sources_b, total_b = await LineageRepository(db_session, tenant_b).list_sources()
        assert total_b == 1
        assert sources_b[0].id == b_src.id

    async def test_cross_tenant_edges_isolated(
        self,
        db_session: AsyncSession,
        tenant_a: TenantContext,
        tenant_b: TenantContext,
    ) -> None:
        svc_a = LineageService(db_session, tenant_a)
        a_src = await svc_a.register_source(_source(), actor=_actor())
        a_asset = await svc_a.register_asset(_asset(), actor=_actor())
        await svc_a.connect(
            LineageEdgeCreate(
                upstream_type="data_source",
                upstream_id=a_src.id,
                downstream_type="data_asset",
                downstream_id=a_asset.id,
            ),
            actor=_actor(),
        )

        # Campus B's view of A's asset id sees nothing.
        repo_b = LineageRepository(db_session, tenant_b)
        assert await repo_b.incoming_edges("data_asset", a_asset.id) == []
        assert await repo_b.get_asset(a_asset.id) is None

    async def test_cross_tenant_calculation_isolated(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = LineageService(db_session, tenant_a)
        svc_b = LineageService(db_session, tenant_b)
        await svc_a.add_calculation_version(
            CalculationVersionCreate(calc_name="fee_collection_rate", formula="x"),
            actor=_actor(),
        )
        # Same calc name in campus B is a separate lineage.
        v = await svc_b.add_calculation_version(
            CalculationVersionCreate(calc_name="fee_collection_rate", formula="y"),
            actor=_actor(),
        )
        assert v.version == 1  # B's own history starts fresh
        current_a = await svc_a.current_calculation("fee_collection_rate")
        assert current_a is not None and current_a.formula == "x"

    async def test_repository_denies_unscoped_access(self, db_session: AsyncSession) -> None:
        from app.core.exceptions import AuthorizationError

        repo = LineageRepository(db_session)
        with pytest.raises(AuthorizationError):
            await repo.list_sources()

        platform_repo = LineageRepository(db_session, TenantContext(user_id=1, platform=True))
        sources, total = await platform_repo.list_sources()
        assert total == 0
