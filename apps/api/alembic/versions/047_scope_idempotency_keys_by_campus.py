"""scope idempotency keys by campus

Revision ID: 047_scope_idempotency_keys_by_campus
Revises: 046_restore_performance_indexes
Create Date: 2026-08-12

Why:
    ``payments.idempotency_key`` and ``transaction_logs.idempotency_key``
    were guarded by *globally* unique constraints.  Two independent tenants
    legitimately using the same client-supplied key collided at the DB
    layer: the second tenant's payment was rejected with a spurious
    409/IntegrityError even though the record was valid for its own
    campus.  This is a multi-tenant correctness/availability defect.

    The keys are scoped per campus: ``UNIQUE (campus_id, idempotency_key)``.
    PostgreSQL treats NULLs as distinct in unique indexes, so the many
    rows with NULL ``idempotency_key`` remain valid.

SQLite note:
    Alembic's ``batch_alter_table`` rebuilds the table on SQLite, and the
    ``legacy_null_campus_records`` view references ``payments``.  The view
    is dropped before the rebuilds and recreated afterwards (SQLite
    requires the view to exist at statement time or the rename fails).
"""

import sqlalchemy as sa

from alembic import op

revision = "047_scope_idem_keys"
down_revision = "046_restore_performance_indexes"
branch_labels = None
depends_on = None

# Recreate of c21889d4e562's read-only view — must exist after we touch
# tables it references, or the view (and every dependent query) breaks.
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


def _existing_unique_names(table: str) -> set[str]:
    """Names of unique constraints currently on ``table`` for this dialect.

    SQLite's reflection surfaces the named constraints; the unnamed
    ``UNIQUE (idempotency_key)`` auto-index (created inline by the original
    ``create_table``) is dropped automatically when batch mode rebuilds the
    table, so it never needs an explicit drop here.
    """
    from sqlalchemy import inspect as sa_inspect

    inspector = sa_inspect(op.get_bind())
    try:
        return {
            uc["name"]
            for uc in inspector.get_unique_constraints(table)
            if uc.get("name")
        }
    except Exception:  # noqa: BLE001 -- reflection best effort
        return set()


def upgrade() -> None:
    # SQLite rebuilds the table and the view would break mid-rename.
    if _is_sqlite():
        op.execute(sa.text("DROP VIEW IF EXISTS legacy_null_campus_records"))

    # payments: global unique -> campus-scoped unique
    with op.batch_alter_table("payments") as batch_op:
        if "uq_payment_idempotency_key" in _existing_unique_names("payments"):
            batch_op.drop_constraint(
                "uq_payment_idempotency_key", type_="unique"
            )
    with op.batch_alter_table("payments") as batch_op:
        batch_op.create_unique_constraint(
            "uq_payment_idempotency_key", ["campus_id", "idempotency_key"]
        )

    # transaction_logs: overlapping global uniques -> one campus-scoped
    with op.batch_alter_table("transaction_logs") as batch_op:
        names = _existing_unique_names("transaction_logs")
        if "uq_transaction_idempotency" in names:
            batch_op.drop_constraint(
                "uq_transaction_idempotency", type_="unique"
            )
        # PostgreSQL names the inline constraint from 9f79b639163c
        # ``transaction_logs_idempotency_key_key``; SQLite keeps it as an
        # unnamed auto-index that batch rebuild discards on its own.
        if "transaction_logs_idempotency_key_key" in names:
            batch_op.drop_constraint(
                "transaction_logs_idempotency_key_key", type_="unique"
            )
    with op.batch_alter_table("transaction_logs") as batch_op:
        batch_op.create_unique_constraint(
            "uq_transaction_idempotency", ["campus_id", "idempotency_key"]
        )

    if _is_sqlite():
        op.execute(_LEGACY_VIEW_SQL)


def downgrade() -> None:
    if _is_sqlite():
        op.execute(sa.text("DROP VIEW IF EXISTS legacy_null_campus_records"))

    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_constraint("uq_payment_idempotency_key", type_="unique")
    with op.batch_alter_table("payments") as batch_op:
        batch_op.create_unique_constraint(
            "uq_payment_idempotency_key", ["idempotency_key"]
        )

    with op.batch_alter_table("transaction_logs") as batch_op:
        batch_op.drop_constraint("uq_transaction_idempotency", type_="unique")
    with op.batch_alter_table("transaction_logs") as batch_op:
        batch_op.create_unique_constraint(
            "uq_transaction_idempotency", ["idempotency_key"]
        )
    with op.batch_alter_table("transaction_logs") as batch_op:
        batch_op.create_unique_constraint(
            "transaction_logs_idempotency_key_key", ["idempotency_key"]
        )

    if _is_sqlite():
        op.execute(_LEGACY_VIEW_SQL)
