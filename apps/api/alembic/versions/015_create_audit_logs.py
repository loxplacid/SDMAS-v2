"""create audit_logs table for compliance auditing

Revision ID: 015_create_audit_logs
Revises: 014_create_leave_requests
Create Date: 2026-07-30
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "015_create_audit_logs"
down_revision: Union[str, None] = "014_create_leave_requests"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("username", sa.String(length=100), nullable=True),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.String(length=100), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=50), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("campus_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_logs_user_id", "audit_logs", ["user_id"]
    )
    op.create_index(
        "ix_audit_logs_action", "audit_logs", ["action"]
    )
    op.create_index(
        "ix_audit_logs_resource_type", "audit_logs", ["resource_type"]
    )
    op.create_index(
        "ix_audit_logs_resource_id", "audit_logs", ["resource_id"]
    )
    op.create_index(
        "ix_audit_logs_campus_id", "audit_logs", ["campus_id"]
    )
    op.create_index(
        "ix_audit_logs_created_at", "audit_logs", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_campus_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_resource_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_resource_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")
