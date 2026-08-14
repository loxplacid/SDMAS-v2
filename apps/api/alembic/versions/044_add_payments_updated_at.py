"""add payments.updated_at to match the Payment model

The ``Payment`` model declares a non-nullable ``updated_at`` (with a Python-side
default), but no migration ever created the column — every SELECT/INSERT of a
payment on PostgreSQL raised UndefinedColumnError. ``fee_dues`` already has the
column; ``payments`` was missed when the timestamps were introduced.

Backward-compatible additive migration: existing rows are back-filled from
``created_at`` so the non-null constraint holds on populated tables.

SQLite note: ``batch_alter_table`` rebuilds the table, which fails while the
``legacy_null_campus_records`` view (migration c21889d4e562) references it —
the view is dropped first and recreated identically afterwards.

Revision ID: 044_add_payments_updated_at
Revises: 043_add_migration_projects
Create Date: 2026-08-11 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "044_add_payments_updated_at"
down_revision: str | Sequence[str] | None = "043_add_migration_projects"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEGACY_VIEW_DDL = """
CREATE VIEW legacy_null_campus_records AS
SELECT 'students' AS table_name, id AS record_id, campus_id
FROM students WHERE campus_id IS NULL
UNION ALL
SELECT 'student_lifecycle_events', id, campus_id
FROM student_lifecycle_events WHERE campus_id IS NULL
UNION ALL
SELECT 'notifications', id, campus_id
FROM notifications WHERE campus_id IS NULL
UNION ALL
SELECT 'device_tokens', id, campus_id
FROM device_tokens WHERE campus_id IS NULL
UNION ALL
SELECT 'fee_dues', id, campus_id
FROM fee_dues WHERE campus_id IS NULL
UNION ALL
SELECT 'payments', id, campus_id
FROM payments WHERE campus_id IS NULL
UNION ALL
SELECT 'invoices', id, campus_id
FROM invoices WHERE campus_id IS NULL
UNION ALL
SELECT 'webhook_events', id, campus_id
FROM webhook_events WHERE campus_id IS NULL
UNION ALL
SELECT 'teacher_assignments', id, campus_id
FROM teacher_assignments WHERE campus_id IS NULL
UNION ALL
SELECT 'sections', id, campus_id
FROM sections WHERE campus_id IS NULL
UNION ALL
SELECT 'enrollments', id, campus_id
FROM enrollments WHERE campus_id IS NULL
UNION ALL
SELECT 'attendance_records', id, campus_id
FROM attendance_records WHERE campus_id IS NULL
UNION ALL
SELECT 'workflow_instances', id, campus_id
FROM workflow_instances WHERE campus_id IS NULL
UNION ALL
SELECT 'search_history', id, campus_id
FROM search_history WHERE campus_id IS NULL
UNION ALL
SELECT 'risk_rule_configs', id, campus_id
FROM risk_rule_configs WHERE campus_id IS NULL
UNION ALL
SELECT 'risk_findings', id, campus_id
FROM risk_findings WHERE campus_id IS NULL
UNION ALL
SELECT 'communication_messages', id, campus_id
FROM communication_messages WHERE campus_id IS NULL
UNION ALL
SELECT 'assignments', id, campus_id
FROM assignments WHERE campus_id IS NULL
UNION ALL
SELECT 'guardian_links', id, campus_id
FROM guardian_links WHERE campus_id IS NULL
"""


def upgrade() -> None:
    # SQLite rebuilds the payments table; the legacy view depends on it.
    if op.get_bind().dialect.name == "sqlite":
        op.execute(sa.text("DROP VIEW legacy_null_campus_records"))

    with op.batch_alter_table("payments") as batch:
        batch.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
    op.execute(
        sa.text(
            "UPDATE payments SET updated_at = created_at "
            "WHERE updated_at IS NULL"
        )
    )
    with op.batch_alter_table("payments") as batch:
        batch.alter_column("updated_at", nullable=False)

    if op.get_bind().dialect.name == "sqlite":
        op.execute(sa.text(_LEGACY_VIEW_DDL))


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute(sa.text("DROP VIEW legacy_null_campus_records"))

    with op.batch_alter_table("payments") as batch:
        batch.drop_column("updated_at")

    if op.get_bind().dialect.name == "sqlite":
        op.execute(sa.text(_LEGACY_VIEW_DDL))
