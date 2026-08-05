"""flag_legacy_null_campus_records

Creates a read-only view ``legacy_null_campus_records`` that lists every
tenant-owned record whose ``campus_id`` is NULL — ambiguous ownership that
must NOT be silently treated as global access.

Revision ID: c21889d4e562
Revises: 038_add_invoice_period_unique
Create Date: 2026-08-04 21:51:18.073592

Security invariant
------------------
Tenant-owned records must carry explicit ownership (a concrete
``campus_id``).  NULL is **never** an implicit authorization state:

* a scoped tenant must not see NULL-campus rows (scoped queries pin to
  ``campus_id = <tenant>`` and never match NULL);
* platform/global records must be explicitly classified as global.

This migration only DETECTS ambiguous rows; it never mutates data.
Records listed here require manual resolution (backfill to the owning
campus, or explicit reclassification as platform data).

Manual resolution guidance
--------------------------
* Migrations 011/016/034 already backfilled ``campus_id = 1`` for NULL
  rows in the core tables created before multi-tenancy — so in production
  the view should be mostly empty for those tables.
* ``risk_rule_configs`` is the documented exception: ``campus_id NULL``
  means *global default rule* (seeded once), a per-row *explicit*
  classification in the model — such rows are platform data, not legacy
  ambiguity.
* Tables NOT listed here carry no ``campus_id`` column and are platform
  data (e.g. ``report_definitions``, ``document_categories``) — they were
  omitted on purpose so this view cannot fail against them.

Fail-safe behaviour
-------------------
If a table in this view ever loses its ``campus_id`` column, the CREATE
VIEW fails and the migration aborts — it refuses to silently drop
detection coverage for a tenant-owned table.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c21889d4e562'
down_revision: Union[str, None] = '038_add_invoice_period_unique'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_view(
        'legacy_null_campus_records',
        sa.text(
            """
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
        ),
    )


def downgrade() -> None:
    op.drop_view('legacy_null_campus_records')
