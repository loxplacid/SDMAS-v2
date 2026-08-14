"""add high-traffic performance indexes

Revision ID: 048_perf_indexes
Revises: 047_scope_idem_keys
Create Date: 2026-08-13

Why:
    Measured on a scratch 100k-student / 300k-ledger-row database (see
    docs/enterprise/PERFORMANCE-AUDIT.md).  Three hot query shapes were
    doing full scans:

    1. Student search — ``/students?search=`` builds
       ``(first_name ILIKE '%q%' OR last_name ILIKE '%q%' OR
        student_number ILIKE '%q%' OR email ILIKE '%q%')``.  The
       per-column trigram indexes from 022 exist, but the planner never
       combined them for OR queries at this scale (seq scan, ~237ms).
       A single multi-column GIN over exactly the OR'd columns is the
       shape the planner actually uses (~3ms).

    2. Student filtered list/count — ``WHERE campus_id = X AND status =
       'active' ORDER BY id LIMIT 50``.  A composite (campus_id, status)
       index lets the page-1 query seek the first 50 matching rows
       instead of scanning the campus subset (~43ms -> ~5ms).

    3. Ledger list by campus + date range — ``/transactions`` and the
       90-day views.  (campus_id, created_at) turns the range into an
       index seek (~159ms -> ~6ms).

SQLite note:
    The trigram index and extension are PostgreSQL-only and guarded by
    the dialect check.  The two btree indexes are dialect-neutral and
    the SQLite test suite exercises the migration path.
"""

import sqlalchemy as sa

from alembic import op

revision = "048_perf_indexes"
down_revision = "047_scope_idem_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        # Enable trigram extension for fuzzy matching (idempotent; the
        # extension is owned by 022 for production databases, but a fresh
        # database runs this migration independently).
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

        # Single GIN over the exact OR'd search columns.  Requires the
        # DB role to be able to create extensions (the compose setup runs
        # as the postgres superuser; managed production DBs should pre-
        # create pg_trgm — the migration fails loudly otherwise).
        op.create_index(
            "ix_students_trgm",
            "students",
            [
                sa.text("first_name gin_trgm_ops"),
                sa.text("last_name gin_trgm_ops"),
                sa.text("student_number gin_trgm_ops"),
                sa.text("email gin_trgm_ops"),
            ],
            postgresql_using="gin",
        )

    # Dialect-neutral: filtered student lists (the status rail on
    # /students and the role dashboards).
    op.create_index(
        "ix_students_campus_status", "students", ["campus_id", "status"]
    )

    # Dialect-neutral: ledger list by campus + recency (created_at DESC
    # is served by a backward scan of this index on both backends).
    op.create_index(
        "ix_transaction_logs_campus_created",
        "transaction_logs",
        ["campus_id", "created_at"],
    )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.drop_index("ix_students_trgm", table_name="students")
    op.drop_index("ix_students_campus_status", table_name="students")
    op.drop_index(
        "ix_transaction_logs_campus_created", table_name="transaction_logs"
    )
    # The pg_trgm extension is intentionally left in place: dropping an
    # extension can break unrelated objects that depend on it, and the
    # per-column trigram indexes from 022 still reference it.
