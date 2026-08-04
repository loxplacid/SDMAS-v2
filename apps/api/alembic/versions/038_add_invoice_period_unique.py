"""add unique invoice constraint: one invoice per subscription billing period

Adds the database-level invariant ``UNIQUE(subscription_id, period_start)``
to ``invoices``.  This is the structural backstop on top of the
application-level row lock in ``SubscriptionService.process_period_end``:
a race between the pending-invoice check and the insert can no longer
double-bill a billing period.

Strategy (fail-closed, never deletes financial records):

1. Scan for existing duplicate ``(subscription_id, period_start)`` rows.
2. If any exist, abort the migration with the exact query to inspect them —
   duplicates must be resolved manually by an operator before the
   constraint can be applied.  No record is silently modified or removed.
3. Only when the data is clean, create the unique constraint.

Revision ID: 038_add_invoice_period_unique
Revises: 037_create_outbox_events
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "038_add_invoice_period_unique"
down_revision: Union[str, None] = "037_create_outbox_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: Name of the unique constraint / index (must match the model's
#: ``__table_args__`` so the schema created by tests mirrors production).
CONSTRAINT_NAME = "uq_invoices_subscription_period"

_DUPLICATE_SCAN_SQL = sa.text(
    "SELECT subscription_id, period_start, COUNT(*) AS n "
    "FROM invoices "
    "GROUP BY subscription_id, period_start "
    "HAVING COUNT(*) > 1"
)


def _find_duplicate_periods(bind) -> list:
    """Return duplicate (subscription_id, period_start) groups, if any."""
    return bind.execute(_DUPLICATE_SCAN_SQL).fetchall()


def upgrade() -> None:
    bind = op.get_bind()

    duplicates = _find_duplicate_periods(bind)
    if duplicates:
        detail = "\n".join(
            f"  subscription_id={row.subscription_id}, "
            f"period_start={row.period_start}, rows={row.n}"
            for row in duplicates
        )
        raise RuntimeError(
            "Cannot add UNIQUE(subscription_id, period_start) to 'invoices': "
            f"{len(duplicates)} duplicate billing period(s) already exist.\n"
            "Financial records are never deleted automatically. Resolve them "
            "manually (e.g. void/merge the duplicate invoice rows) then re-run "
            "the migration. Duplicates found:\n"
            f"{detail}\n"
            "Inspect them with:\n"
            "  SELECT subscription_id, period_start, COUNT(*) AS n "
            "FROM invoices GROUP BY subscription_id, period_start HAVING COUNT(*) > 1;"
        )

    with op.batch_alter_table("invoices") as batch_op:
        batch_op.create_unique_constraint(CONSTRAINT_NAME, ["subscription_id", "period_start"])


def downgrade() -> None:
    with op.batch_alter_table("invoices") as batch_op:
        batch_op.drop_constraint(CONSTRAINT_NAME, type_="unique")
