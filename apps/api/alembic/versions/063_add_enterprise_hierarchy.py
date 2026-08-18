"""Add enterprise organization hierarchy (organization → group → region → campus).

Revision ID: 063_add_enterprise_hierarchy
Revises: 062_add_exception_tables
Create Date: 2026-08-18

TASK 21 (Enterprise Organization Hierarchy) extends the existing
institution → campus model with two aggregation levels *above* the campus:

- ``school_groups``       — an operating unit of an organization (a legal
  ``institutions`` row) that groups several regions/campuses under one
  group administrator.
- ``regions``             — a geographic region of one or more campuses,
  normally under a school group (``school_group_id`` nullable so an
  organization may skip the group level).

These are organizational aggregations, NOT tenant units: the campus
remains the data-isolation boundary and every tenant-owned row keeps its
``campus_id``.  Group/region/organization administrators gain cross-campus
scope only *within their subtree* via a new ``organization_assignments``
table (user → node assignment); that subtree is enforced by the tenant
context, never by the role alone.

The migration also:

- links ``campuses`` to ``school_groups`` / ``regions`` (nullable FKs,
  ``SET NULL`` on delete so a group/region can be removed without orphaning
  campuses);
- adds a denormalized nullable ``departments.campus_id`` (derived from the
  school chain) so department-scoped authorization needs no join, and
  backfills it from the existing school/campus chain;
- backfills ``campuses.school_group_id`` from the campus's region where the
  region is linked to a group;
- creates ``organization_assignments`` with a ``(user_id, node_type,
  node_id)`` unique constraint so a user can hold at most one assignment
  per node.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "063_add_enterprise_hierarchy"
down_revision: str | None = "062_add_exception_tables"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # School groups (aggregation above campuses, below an organization)
    # ------------------------------------------------------------------
    op.create_table(
        "school_groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_school_groups_institution_id", "school_groups", ["institution_id"]
    )

    # ------------------------------------------------------------------
    # Regions (one or more campuses, normally under a school group)
    # ------------------------------------------------------------------
    op.create_table(
        "regions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("school_group_id", sa.Integer(), nullable=True),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["school_group_id"], ["school_groups.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_regions_school_group_id", "regions", ["school_group_id"])
    op.create_index("ix_regions_institution_id", "regions", ["institution_id"])

    # ------------------------------------------------------------------
    # Link campuses into the hierarchy (nullable, SET NULL on delete).
    # ``batch_alter_table`` rebuilds the table on SQLite (which cannot
    # ALTER-ADD constraints) and emits plain ALTER TABLE on PostgreSQL.
    # ------------------------------------------------------------------
    with op.batch_alter_table("campuses") as batch:
        batch.add_column(
            sa.Column("school_group_id", sa.Integer(), nullable=True)
        )
        batch.add_column(
            sa.Column("region_id", sa.Integer(), nullable=True)
        )
        batch.create_foreign_key(
            "fk_campuses_school_group_id",
            "school_groups",
            ["school_group_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "fk_campuses_region_id",
            "regions",
            ["region_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_campuses_school_group_id", ["school_group_id"])
        batch.create_index("ix_campuses_region_id", ["region_id"])

    # Backfill campuses.school_group_id from the region chain so existing
    # regions that already belong to a group keep their subtree reachable.
    op.execute(
        sa.text(
            "UPDATE campuses SET school_group_id = "
            "(SELECT regions.school_group_id FROM regions "
            " WHERE regions.id = campuses.region_id AND regions.school_group_id IS NOT NULL) "
            "WHERE EXISTS (SELECT 1 FROM regions "
            "            WHERE regions.id = campuses.region_id "
            "              AND regions.school_group_id IS NOT NULL)"
        )
    )

    # ------------------------------------------------------------------
    # Denormalized campus link on departments (backfilled from schools)
    # ------------------------------------------------------------------
    with op.batch_alter_table("departments") as batch:
        batch.add_column(
            sa.Column("campus_id", sa.Integer(), nullable=True)
        )
        batch.create_foreign_key(
            "fk_departments_campus_id",
            "campuses",
            ["campus_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_index("ix_departments_campus_id", ["campus_id"])

    op.execute(
        sa.text(
            "UPDATE departments SET campus_id = "
            "(SELECT schools.campus_id FROM schools "
            " WHERE schools.id = departments.school_id)"
        )
    )

    # ------------------------------------------------------------------
    # Organization hierarchy assignments (admin → subtree)
    # ------------------------------------------------------------------
    op.create_table(
        "organization_assignments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("node_type", sa.String(20), nullable=False, server_default="campus"),
        sa.Column("node_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="admin"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "node_type", "node_id", name="uq_org_assignment"
        ),
    )
    op.create_index(
        "ix_organization_assignments_user_id",
        "organization_assignments",
        ["user_id"],
    )
    op.create_index(
        "ix_organization_assignments_node_id",
        "organization_assignments",
        ["node_id"],
    )


def downgrade() -> None:
    op.drop_table("organization_assignments")

    with op.batch_alter_table("departments") as batch:
        batch.drop_index("ix_departments_campus_id")
        batch.drop_constraint("fk_departments_campus_id", type_="foreignkey")
        batch.drop_column("campus_id")

    with op.batch_alter_table("campuses") as batch:
        batch.drop_index("ix_campuses_region_id")
        batch.drop_index("ix_campuses_school_group_id")
        batch.drop_constraint("fk_campuses_region_id", type_="foreignkey")
        batch.drop_constraint("fk_campuses_school_group_id", type_="foreignkey")
        batch.drop_column("region_id")
        batch.drop_column("school_group_id")

    op.drop_table("regions")
    op.drop_table("school_groups")
