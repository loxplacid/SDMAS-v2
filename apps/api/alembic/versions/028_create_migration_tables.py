"""create migration tracking tables: migration_runs, migration_logs, migration_mappings

Revision ID: 028_create_migration_tables
Revises: 027_create_billing
Create Date: 2026-07-31 07:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "028_create_migration"
down_revision: str | None = "027_create_billing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Migration Runs ─────────────────────────────────────────────────
    op.create_table(
        "migration_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("total_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warnings", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_dry_run", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_migration_runs_entity", "migration_runs", ["entity_type"])
    op.create_index("ix_migration_runs_status", "migration_runs", ["status"])

    # ── Migration Logs (row-level audit trail) ─────────────────────────
    op.create_table(
        "migration_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(10), nullable=False),
        sa.Column("legacy_id", sa.String(255), nullable=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_subtype", sa.String(50), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "legacy_id", "entity_subtype", name="uq_migration_log_entry"),
    )
    op.create_index("ix_migration_logs_run", "migration_logs", ["run_id"])
    op.create_index("ix_migration_logs_level", "migration_logs", ["level"])

    # ── ID Mappings (legacy → SDMAS) ───────────────────────────────────
    op.create_table(
        "migration_mappings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("legacy_id", sa.String(255), nullable=False),
        sa.Column("sdmas_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_type", "legacy_id", name="uq_migration_mapping_entity_legacy"),
    )
    op.create_index("ix_migration_mappings_run", "migration_mappings", ["run_id"])
    op.create_index("ix_migration_mappings_entity", "migration_mappings", ["entity_type"])


def downgrade() -> None:
    op.drop_table("migration_mappings")
    op.drop_table("migration_logs")
    op.drop_table("migration_runs")
