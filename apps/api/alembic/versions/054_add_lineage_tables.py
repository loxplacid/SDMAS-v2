"""Add data lineage foundation tables.

Revision ID: 054_add_lineage_tables
Revises: 053_add_identity_layer
Create Date: 2026-08-17

Adds the data lineage foundation (app/platform/lineage):

- ``lineage_data_sources``          — named source systems/tables/files
- ``lineage_data_assets``           — datasets, metrics, dashboards, reports
- ``lineage_transformations``       — transforms between source and asset
- ``lineage_edges``                 — directed polymorphic edges
- ``lineage_calculation_versions``  — versioned calculation definitions
- ``lineage_evidence_refs``         — evidence pointers (audit, files, runs)

Edges are polymorphic ``(node_type, node_id)`` endpoints (node_type in
``data_source`` / ``data_asset`` / ``transformation``), so the graph can
later span reports, migration runs and reconciliation without re-migration.
JSON columns use the dialect-aware helper (JSONB on PostgreSQL, JSON
elsewhere) mirroring the model ``JSONType`` decorator.

Tenancy: every table carries ``campus_id`` (direct tenant scoping) so the
multi-tenant registry classifies all six as tenant-owned.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "054_add_lineage_tables"
down_revision: str | None = "053_add_identity_layer"
branch_labels: str | None = None
depends_on: str | None = None


def _json_type():
    """JSONB on PostgreSQL, JSON elsewhere — mirrors the model JSONType."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import JSONB

        return JSONB()
    return sa.JSON()


def upgrade() -> None:
    op.create_table(
        "lineage_data_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False, server_default="table"),
        sa.Column("external_ref", sa.String(512), nullable=True),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("record_ref", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_lineage_data_sources_campus_id", "lineage_data_sources", ["campus_id"])
    op.create_index("ix_lineage_data_sources_source_type", "lineage_data_sources", ["source_type"])
    op.create_index(
        "ix_lineage_sources_campus_type_ref",
        "lineage_data_sources",
        ["campus_id", "source_type", "external_ref"],
    )

    op.create_table(
        "lineage_data_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("asset_type", sa.String(30), nullable=False, server_default="dataset"),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("ref", sa.String(255), nullable=True),
        sa.Column("schema_info", _json_type(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_lineage_data_assets_campus_id", "lineage_data_assets", ["campus_id"])
    op.create_index("ix_lineage_data_assets_asset_type", "lineage_data_assets", ["asset_type"])
    op.create_index(
        "ix_lineage_assets_campus_type_ref",
        "lineage_data_assets",
        ["campus_id", "asset_type", "ref"],
    )

    op.create_table(
        "lineage_transformations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("transform_type", sa.String(30), nullable=False, server_default="mapping"),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("definition", _json_type(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_lineage_transformations_campus_id", "lineage_transformations", ["campus_id"]
    )
    op.create_index(
        "ix_lineage_transformations_transform_type",
        "lineage_transformations",
        ["transform_type"],
    )

    op.create_table(
        "lineage_edges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("upstream_type", sa.String(30), nullable=False),
        sa.Column("upstream_id", sa.Integer(), nullable=False),
        sa.Column("downstream_type", sa.String(30), nullable=False),
        sa.Column("downstream_id", sa.Integer(), nullable=False),
        sa.Column("edge_type", sa.String(30), nullable=False, server_default="derives_from"),
        sa.Column(
            "transformation_id",
            sa.Integer(),
            sa.ForeignKey("lineage_transformations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "campus_id",
            "upstream_type",
            "upstream_id",
            "downstream_type",
            "downstream_id",
            "edge_type",
            name="uq_lineage_edge",
        ),
    )
    op.create_index("ix_lineage_edges_campus_id", "lineage_edges", ["campus_id"])
    op.create_index("ix_lineage_edges_upstream_type", "lineage_edges", ["upstream_type"])
    op.create_index("ix_lineage_edges_upstream_id", "lineage_edges", ["upstream_id"])
    op.create_index("ix_lineage_edges_downstream_type", "lineage_edges", ["downstream_type"])
    op.create_index("ix_lineage_edges_downstream_id", "lineage_edges", ["downstream_id"])

    op.create_table(
        "lineage_calculation_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("calc_name", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("formula", sa.String(2000), nullable=False, server_default=""),
        sa.Column("definition", _json_type(), nullable=True),
        sa.Column(
            "asset_id",
            sa.Integer(),
            sa.ForeignKey("lineage_data_assets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("superseded_by", sa.Integer(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("campus_id", "calc_name", "version", name="uq_lineage_calc_version"),
    )
    op.create_index(
        "ix_lineage_calculation_versions_campus_id",
        "lineage_calculation_versions",
        ["campus_id"],
    )
    op.create_index(
        "ix_lineage_calculation_versions_calc_name",
        "lineage_calculation_versions",
        ["calc_name"],
    )

    op.create_table(
        "lineage_evidence_refs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("node_type", sa.String(30), nullable=False),
        sa.Column("node_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False, server_default="audit"),
        sa.Column("reference", sa.String(512), nullable=False),
        sa.Column("checksum", sa.String(128), nullable=True),
        sa.Column("note", sa.String(1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_lineage_evidence_refs_campus_id", "lineage_evidence_refs", ["campus_id"])
    op.create_index("ix_lineage_evidence_refs_node_type", "lineage_evidence_refs", ["node_type"])
    op.create_index("ix_lineage_evidence_refs_node_id", "lineage_evidence_refs", ["node_id"])
    op.create_index("ix_lineage_evidence_refs_kind", "lineage_evidence_refs", ["kind"])
    op.create_index(
        "ix_lineage_evidence_node_kind_ref",
        "lineage_evidence_refs",
        ["node_type", "node_id", "kind", "reference"],
    )


def downgrade() -> None:
    op.drop_table("lineage_evidence_refs")
    op.drop_table("lineage_calculation_versions")
    op.drop_table("lineage_edges")
    op.drop_table("lineage_transformations")
    op.drop_table("lineage_data_assets")
    op.drop_table("lineage_data_sources")
