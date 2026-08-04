"""create student_lifecycle_events table

Revision ID: 032_create_student_lifecycle
Revises: 031_create_risk_engine_tables
Create Date: 2026-08-01 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "032_create_student_lifecycle"
down_revision: Union[str, None] = "031_create_risk_engine_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "student_lifecycle_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "student_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(length=20), nullable=False),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("campus_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["campus_id"], ["campuses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_student_lifecycle_events_student_id"),
        "student_lifecycle_events",
        ["student_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_student_lifecycle_events_campus_id"),
        "student_lifecycle_events",
        ["campus_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_student_lifecycle_events_campus_id"),
        table_name="student_lifecycle_events",
    )
    op.drop_index(
        op.f("ix_student_lifecycle_events_student_id"),
        table_name="student_lifecycle_events",
    )
    op.drop_table("student_lifecycle_events")
