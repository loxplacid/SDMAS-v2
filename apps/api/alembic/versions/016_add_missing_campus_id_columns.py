"""add campus_id to device_tokens, leave_requests, and workflow_instances

Revision ID: 016_add_missing_campus_id_columns
Revises: 015_create_audit_logs
Create Date: 2026-07-30

Tables ``device_tokens`` (migration 009), ``workflow_instances``
(migration 013), and ``leave_requests`` (migration 014) were created
without a ``campus_id`` column because they were either created before
migration 011 (which added campus_id to the core set of tables) or
were added later as new domains.  This migration backfills those
columns.

For SQLite compatibility we use ``ALTER TABLE`` (via batch mode) and
leave FOREIGN KEY enforcement to the ORM.  The index is added so that
tenant-scoped queries can use it.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "016_add_missing_campus_id_columns"
down_revision: Union[str, None] = "015_create_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES_TO_UPDATE = [
    "device_tokens",
    "workflow_instances",
    "leave_requests",
]


def upgrade() -> None:
    for table in TABLES_TO_UPDATE:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column("campus_id", sa.Integer(), nullable=True),
            )
            batch_op.create_index(
                f"ix_{table}_campus_id", ["campus_id"],
            )

    # Set campus_id = 1 (Main Campus / default tenant) for all existing
    # records so that they remain visible after tenancy is enforced.
    for table in TABLES_TO_UPDATE:
        op.execute(
            sa.text(f"UPDATE {table} SET campus_id = 1 WHERE campus_id IS NULL")
        )


def downgrade() -> None:
    for table in TABLES_TO_UPDATE:
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_index(f"ix_{table}_campus_id")
            batch_op.drop_column("campus_id")
