"""add notification event_key dedup column

Revision ID: 033_add_notification_event_key
Revises: 032_create_student_lifecycle
Create Date: 2026-08-02 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "033_add_notification_event_key"
down_revision: Union[str, None] = "032_create_student_lifecycle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("event_key", sa.String(length=128), nullable=True),
    )
    op.create_index(
        op.f("ix_notifications_event_key"),
        "notifications",
        ["event_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_notifications_event_key"),
        table_name="notifications",
    )
    op.drop_column("notifications", "event_key")
