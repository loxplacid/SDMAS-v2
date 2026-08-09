"""add_communication_context

Revision ID: 041_add_communication_context
Revises: 040_create_cases_tables
Create Date: 2026-08-08

P15 — contextual communications: a message is linked to the operational
entity it was composed from (student, case, fee due, admission). The
columns are plain nullable strings/ints so existing rows are untouched;
the link is cosmetic-but-indexed (no FK on purpose — contexts are
polymorphic across domains and a missing target must never block the
message lifecycle).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "041_add_communication_context"
down_revision: Union[str, None] = "040_create_cases_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "communication_messages",
        sa.Column("context_type", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "communication_messages",
        sa.Column("context_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_communication_messages_context",
        "communication_messages",
        ["context_type", "context_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_communication_messages_context", table_name="communication_messages")
    op.drop_column("communication_messages", "context_id")
    op.drop_column("communication_messages", "context_type")
