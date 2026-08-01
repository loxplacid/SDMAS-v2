"""create user_school_memberships table

Revision ID: 030_create_user_school_memberships
Revises: merge_multi_tenant_heads
Create Date: 2026-08-01 00:00:00.000000

Migration strategy for existing data:
------------------------------------
The ``users`` table has a legacy nullable ``campus_id`` column that
represented the user's single school. This migration:

1. Creates the ``user_school_memberships`` table (user <-> campus join
   with per-school role, active flag and default flag).
2. Backfills every existing user who has a ``campus_id`` into a single
   active, default membership row using that exact ``campus_id`` — so
   existing IDs are preserved and the tenant assignment is deterministic
   (a user keeps exactly the school they already had).

Users with ``campus_id IS NULL`` (platform admins / cross-tenant admins)
get no membership row, preserving their unscoped access.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "030_create_user_school_memberships"
down_revision: Union[str, None] = "merge_multi_tenant_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_school_memberships",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("campus_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="staff"),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campus_id"], ["campuses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "campus_id", name="uq_user_school_membership"),
    )
    op.create_index(
        op.f("ix_user_school_memberships_user_id"),
        "user_school_memberships",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_school_memberships_campus_id"),
        "user_school_memberships",
        ["campus_id"],
        unique=False,
    )

    # ── Deterministic backfill from the legacy single-campus column ──
    # Every existing user keeps the school they already had.
    op.execute(
        sa.text(
            """
            INSERT INTO user_school_memberships
                (user_id, campus_id, role, is_default, is_active)
            SELECT
                u.id,
                u.campus_id,
                COALESCE(u.role, 'staff'),
                1,
                1
            FROM users u
            WHERE u.campus_id IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_user_school_memberships_campus_id"),
        table_name="user_school_memberships",
    )
    op.drop_index(
        op.f("ix_user_school_memberships_user_id"),
        table_name="user_school_memberships",
    )
    op.drop_table("user_school_memberships")
