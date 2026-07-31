"""Create notification_preferences table for per-user event/channel opt-in.

Revision ID: 019
Revises: 018
Create Date: 2026-07-30
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "019"
down_revision: str | None = "018"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False, server_default="in_app"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notification_preferences_user_event",
        "notification_preferences",
        ["user_id", "event_type"],
    )
    op.create_index(
        "ix_notification_preferences_user",
        "notification_preferences",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_notification_preferences_user", table_name="notification_preferences")
    op.drop_index("ix_notification_preferences_user_event", table_name="notification_preferences")
    op.drop_table("notification_preferences")
