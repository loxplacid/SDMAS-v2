"""harden finance ledger: idempotent payments, refunds, webhook dedup

Adds the payment idempotency/refund columns and DB-enforced range checks
to ``payments``/``fee_dues``, and creates the ``webhook_events``
idempotency ledger used to deduplicate provider webhook deliveries.

Revision ID: 036_harden_finance_ledger
Revises: 035_harden_audit_logs
Create Date: 2026-08-03
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "036_harden_finance_ledger"
down_revision: Union[str, None] = "035_harden_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── payments: idempotency key, explicit status, refund tracking ───
    with op.batch_alter_table("payments") as batch:
        batch.add_column(sa.Column("idempotency_key", sa.String(length=255), nullable=True))
        batch.add_column(
            sa.Column("status", sa.String(length=20), nullable=False, server_default="completed")
        )
        batch.add_column(
            sa.Column("refunded_amount", sa.Integer(), nullable=False, server_default="0")
        )
        batch.create_unique_constraint("uq_payment_idempotency_key", ["idempotency_key"])

    # ── DB-enforced money sanity checks ───────────────────────────────
    # Payments can never be negative; a refunded amount can never exceed the
    # original payment.  A fee due can never hold a paid balance outside
    # [0, original_amount] — the final guard against concurrent double-pay.
    with op.batch_alter_table("payments") as batch:
        batch.create_check_constraint(
            "ck_payment_amount_positive", "amount > 0"
        )
        batch.create_check_constraint(
            "ck_payment_refunded_amount_range",
            "refunded_amount >= 0 AND refunded_amount <= amount",
        )

    with op.batch_alter_table("fee_dues") as batch:
        batch.create_check_constraint(
            "ck_fee_due_amount_paid_range",
            "amount_paid >= 0 AND amount_paid <= original_amount",
        )

    # ── webhook_events: idempotency ledger for provider deliveries ────
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider_name", sa.String(length=50), nullable=False),
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column("event_name", sa.String(length=100), nullable=False, server_default="unknown"),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("campus_id", sa.Integer(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_name", "event_id", name="uq_webhook_event_delivery"
        ),
    )
    op.create_index("ix_webhook_events_campus_id", "webhook_events", ["campus_id"])


def downgrade() -> None:
    op.drop_index("ix_webhook_events_campus_id", table_name="webhook_events")
    op.drop_table("webhook_events")

    with op.batch_alter_table("fee_dues") as batch:
        batch.drop_constraint("ck_fee_due_amount_paid_range", type_="check")

    with op.batch_alter_table("payments") as batch:
        batch.drop_constraint("ck_payment_refunded_amount_range", type_="check")
        batch.drop_constraint("ck_payment_amount_positive", type_="check")

    with op.batch_alter_table("payments") as batch:
        batch.drop_constraint("uq_payment_idempotency_key", type_="unique")
        batch.drop_column("refunded_amount")
        batch.drop_column("status")
        batch.drop_column("idempotency_key")
