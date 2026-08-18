"""Data lineage foundation — ORM models.

Six tenant-scoped tables implement the lineage graph:

- ``lineage_data_sources``        — named source systems/tables/records
- ``lineage_data_assets``         — datasets, metrics, dashboards, reports
- ``lineage_transformations``     — transforms between source and asset
- ``lineage_edges``               — directed, polymorphic edges
- ``lineage_calculation_versions``— versioned calculation definitions
- ``lineage_evidence_refs``       — evidence pointers (audit, files, runs)

Edges are *polymorphic*: an edge has ``upstream_type``/``upstream_id`` and
``downstream_type``/``downstream_id`` where the type is one of ``data_source``,
``data_asset``, ``transformation``.  This keeps the graph open to future
node kinds (reports, migration runs, reconciliation batches) without
re-migrating the edge table.

Tenancy: every table carries ``campus_id`` (direct tenant scoping — the
multi-tenant registry classifies them ``TENANT_DIRECT`` automatically), so
the tenant-scoped repository pins every query to the caller's campus.
"""

from __future__ import annotations

import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base
from app.infrastructure.types import JSONType

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Node kinds an edge endpoint may reference.
NODE_TYPES = frozenset({"data_source", "data_asset", "transformation"})

#: Edge semantics.
EDGE_DERIVES = "derives_from"  # downstream derived from upstream
EDGE_FEEDS = "feeds_into"  # upstream feeds downstream
EDGE_EDGE_TYPES = frozenset({EDGE_DERIVES, EDGE_FEEDS})

#: Data source kinds.
SOURCE_TABLE = "table"
SOURCE_FILE = "file"
SOURCE_SYSTEM = "system"
SOURCE_RECORD = "record"
SOURCE_API = "api"
SOURCE_TYPES = frozenset({SOURCE_TABLE, SOURCE_FILE, SOURCE_SYSTEM, SOURCE_RECORD, SOURCE_API})

#: Data asset kinds.
ASSET_DATASET = "dataset"
ASSET_METRIC = "metric"
ASSET_DASHBOARD = "dashboard"
ASSET_REPORT = "report"
ASSET_EXPORT = "export"
ASSET_TYPES = frozenset({ASSET_DATASET, ASSET_METRIC, ASSET_DASHBOARD, ASSET_REPORT, ASSET_EXPORT})

#: Transformation kinds.
TRANSFORM_SQL = "sql"
TRANSFORM_MAPPING = "mapping"
TRANSFORM_AGGREGATION = "aggregation"
TRANSFORM_CALCULATION = "calculation"
TRANSFORM_IMPORT = "import"
TRANSFORM_DEDUP = "dedup"
TRANSFORM_TYPES = frozenset(
    {
        TRANSFORM_SQL,
        TRANSFORM_MAPPING,
        TRANSFORM_AGGREGATION,
        TRANSFORM_CALCULATION,
        TRANSFORM_IMPORT,
        TRANSFORM_DEDUP,
    }
)

#: Evidence kinds.
EVIDENCE_AUDIT = "audit"
EVIDENCE_FILE = "file"
EVIDENCE_MIGRATION_RUN = "migration_run"
EVIDENCE_REPORT = "report"
EVIDENCE_SOURCE_RECORD = "source_record"
EVIDENCE_TYPES = frozenset(
    {
        EVIDENCE_AUDIT,
        EVIDENCE_FILE,
        EVIDENCE_MIGRATION_RUN,
        EVIDENCE_REPORT,
        EVIDENCE_SOURCE_RECORD,
    }
)


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class DataSource(Base):
    """A named source of data (tenant-scoped): system, table, file, record."""

    __tablename__ = "lineage_data_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default=SOURCE_TABLE, index=True
    )
    #: External reference — e.g. ``legacy_erp.students``, a file key, a
    #: table name, or a record id within a source.
    external_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    #: Optional pointer to a concrete record within the source (e.g. the
    #: legacy row that produced a value).
    record_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        Index(
            "ix_lineage_sources_campus_type_ref",
            "campus_id",
            "source_type",
            "external_ref",
        ),
    )

    def __repr__(self) -> str:
        return f"<DataSource id={self.id} name={self.name!r} type={self.source_type}>"


class DataAsset(Base):
    """A dataset, metric, dashboard, report, or export (tenant-scoped)."""

    __tablename__ = "lineage_data_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default=ASSET_DATASET, index=True
    )
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    #: Optional pointer to the concrete object this asset represents
    #: (e.g. ``report_definitions:{id}``, ``migration_projects:{id}``).
    ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    #: Schema/columns the asset exposes (informational, JSON).
    schema_info: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (Index("ix_lineage_assets_campus_type_ref", "campus_id", "asset_type", "ref"),)

    def __repr__(self) -> str:
        return f"<DataAsset id={self.id} name={self.name!r} type={self.asset_type}>"


class Transformation(Base):
    """A transformation step between a source and an asset (tenant-scoped)."""

    __tablename__ = "lineage_transformations"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    transform_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default=TRANSFORM_MAPPING, index=True
    )
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    #: Machine-readable definition of the transform (SQL text, mapping
    #: config, aggregation spec).  Informational — not executed here.
    definition: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    def __repr__(self) -> str:
        return f"<Transformation id={self.id} name={self.name!r} type={self.transform_type}>"


class LineageEdge(Base):
    """A directed edge between two lineage nodes (tenant-scoped).

    Polymorphic endpoints: ``(upstream_type, upstream_id)`` →
    ``(downstream_type, downstream_id)`` where the type is one of
    ``data_source`` / ``data_asset`` / ``transformation``.
    """

    __tablename__ = "lineage_edges"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    upstream_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    upstream_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    downstream_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    downstream_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    #: derives_from | feeds_into (semantic direction hint).
    edge_type: Mapped[str] = mapped_column(String(30), nullable=False, default=EDGE_DERIVES)
    #: Optional transformation that produced the downstream node.
    transformation_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("lineage_transformations.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        UniqueConstraint(
            "campus_id",
            "upstream_type",
            "upstream_id",
            "downstream_type",
            "downstream_id",
            "edge_type",
            name="uq_lineage_edge",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<LineageEdge id={self.id} {self.upstream_type}:{self.upstream_id} "
            f"-> {self.downstream_type}:{self.downstream_id} [{self.edge_type}]>"
        )


class CalculationVersion(Base):
    """A versioned calculation / metric definition (tenant-scoped)."""

    __tablename__ = "lineage_calculation_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    #: Stable calculation name (e.g. ``fee_collection_rate``).
    calc_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    #: Human-readable formula/definition.
    formula: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    #: Structured definition (JSON) for machine consumption.
    definition: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    #: Optional pointer to the data asset this calculation feeds.
    asset_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("lineage_data_assets.id", ondelete="SET NULL"), nullable=True
    )
    #: Optional pointer to the asset that superseded this version.
    superseded_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        UniqueConstraint("campus_id", "calc_name", "version", name="uq_lineage_calc_version"),
    )

    def __repr__(self) -> str:
        return (
            f"<CalculationVersion id={self.id} {self.calc_name} "
            f"v{self.version} current={self.is_current}>"
        )


class EvidenceReference(Base):
    """A pointer to evidence for a lineage node (tenant-scoped).

    Evidence is not copied into this table — it stays in its source of
    truth (audit log, file storage, migration run, report) and is
    referenced by ``kind`` + ``reference``.
    """

    __tablename__ = "lineage_evidence_refs"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    node_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    node_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(
        String(30), nullable=False, default=EVIDENCE_AUDIT, index=True
    )
    #: Reference into the evidence source (audit entry id, file key,
    #: migration run id, report id, source record id).
    reference: Mapped[str] = mapped_column(String(512), nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        Index(
            "ix_lineage_evidence_node_kind_ref",
            "node_type",
            "node_id",
            "kind",
            "reference",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<EvidenceReference id={self.id} node={self.node_type}:{self.node_id} "
            f"kind={self.kind} ref={self.reference!r}>"
        )
