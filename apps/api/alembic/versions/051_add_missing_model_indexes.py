"""Add model-declared indexes missing from the schema.

Revision ID: 051_add_missing_model_indexes
Revises: 050_add_missing_tenant_fks
Create Date: 2026-08-16

The ORM models declare ``migration_projects.job_id`` and
``refresh_tokens.is_revoked`` with ``index=True``, but the migrations that
introduced the columns never created the indexes.  Alembic autogenerate
reports them as "added index".  Corrective migration creates both (plain
CREATE INDEX — portable across PostgreSQL and SQLite).
"""

from alembic import op

revision: str = "051_add_missing_model_indexes"
down_revision: str | None = "050_add_missing_tenant_fks"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_index("ix_migration_projects_job_id", "migration_projects", ["job_id"])
    op.create_index("ix_refresh_tokens_is_revoked", "refresh_tokens", ["is_revoked"])


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_is_revoked", table_name="refresh_tokens")
    op.drop_index("ix_migration_projects_job_id", table_name="migration_projects")
