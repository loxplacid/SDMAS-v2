"""Add universal exception management tables.

Revision ID: 062_add_exception_tables
Revises: 061_add_ledger_tables
Create Date: 2026-08-18

TASK 17 (Universal Exception Management) adds a canonical, tenant-scoped
representation for every system-detected issue (data quality, financial,
risk, migration, compliance, operational, manual) that requires tracking
and resolution.

Three tables:

- ``system_exceptions``     — one row per detected issue.  The
  ``(campus_id, source_domain, source_type, source_id)`` tuple is unique,
  so the same issue can never be recorded twice.  Optional links to
  ``cases`` (human workflow) and ``workflow_instances`` (structured
  process) keep backward compatibility with the existing case system.
- ``system_exception_events`` — immutable timeline of every action taken
  on an exception (creation, transitions, assignment, evidence,
  resolution, closure), keyed by (exception_id, event_seq).
- ``exception_sla_configs`` — configurable resolution deadlines per
  (campus, exception_type, severity); campus rows override global rows.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "062_add_exception_tables"
down_revision: str | None = "061_add_ledger_tables"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "system_exceptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="CASCADE"),
            nullable=True,
        ),
        # Source provenance
        sa.Column("source_domain", sa.String(50), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        # Classification
        sa.Column("exception_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("rule_code", sa.String(100), nullable=True),
        # Entity reference
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("students.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Title & description
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # Lifecycle
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        # Ownership
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # SLA
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        # Resolution
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("resolution_type", sa.String(50), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "resolved_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "closed_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Evidence
        sa.Column("evidence", sa.JSON(), nullable=True),
        # Links
        sa.Column(
            "case_id",
            sa.Integer(),
            sa.ForeignKey("cases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "workflow_instance_id",
            sa.Integer(),
            sa.ForeignKey("workflow_instances.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Audit
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "acknowledged_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("in_progress_at", sa.DateTime(timezone=True), nullable=True),
        # Concurrency
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # Uniqueness: the same source record can only produce one exception.
        sa.UniqueConstraint(
            "campus_id",
            "source_domain",
            "source_type",
            "source_id",
            name="uq_system_exception_source",
        ),
        sa.CheckConstraint(
            "severity IN ('info','low','medium','high','critical')",
            name="ck_system_exception_severity",
        ),
        sa.CheckConstraint(
            "status IN ('open','acknowledged','in_progress','resolved','closed')",
            name="ck_system_exception_status",
        ),
    )
    op.create_index(
        "ix_system_exceptions_campus_id", "system_exceptions", ["campus_id"]
    )
    op.create_index(
        "ix_system_exceptions_source_domain", "system_exceptions", ["source_domain"]
    )
    op.create_index(
        "ix_system_exceptions_exception_type", "system_exceptions", ["exception_type"]
    )
    op.create_index(
        "ix_system_exceptions_severity", "system_exceptions", ["severity"]
    )
    op.create_index(
        "ix_system_exceptions_status", "system_exceptions", ["status"]
    )
    op.create_index(
        "ix_system_exceptions_entity",
        "system_exceptions",
        ["entity_type", "entity_id"],
    )
    op.create_index(
        "ix_system_exceptions_student_id", "system_exceptions", ["student_id"]
    )
    op.create_index("ix_system_exceptions_owner_id", "system_exceptions", ["owner_id"])
    op.create_index("ix_system_exceptions_due_at", "system_exceptions", ["due_at"])

    op.create_table(
        "system_exception_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "exception_id",
            sa.Integer(),
            sa.ForeignKey("system_exceptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_name", sa.String(200), nullable=True),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "exception_id", "event_seq", name="uq_system_exception_events_seq"
        ),
    )
    op.create_index(
        "ix_system_exception_events_exception_id",
        "system_exception_events",
        ["exception_id"],
    )
    op.create_index(
        "ix_system_exception_events_event_type",
        "system_exception_events",
        ["event_type"],
    )

    op.create_table(
        "exception_sla_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("exception_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("after_hours", sa.Float(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "updated_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "campus_id",
            "exception_type",
            "severity",
            name="uq_exception_sla_config_type_severity",
        ),
    )
    op.create_index(
        "ix_exception_sla_configs_campus_id", "exception_sla_configs", ["campus_id"]
    )


def downgrade() -> None:
    op.drop_table("exception_sla_configs")
    op.drop_table("system_exception_events")
    op.drop_table("system_exceptions")
