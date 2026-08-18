"""Add Migration Factory workspace state.

Revision ID: 060_add_migration_factory_tables
Revises: 059_add_extension_tables
Create Date: 2026-08-17

TASK 15 (Migration Factory) extends the existing migration workspace
without replacing it.  All changes are additive:

- New JSON columns on ``migration_projects``:
  ``profile`` (source profiling), ``identity_match`` (deterministic
  legacy->SDMAS matching), ``mapping_versions`` (mapping version
  history), ``verification`` (post-import verification), ``approval``
  (the optional approval gate) and ``cutover`` (cutover state).
- New tenant-owned table ``migration_snapshots`` — immutable point-in-time
  snapshots of a pipeline stage (``dry_run`` / ``verify``), so dry-run
  decisions are evidence, not ephemeral.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "060_add_migration_factory_tables"
down_revision: str | None = "059_add_extension_tables"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("migration_projects") as batch_op:
        batch_op.add_column(sa.Column("profile", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("identity_match", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("mapping_versions", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("verification", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("approval", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("cutover", sa.JSON(), nullable=True))

    op.create_table(
        "migration_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("campus_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_migration_snapshots_campus_id", "migration_snapshots", ["campus_id"])
    op.create_index(
        "ix_migration_snapshots_project_id", "migration_snapshots", ["project_id"]
    )
    op.create_index("ix_migration_snapshots_kind", "migration_snapshots", ["kind"])


def downgrade() -> None:
    op.drop_table("migration_snapshots")
    with op.batch_alter_table("migration_projects") as batch_op:
        batch_op.drop_column("cutover")
        batch_op.drop_column("approval")
        batch_op.drop_column("verification")
        batch_op.drop_column("mapping_versions")
        batch_op.drop_column("identity_match")
        batch_op.drop_column("profile")
