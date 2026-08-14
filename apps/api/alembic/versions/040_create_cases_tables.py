"""create case management tables

Revision ID: 040_create_cases_tables
Revises: 039_create_data_quality_tables
Create Date: 2026-08-08 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "040_create_cases_tables"
down_revision: Union[str, None] = "039_create_data_quality_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_number", sa.String(length=20), nullable=False),
        sa.Column("campus_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("case_type", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("original_priority", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("source_type", sa.String(length=30), nullable=False, server_default="manual"),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("student_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("assigned_to", sa.Integer(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.Integer(), nullable=True),
        sa.Column("resolved_reason", sa.Text(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
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
        sa.ForeignKeyConstraint(["campus_id"], ["campuses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["closed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_number", name="uq_cases_case_number"),
        sa.UniqueConstraint(
            "campus_id", "source_type", "source_id", name="uq_cases_source"
        ),
    )
    op.create_index(op.f("ix_cases_case_number"), "cases", ["case_number"], unique=False)
    op.create_index(op.f("ix_cases_campus_id"), "cases", ["campus_id"], unique=False)
    op.create_index(op.f("ix_cases_case_type"), "cases", ["case_type"], unique=False)
    op.create_index(op.f("ix_cases_priority"), "cases", ["priority"], unique=False)
    op.create_index(op.f("ix_cases_status"), "cases", ["status"], unique=False)
    op.create_index(op.f("ix_cases_assigned_to"), "cases", ["assigned_to"], unique=False)
    op.create_index(op.f("ix_cases_due_at"), "cases", ["due_at"], unique=False)
    op.create_index(op.f("ix_cases_student_id"), "cases", ["student_id"], unique=False)

    op.create_table(
        "case_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("event_seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_name", sa.String(length=200), nullable=True),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "event_seq", name="uq_case_events_seq"),
    )
    op.create_index(op.f("ix_case_events_case_id"), "case_events", ["case_id"], unique=False)
    op.create_index(op.f("ix_case_events_event_type"), "case_events", ["event_type"], unique=False)

    op.create_table(
        "case_comments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=True),
        sa.Column("author_name", sa.String(length=200), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_case_comments_case_id"), "case_comments", ["case_id"], unique=False)

    op.create_table(
        "case_evidence",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("reference_type", sa.String(length=50), nullable=True),
        sa.Column("reference_id", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("added_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["added_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_case_evidence_case_id"), "case_evidence", ["case_id"], unique=False)

    op.create_table(
        "case_sla_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("campus_id", sa.Integer(), nullable=True),
        sa.Column("case_type", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("after_hours", sa.Float(), nullable=True),
        sa.Column("escalation_after_hours", sa.Float(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_by", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(["campus_id"], ["campuses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "campus_id", "case_type", "priority", name="uq_case_sla_config_type_priority"
        ),
    )
    op.create_index(op.f("ix_case_sla_configs_campus_id"), "case_sla_configs", ["campus_id"], unique=False)

    # Seed global default SLA rows (campus_id NULL = applies to every campus).
    from app.domains.cases.models import CASE_PRIORITIES, CASE_TYPES

    defaults = {
        "critical": (4.0, 8.0),
        "high": (24.0, 48.0),
        "medium": (72.0, 144.0),
        "low": (168.0, 336.0),
    }
    conn = op.get_bind()
    for case_type in CASE_TYPES:
        for priority in CASE_PRIORITIES:
            after, escalation = defaults[priority]
            conn.execute(
                sa.text(
                    "INSERT INTO case_sla_configs "
                    "(campus_id, case_type, priority, after_hours, escalation_after_hours, enabled) "
                    # enabled is BOOLEAN: PostgreSQL rejects the bare integer 1
                    # (SQLite tolerates it), so use the SQL TRUE literal.
                    "VALUES (NULL, :t, :p, :a, :e, TRUE)"
                ),
                {"t": case_type, "p": priority, "a": after, "e": escalation},
            )


def downgrade() -> None:
    op.drop_table("case_sla_configs")
    op.drop_table("case_evidence")
    op.drop_table("case_comments")
    op.drop_table("case_events")
    op.drop_table("cases")
