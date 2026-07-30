"""create leave_requests table and seed LEAVE_REQUEST workflow

Revision ID: 014_create_leave_requests
Revises: 013_create_workflow_engine
Create Date: 2026-07-29
"""
from __future__ import annotations

import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "014_create_leave_requests"
down_revision: Union[str, None] = "013_create_workflow_engine"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "leave_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("leave_type", sa.String(50), nullable=False),
        sa.Column("start_date", sa.String(10), nullable=False),
        sa.Column("end_date", sa.String(10), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("duration_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("workflow_instance_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workflow_instance_id"], ["workflow_instances.id"], ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leave_requests_user_id", "leave_requests", ["user_id"])
    op.create_index(
        "ix_leave_requests_workflow_instance_id",
        "leave_requests", ["workflow_instance_id"],
    )

    # ── Seed the LEAVE_REQUEST workflow template ──
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    op.execute(
        sa.text(
            "INSERT OR IGNORE INTO workflows "
            "(id, name, code, description, entity_type, status, created_at, updated_at) "
            "VALUES (1, 'Leave Request', 'LEAVE_REQUEST', "
            "'Standard leave approval process', 'leave_request', 'active', "
            f"'{now}', '{now}')"
        )
    )

    for step_id, name, label, order, initial, final, role in [
        (1, 'Draft', 'Draft', 0, 1, 0, None),
        (2, 'Submitted', 'Submitted', 1, 0, 0, None),
        (3, 'Manager Approval', 'Manager Approval', 2, 0, 0, 'admin'),
        (4, 'HR Approval', 'HR Approval', 3, 0, 0, 'admin'),
        (5, 'Approved', 'Approved', 4, 0, 1, None),
        (6, 'Rejected', 'Rejected', 5, 0, 1, None),
    ]:
        role_str = "NULL" if role is None else f"'{role}'"
        op.execute(
            sa.text(
                "INSERT OR IGNORE INTO workflow_steps "
                "(id, workflow_id, name, label, step_order, is_initial, is_final, assigned_role, created_at) "
                f"VALUES ({step_id}, 1, '{name}', '{label}', {order}, {initial}, {final}, "
                f"{role_str}, '{now}')"
            )
        )

    for t_id, from_step, to_step, tlabel, role in [
        (1, 1, 2, 'Submit', None),
        (2, 2, 3, 'Forward to Manager', None),
        (3, 3, 4, 'Forward to HR', 'admin'),
        (4, 3, 6, 'Reject', 'admin'),
        (5, 4, 5, 'Approve', 'admin'),
        (6, 4, 6, 'Reject', 'admin'),
    ]:
        role_str = "NULL" if role is None else f"'{role}'"
        op.execute(
            sa.text(
                "INSERT OR IGNORE INTO workflow_transitions "
                "(id, workflow_id, from_step_id, to_step_id, label, required_role, created_at) "
                f"VALUES ({t_id}, 1, {from_step}, {to_step}, '{tlabel}', "
                f"{role_str}, '{now}')"
            )
        )


def downgrade() -> None:
    op.drop_table("leave_requests")
