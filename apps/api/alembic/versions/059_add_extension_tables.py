"""Add zero-fork extension tables.

Revision ID: 059_add_extension_tables
Revises: 058_add_audit_chain_tables
Create Date: 2026-08-17

Adds the controlled extension system (app/platform/extensions):

- ``extension_definitions`` — the registry entry: stable ``extension_id``
  business key (UNIQUE per campus), provider metadata, lifecycle status,
  and the core compatibility range
- ``extension_versions``    — immutable manifest snapshots (the declared
  contract: permissions, routes, events, config schema, migrations,
  frontend, policy), versioned per extension
- ``extension_grants``      — approved permissions (the authorization
  gate: enabling an extension requires a grant for every permission its
  manifest declares; extensions cannot grant themselves capabilities)
- ``extension_configs``     — validated configuration (values must match
  the manifest's declared config schema; one row per extension)

All four tables carry ``campus_id`` (direct tenant scoping).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "059_add_extension_tables"
down_revision: str | None = "058_add_audit_chain_tables"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "extension_definitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("extension_id", sa.String(80), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("provider", sa.String(255), nullable=False),
        sa.Column("homepage", sa.String(500), nullable=True),
        sa.Column("license", sa.String(100), nullable=True),
        sa.Column("core_compat", sa.String(120), nullable=True),
        sa.Column("current_version", sa.String(40), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="registered"),
        sa.Column("created_by", sa.Integer(), nullable=True),
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
        sa.UniqueConstraint("campus_id", "extension_id", name="uq_extension_definition_key"),
    )
    op.create_index("ix_extension_definitions_campus_id", "extension_definitions", ["campus_id"])
    op.create_index("ix_extension_definitions_status", "extension_definitions", ["status"])

    op.create_table(
        "extension_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "extension_def_id",
            sa.Integer(),
            sa.ForeignKey("extension_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("installed_by", sa.Integer(), nullable=True),
        sa.Column("installed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("extension_def_id", "version", name="uq_extension_version_number"),
    )
    op.create_index("ix_extension_versions_campus_id", "extension_versions", ["campus_id"])
    op.create_index(
        "ix_extension_versions_extension_def_id", "extension_versions", ["extension_def_id"]
    )
    op.create_index("ix_extension_versions_status", "extension_versions", ["status"])

    op.create_table(
        "extension_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "extension_def_id",
            sa.Integer(),
            sa.ForeignKey("extension_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("permission", sa.String(80), nullable=False),
        sa.Column("scope", sa.String(40), nullable=False),
        sa.Column("granted_by", sa.Integer(), nullable=True),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("extension_def_id", "permission", name="uq_extension_grant_permission"),
    )
    op.create_index("ix_extension_grants_campus_id", "extension_grants", ["campus_id"])
    op.create_index(
        "ix_extension_grants_extension_def_id", "extension_grants", ["extension_def_id"]
    )
    op.create_index("ix_extension_grants_scope", "extension_grants", ["scope"])

    op.create_table(
        "extension_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "extension_def_id",
            sa.Integer(),
            sa.ForeignKey("extension_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("schema_version", sa.String(40), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column(
            "validated_at",
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
        sa.UniqueConstraint("extension_def_id", name="uq_extension_config_one_per_extension"),
    )
    op.create_index("ix_extension_configs_campus_id", "extension_configs", ["campus_id"])
    op.create_index(
        "ix_extension_configs_extension_def_id", "extension_configs", ["extension_def_id"]
    )


def downgrade() -> None:
    op.drop_table("extension_configs")
    op.drop_table("extension_grants")
    op.drop_table("extension_versions")
    op.drop_table("extension_definitions")
