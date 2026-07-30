"""create workflow engine tables

Revision ID: 013_create_workflow_engine
Revises: 012_create_admission_tables
Create Date: 2026-07-29
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "013_create_workflow_engine"
down_revision: Union[str, None] = "012_create_admission_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Workflow Definitions
    # ------------------------------------------------------------------
    op.create_table(
        "workflows",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "entity_type", sa.String(100), nullable=False,
            comment="Domain entity this workflow applies to (e.g., 'leave_request', 'purchase_order')",
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_workflows_code"),
    )

    # ------------------------------------------------------------------
    # Workflow Steps
    # ------------------------------------------------------------------
    op.create_table(
        "workflow_steps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("label", sa.String(200), nullable=True),
        sa.Column("step_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_initial", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("is_final", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column(
            "assigned_role", sa.String(50), nullable=True,
            comment="Role required to act on this step (null = any authenticated user)",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workflow_id"], ["workflows.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_steps_workflow_id", "workflow_steps", ["workflow_id"])

    # ------------------------------------------------------------------
    # Workflow Transitions
    # ------------------------------------------------------------------
    op.create_table(
        "workflow_transitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("from_step_id", sa.Integer(), nullable=False),
        sa.Column("to_step_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(100), nullable=True),
        sa.Column(
            "required_role", sa.String(50), nullable=True,
            comment="Role required to perform this transition",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workflow_id"], ["workflows.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["from_step_id"], ["workflow_steps.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["to_step_id"], ["workflow_steps.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workflow_transitions_workflow_id", "workflow_transitions", ["workflow_id"],
    )

    # ------------------------------------------------------------------
    # Workflow Actions
    # ------------------------------------------------------------------
    op.create_table(
        "workflow_actions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("step_id", sa.Integer(), nullable=False),
        sa.Column(
            "action_type", sa.String(50), nullable=False,
            comment="send_email | notify_user | webhook | create_record | custom",
        ),
        sa.Column(
            "action_config", sa.Text(), nullable=True,
            comment="JSON configuration for the action",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workflow_id"], ["workflows.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["step_id"], ["workflow_steps.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workflow_actions_workflow_id", "workflow_actions", ["workflow_id"],
    )

    # ------------------------------------------------------------------
    # Workflow Instances
    # ------------------------------------------------------------------
    op.create_table(
        "workflow_instances",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("current_step_id", sa.Integer(), nullable=False),
        sa.Column(
            "entity_type", sa.String(100), nullable=False,
            comment="Polymorphic entity type (e.g., 'leave_request')",
        ),
        sa.Column(
            "entity_id", sa.Integer(), nullable=False,
            comment="ID of the entity record this instance belongs to",
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workflow_id"], ["workflows.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["current_step_id"], ["workflow_steps.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workflow_instances_workflow_id", "workflow_instances", ["workflow_id"],
    )
    op.create_index(
        "ix_workflow_instances_entity", "workflow_instances",
        ["entity_type", "entity_id"],
    )

    # ------------------------------------------------------------------
    # Approval History
    # ------------------------------------------------------------------
    op.create_table(
        "approval_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instance_id", sa.Integer(), nullable=False),
        sa.Column("from_step_id", sa.Integer(), nullable=True),
        sa.Column("to_step_id", sa.Integer(), nullable=True),
        sa.Column(
            "action", sa.String(30), nullable=False,
            comment="approve | reject | return | submit | cancel",
        ),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["instance_id"], ["workflow_instances.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["from_step_id"], ["workflow_steps.id"], ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["to_step_id"], ["workflow_steps.id"], ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_approval_history_instance_id", "approval_history", ["instance_id"],
    )


def downgrade() -> None:
    op.drop_table("approval_history")
    op.drop_table("workflow_instances")
    op.drop_table("workflow_actions")
    op.drop_table("workflow_transitions")
    op.drop_table("workflow_steps")
    op.drop_table("workflows")
