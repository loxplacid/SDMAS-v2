"""harden tenant boundaries: campus_id on assignments/guardian_links + tenant indexes

Revision ID: 034_harden_tenant_boundaries
Revises: 033_add_notification_event_key
Create Date: 2026-08-02

Multi-tenancy hardening:

1. ``assignments`` and ``guardian_links`` never carried a ``campus_id``
   column.  That made both tables *platform* in the tenancy registry:
   ``Assignment`` could never be tenant-filtered, and
   ``AssignmentSubmission`` (which inherits tenancy from ``Assignment``)
   could not resolve its parent's campus.  ``Guardian`` (parent↔student
   junction) could therefore link a user to a student of any tenant.
   This migration adds the column, backfills to the default campus (1,
   matching the earlier 011/016 backfills) and indexes it.

2. Tables created after migrations 011/016 gained a ``campus_id`` column
   without a ``campus_id`` index.  Every tenant-scoped query filters on
   ``campus_id`` at construction time, so those columns need indexes.
   We create ``ix_<table>_campus_id`` for each such table; the tables
   covered by 011/016 already have their index.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "034_harden_tenant_boundaries"
down_revision: Union[str, None] = "033_add_notification_event_key"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables that gained campus_id after migration 011/016 and never received
# an index on it.
TABLES_NEEDING_INDEX = [
    "admission_applications",
    "rooms",
    "time_slots",
    "timetable_entries",
    "substitutions",
    "exam_schedules",
    "grading_structures",
    "grade_records",
    "curricula",
    "payment_methods",
    "fee_schedules",
    "transaction_logs",
    "payment_reconciliations",
    "receipts",
    "finance_reports",
    "absence_reasons",
    "attendance_corrections",
    "attendance_thresholds",
    "period_attendances",
    "documents",
    "communication_messages",
    "message_templates",
    "message_threads",
    "export_jobs",
    "search_history",
]


def upgrade() -> None:
    # 1. Add campus_id to assignments and guardian_links (SQLite-safe batch
    #    mode; FK enforcement is ORM-level).
    for table in ("assignments", "guardian_links"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column("campus_id", sa.Integer(), nullable=True),
            )
            batch_op.create_index(
                f"ix_{table}_campus_id", ["campus_id"],
            )

    # Backfill to the default campus (1) so existing rows remain visible.
    for table in ("assignments", "guardian_links"):
        op.execute(
            sa.text(f"UPDATE {table} SET campus_id = 1 WHERE campus_id IS NULL")
        )

    # 2. Tenant-aware indexes on the remaining tenant-owned tables.
    for table in TABLES_NEEDING_INDEX:
        op.create_index(f"ix_{table}_campus_id", table, ["campus_id"])


def downgrade() -> None:
    for table in reversed(TABLES_NEEDING_INDEX):
        op.drop_index(f"ix_{table}_campus_id", table_name=table)

    for table in ("guardian_links", "assignments"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_index(f"ix_{table}_campus_id")
            batch_op.drop_column("campus_id")
