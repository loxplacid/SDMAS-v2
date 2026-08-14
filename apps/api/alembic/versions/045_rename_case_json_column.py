"""rename case_events/case_evidence metadata column to data

Migration 040 created the JSON payload column as ``metadata`` on both
``case_events`` and ``case_evidence``, but the ORM models (and the cases
service, which constructs ``CaseEvent(data=...)`` / ``CaseEvidence(data=...)``)
declare the column as ``data``.  The API input schema keeps ``metadata`` as
its public field name and the service maps it onto the model attribute, so the
DB column must match the model: ``data``.

Without this, every INSERT/SELECT of a case event or evidence through the ORM
fails on PostgreSQL with UndefinedColumnError.  Tests never caught it because
the suite builds the schema from ``Base.metadata.create_all`` (the model
definition) instead of running the migrations.

Backward-compatible rename: no data is rewritten, only the column name.

Revision ID: 045_rename_case_json_column
Revises: 044_add_payments_updated_at
Create Date: 2026-08-12 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "045_rename_case_json_column"
down_revision: str | Sequence[str] | None = "044_add_payments_updated_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # SQLite needs a batch table-rebuild for renames; PostgreSQL executes a
    # plain ALTER TABLE RENAME.  batch_alter_table handles both transparently.
    with op.batch_alter_table("case_events") as batch:
        batch.alter_column(
            "metadata",
            new_column_name="data",
            existing_type=sa.JSON(),
            existing_nullable=True,
        )
    with op.batch_alter_table("case_evidence") as batch:
        batch.alter_column(
            "metadata",
            new_column_name="data",
            existing_type=sa.JSON(),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("case_events") as batch:
        batch.alter_column(
            "data",
            new_column_name="metadata",
            existing_type=sa.JSON(),
            existing_nullable=True,
        )
    with op.batch_alter_table("case_evidence") as batch:
        batch.alter_column(
            "data",
            new_column_name="metadata",
            existing_type=sa.JSON(),
            existing_nullable=True,
        )
