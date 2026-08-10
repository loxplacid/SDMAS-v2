"""add migration_projects table + migration_runs project linkage

D2 — Migration Center workspace.  Adds the tenant-scoped ``migration_projects``
table (upload → discover → map → validate → import → reconcile → report) and
back-links ``migration_runs`` to its owning project + campus so worker-executed
runs stay tenant-scoped.

Revision ID: 043_add_migration_projects
Revises: 042_merge_migration_heads
Create Date: 2026-08-10 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "043_add_migration_projects"
down_revision: str | Sequence[str] | None = "042_merge_migration_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "migration_projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campus_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("source_system", sa.String(100), nullable=False, server_default="Generic CSV"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("file_key", sa.String(512), nullable=True),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("file_mime", sa.String(100), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("discovery", sa.JSON(), nullable=True),
        sa.Column("mapping", sa.JSON(), nullable=True),
        sa.Column("validation", sa.JSON(), nullable=True),
        sa.Column("reconciliation", sa.JSON(), nullable=True),
        sa.Column("records_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_imported", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_rejected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warnings", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("operator_id", sa.Integer(), nullable=True),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_migration_projects_campus_id", "migration_projects", ["campus_id"])
    op.create_index("ix_migration_projects_status", "migration_projects", ["status"])
    op.create_index("ix_migration_projects_operator_id", "migration_projects", ["operator_id"])
    op.create_index("ix_migration_projects_run_id", "migration_projects", ["run_id"])

    # Back-link runs to their owning project + campus (nullable, additive).
    op.add_column(
        "migration_runs",
        sa.Column("project_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "migration_runs",
        sa.Column("campus_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_migration_runs_project_id", "migration_runs", ["project_id"])
    op.create_index("ix_migration_runs_campus_id", "migration_runs", ["campus_id"])


def downgrade() -> None:
    op.drop_index("ix_migration_runs_campus_id", table_name="migration_runs")
    op.drop_index("ix_migration_runs_project_id", table_name="migration_runs")
    op.drop_column("migration_runs", "campus_id")
    op.drop_column("migration_runs", "project_id")
    op.drop_index("ix_migration_projects_run_id", table_name="migration_projects")
    op.drop_index("ix_migration_projects_operator_id", table_name="migration_projects")
    op.drop_index("ix_migration_projects_status", table_name="migration_projects")
    op.drop_index("ix_migration_projects_campus_id", table_name="migration_projects")
    op.drop_table("migration_projects")
