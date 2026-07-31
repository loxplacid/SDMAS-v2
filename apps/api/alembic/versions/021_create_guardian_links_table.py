"""Create guardian_links table for parent-child relationships

Revision ID: 021
Revises: d29e45f87a2c
Create Date: 2026-07-31 08:45:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "021"
down_revision: Union[str, None] = "d29e45f87a2c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "guardian_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column(
            "relationship",
            sa.String(length=50),
            nullable=False,
            server_default="parent",
        ),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["students.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "student_id", name="uq_guardian_user_student"
        ),
    )
    op.create_index(
        op.f("ix_guardian_links_user_id"),
        "guardian_links",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_guardian_links_student_id"),
        "guardian_links",
        ["student_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_guardian_links_student_id"), table_name="guardian_links"
    )
    op.drop_index(
        op.f("ix_guardian_links_user_id"), table_name="guardian_links"
    )
    op.drop_table("guardian_links")
