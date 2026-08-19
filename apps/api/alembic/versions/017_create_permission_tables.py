"""create roles, permissions, and role_permissions tables

Revision ID: 017_create_permission_tables
Revises: 016_campus_id_columns
Create Date: 2026-07-30
"""
from __future__ import annotations

import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.domains.auth.permissions import ALL_PERMISSIONS, ROLE_PERMISSIONS

revision: str = "017_create_permission_tables"
down_revision: Union[str, None] = "016_campus_id_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # ── roles table ──
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_roles_code", "roles", ["code"])

    # Seed system roles
    role_data = [
        ("admin", "Administrator", "Full system access"),
        ("principal", "Principal", "School leadership overview"),
        ("accountant", "Accountant", "Financial management"),
        ("staff", "Staff", "General staff access"),
        ("teacher", "Teacher", "Classes, attendance & students"),
        ("student", "Student", "My attendance, fees & schedule"),
        ("parent", "Parent", "Children overview & payments"),
    ]
    for code, label, description in role_data:
        desc_sql = "NULL" if description is None else f"'{description}'"
        op.execute(
            sa.text(
                "INSERT INTO roles "
                "(code, label, description, is_system, created_at) "
                # is_system is BOOLEAN: PostgreSQL rejects the bare integer 1
                # (SQLite tolerates it), so use the SQL TRUE literal.
                f"VALUES ('{code}', '{label}', {desc_sql}, TRUE, '{now}') "
                "ON CONFLICT DO NOTHING"
            )
        )

    # ── permissions table ──
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_permissions_code", "permissions", ["code"])

    # Seed all permissions
    for perm_code in ALL_PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO permissions "
                "(code, description, created_at) "
                f"VALUES ('{perm_code}', NULL, '{now}') "
                "ON CONFLICT DO NOTHING"
            )
        )

    # ── role_permissions association table ──
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"], ["permissions.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )

    # Seed role → permission mappings
    for role_code, perms in ROLE_PERMISSIONS.items():
        for perm_code in perms:
            op.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id) "
                    "SELECT r.id, p.id FROM roles r, permissions p "
                    f"WHERE r.code = '{role_code}' AND p.code = '{perm_code}' "
                    "ON CONFLICT DO NOTHING"
                )
            )


def downgrade() -> None:
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
