"""create outbox_events: durable integration event outbox

Adds the transactional-outbox table used to persist critical integration
events (payment recorded, fee dues created, batch completed, academic-year
rollover) atomically with the business mutation that produced them.  The
dedicated worker process delivers these rows to their handlers with
retry / dead-letter semantics; ``event_id`` is unique so a re-published
event collapses to one row (idempotent producer) and consumers dedup on
the same id.

Revision ID: 037_create_outbox_events
Revises: 036_harden_finance_ledger
Create Date: 2026-08-03
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "037_create_outbox_events"
down_revision: Union[str, None] = "036_harden_finance_ledger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("school_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_outbox_events_event_id"),
    )
    op.create_index("ix_outbox_events_event_id", "outbox_events", ["event_id"])
    op.create_index("ix_outbox_events_event_type", "outbox_events", ["event_type"])
    op.create_index("ix_outbox_events_school_id", "outbox_events", ["school_id"])
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"])
    op.create_index("ix_outbox_events_next_attempt_at", "outbox_events", ["next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_outbox_events_next_attempt_at", table_name="outbox_events")
    op.drop_index("ix_outbox_events_status", table_name="outbox_events")
    op.drop_index("ix_outbox_events_school_id", table_name="outbox_events")
    op.drop_index("ix_outbox_events_event_type", table_name="outbox_events")
    op.drop_index("ix_outbox_events_event_id", table_name="outbox_events")
    op.drop_table("outbox_events")
