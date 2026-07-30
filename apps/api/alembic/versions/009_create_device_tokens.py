"""create device_tokens table for push notifications

Revision ID: 009_create_device_tokens
Revises: 008_create_notifications
Create Date: 2026-07-29
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "009_create_device_tokens"
down_revision: Union[str, None] = "008_create_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "device_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "token",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "platform",
            sa.String(length=20),
            nullable=False,
            server_default="android",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_device_tokens_token"),
    )
    op.create_index(
        "ix_device_tokens_user_id", "device_tokens", ["user_id"]
    )
    op.create_index(
        "ix_device_tokens_token", "device_tokens", ["token"]
    )


def downgrade() -> None:
    op.drop_index("ix_device_tokens_token", table_name="device_tokens")
    op.drop_index("ix_device_tokens_user_id", table_name="device_tokens")
    op.drop_table("device_tokens")
