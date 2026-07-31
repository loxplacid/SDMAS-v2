"""Create user_roles association table for multi-role support.

Revision ID: 018
Revises: 017
Create Date: 2026-07-30

This migration adds a user_roles M2M join table linking users to roles,
enabling users to hold multiple roles simultaneously.

Migration strategy:
1. Create ``user_roles`` table (user_id → users.id, role_id → roles.id)
2. Backfill rows for every existing user based on their ``role`` field
   (ensures backward compatibility — every existing user gets their
   primary role linked in the M2M table)
3. Add composite index on (user_id, role_id)

The User model's ``role`` string field is preserved (backward compatible).
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "018"
down_revision: str | None = "017_create_permission_tables"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Create user_roles join table ──────────────────────────────
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )

    # ── 2. Backfill: link every user to their current role ───────────
    # Roles were seeded in migration 017; the code column matches
    # the User.role string field.
    users = conn.execute(
        sa.text("SELECT id, role FROM users")
    ).mappings().all()

    roles = conn.execute(
        sa.text("SELECT id, code FROM roles")
    ).mappings().all()

    role_map = {r["code"]: r["id"] for r in roles}

    values: list[dict[str, int]] = []
    for u in users:
        role_id = role_map.get(u["role"])
        if role_id is not None:
            values.append({"user_id": u["id"], "role_id": role_id})

    if values:
        conn.execute(
            sa.text(
                "INSERT INTO user_roles (user_id, role_id) VALUES (:user_id, :role_id)"
            ),
            values,
        )

    # ── 3. Composite index for efficient lookups ─────────────────────
    op.create_index(
        "ix_user_roles_user_role",
        "user_roles",
        ["user_id", "role_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_user_roles_user_role", table_name="user_roles")
    op.drop_table("user_roles")
