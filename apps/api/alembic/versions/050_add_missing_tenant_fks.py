"""Add tenant FKs missing on assignments and guardian_links.

Revision ID: 050_add_missing_tenant_fks
Revises: 049_widen_audit_action
Create Date: 2026-08-16

The ORM models declare ``assignments.campus_id`` and
``guardian_links.campus_id`` with ``ForeignKey("campuses.id",
ondelete="SET NULL")``, but the historical migrations that created the
columns never added the database-level constraint.  Alembic autogenerate
detected both as "added foreign key" — the DB was not enforcing a tenant FK
the application layer promises.  Corrective migration adds both
constraints (verified: no orphan rows exist on production data).

SQLite needs batch_alter_table to add an FK; PostgreSQL emits a plain
ALTER TABLE.

SQLite note (repair): ``batch_alter_table`` rebuilds the table, which
fails while the ``legacy_null_campus_records`` view (migration
c21889d4e562) references ``assignments``/``guardian_links`` — the view is
dropped first and recreated identically afterwards, matching the pattern
already used by migrations 044 and 047.  The repair is SQLite-only; it
does not change the DDL emitted on PostgreSQL, so databases that already
applied this revision are unaffected.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "050_add_missing_tenant_fks"
down_revision: str | None = "049_widen_audit_action"
branch_labels: str | None = None
depends_on: str | None = None

#: The read-only detection view from c21889d4e562, recreated verbatim.
_LEGACY_VIEW_SQL = sa.text(
    """
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
)


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    # SQLite rebuilds the tables and the view would break mid-rename.
    if _is_sqlite():
        op.execute(sa.text("DROP VIEW IF EXISTS legacy_null_campus_records"))

    for table in ("assignments", "guardian_links"):
        with op.batch_alter_table(table) as batch:
            batch.create_foreign_key(
                f"fk_{table}_campus_id",
                "campuses",
                ["campus_id"],
                ["id"],
                ondelete="SET NULL",
            )

    if _is_sqlite():
        op.execute(_LEGACY_VIEW_SQL)


def downgrade() -> None:
    if _is_sqlite():
        op.execute(sa.text("DROP VIEW IF EXISTS legacy_null_campus_records"))

    for table in ("assignments", "guardian_links"):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(f"fk_{table}_campus_id", type_="foreignkey")

    if _is_sqlite():
        op.execute(_LEGACY_VIEW_SQL)
