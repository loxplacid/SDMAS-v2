"""harden audit_logs with canonical event structure

Adds the canonical audit-event columns to ``audit_logs`` (event_id,
typed actor, tenant/request/correlation ids, before/after state,
outcome, metadata), widens ``action`` for semantic actions, and adds
verifier columns to ``payment_reconciliations``.

Revision ID: 035_harden_audit_logs
Revises: 034_harden_tenant_boundaries
Create Date: 2026-08-03
"""
from __future__ import annotations

import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "035_harden_audit_logs"
down_revision: Union[str, None] = "034_harden_tenant_boundaries"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _backfill_event_id_sql(dialect: str) -> str:
    """Dialect-specific expression producing a 32-char hex event id."""
    if dialect == "postgresql":
        return (
            "UPDATE audit_logs SET event_id = md5(random()::text || "
            "clock_timestamp()::text) WHERE event_id IS NULL"
        )
    if dialect == "mysql":
        return (
            "UPDATE audit_logs SET event_id = "
            "replace(uuid(), '-', '') WHERE event_id IS NULL"
        )
    # SQLite / default
    return (
        "UPDATE audit_logs SET event_id = "
        "lower(hex(randomblob(16))) WHERE event_id IS NULL"
    )


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # ── audit_logs: add canonical audit-event columns ────────────────
    with op.batch_alter_table("audit_logs") as batch:
        batch.add_column(sa.Column("event_id", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("actor_type", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("actor_id", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("tenant_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("request_id", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("correlation_id", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("before_state", sa.Text(), nullable=True))
        batch.add_column(sa.Column("after_state", sa.Text(), nullable=True))
        batch.add_column(sa.Column("result", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("failure_reason", sa.Text(), nullable=True))
        batch.add_column(sa.Column("metadata", sa.Text(), nullable=True))

    # Backfill event ids for existing rows so the column can be NOT NULL.
    op.execute(sa.text(_backfill_event_id_sql(dialect)))

    with op.batch_alter_table("audit_logs") as batch:
        batch.alter_column(
            "action",
            existing_type=sa.String(length=20),
            type_=sa.String(length=30),
            existing_nullable=False,
        )
        batch.alter_column(
            "event_id",
            existing_type=sa.String(length=32),
            nullable=False,
        )
        batch.create_unique_constraint("uq_audit_logs_event_id", ["event_id"])
        batch.create_index("ix_audit_logs_event_id", ["event_id"])
        batch.create_index("ix_audit_logs_actor_type", ["actor_type"])
        batch.create_index("ix_audit_logs_actor_id", ["actor_id"])
        batch.create_index("ix_audit_logs_tenant_id", ["tenant_id"])
        batch.create_index("ix_audit_logs_request_id", ["request_id"])
        batch.create_index("ix_audit_logs_correlation_id", ["correlation_id"])
        batch.create_index("ix_audit_logs_result", ["result"])

    # ── payment_reconciliations: persist reviewer identities ──────────
    with op.batch_alter_table("payment_reconciliations") as batch:
        batch.add_column(sa.Column("verified_by", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("approved_by", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_payment_reconciliations_verified_by",
            "users", ["verified_by"], ["id"], ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "fk_payment_reconciliations_approved_by",
            "users", ["approved_by"], ["id"], ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("payment_reconciliations") as batch:
        batch.drop_constraint(
            "fk_payment_reconciliations_verified_by", type_="foreignkey"
        )
        batch.drop_constraint(
            "fk_payment_reconciliations_approved_by", type_="foreignkey"
        )
        batch.drop_column("verified_by")
        batch.drop_column("approved_by")

    with op.batch_alter_table("audit_logs") as batch:
        batch.drop_index("ix_audit_logs_result")
        batch.drop_index("ix_audit_logs_correlation_id")
        batch.drop_index("ix_audit_logs_request_id")
        batch.drop_index("ix_audit_logs_tenant_id")
        batch.drop_index("ix_audit_logs_actor_id")
        batch.drop_index("ix_audit_logs_actor_type")
        batch.drop_index("ix_audit_logs_event_id")
        batch.drop_constraint("uq_audit_logs_event_id", type_="unique")
        batch.alter_column(
            "action",
            existing_type=sa.String(length=30),
            type_=sa.String(length=20),
            existing_nullable=False,
        )
        batch.drop_column("event_id")
        batch.drop_column("actor_type")
        batch.drop_column("actor_id")
        batch.drop_column("tenant_id")
        batch.drop_column("request_id")
        batch.drop_column("correlation_id")
        batch.drop_column("before_state")
        batch.drop_column("after_state")
        batch.drop_column("result")
        batch.drop_column("failure_reason")
        batch.drop_column("metadata")
