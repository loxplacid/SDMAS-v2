"""Widen audit_logs.action to fit migration-domain actions.

Revision ID: 049_widen_audit_action
Revises: 048_add_performance_indexes
Create Date: 2026-08-14

The migration domain emits semantic audit actions up to 34 characters
(MIGRATION_PROJECT_IMPORT_COMPLETED).  The column was String(30) since 035,
so those INSERTs raised StringDataRightTruncationError, poisoning the
request session and returning 500 from /migration/projects/{id}/import.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "049_widen_audit_action"
down_revision: str | None = "048_perf_indexes"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # batch_alter_table: plain ALTER COLUMN TYPE is not supported on
    # SQLite; batch mode rebuilds the table on SQLite and emits a plain
    # ALTER on PostgreSQL.
    with op.batch_alter_table("audit_logs") as batch:
        batch.alter_column(
            "action",
            existing_type=sa.String(length=30),
            type_=sa.String(length=64),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("audit_logs") as batch:
        batch.alter_column(
            "action",
            existing_type=sa.String(length=64),
            type_=sa.String(length=30),
            existing_nullable=False,
        )
