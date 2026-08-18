"""Add policy-as-code tables.

Revision ID: 056_add_policy_tables
Revises: 055_add_reconciliation_tables
Create Date: 2026-08-17

Adds the policy-as-code foundation (app/platform/policy):

- ``policy_definitions``  — named policies with a stable business key
  (``policy_id``) and a scope (attendance, fees, admissions, approvals,
  compliance, security, workflow, global)
- ``policy_versions``     — immutable versioned snapshots: rules +
  exceptions + applicability, effective dates, approval metadata
- ``policy_evaluations``  — persisted evaluation records (traceability:
  policy version + input data + result)

Rules are JSON data (conditions over a closed operator set), never code.
The engine is deterministic; every evaluation is persisted and traceable.

JSON columns use the dialect-aware helper (JSONB on PostgreSQL, JSON
elsewhere) mirroring the model ``JSONType`` decorator.  Every table carries
``campus_id`` (direct tenant scoping).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "056_add_policy_tables"
down_revision: str | None = "055_add_reconciliation_tables"
branch_labels: str | None = None
depends_on: str | None = None


def _json_type():
    """JSONB on PostgreSQL, JSON elsewhere — mirrors the model JSONType."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import JSONB

        return JSONB()
    return sa.JSON()


def upgrade() -> None:
    op.create_table(
        "policy_definitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("policy_id", sa.String(200), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("scope", sa.String(40), nullable=False),
        sa.Column("scope_ref", sa.String(80), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("campus_id", "policy_id", name="uq_policy_definition_key"),
    )
    op.create_index("ix_policy_definitions_campus_id", "policy_definitions", ["campus_id"])
    op.create_index("ix_policy_definitions_scope", "policy_definitions", ["scope"])
    op.create_index("ix_policy_definitions_status", "policy_definitions", ["status"])

    op.create_table(
        "policy_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "policy_def_id",
            sa.Integer(),
            sa.ForeignKey("policy_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("rules", _json_type(), nullable=True),
        sa.Column("exceptions", _json_type(), nullable=True),
        sa.Column("applicability", _json_type(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_note", sa.String(1000), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("policy_def_id", "version", name="uq_policy_version_number"),
    )
    op.create_index("ix_policy_versions_campus_id", "policy_versions", ["campus_id"])
    op.create_index("ix_policy_versions_policy_def_id", "policy_versions", ["policy_def_id"])
    op.create_index("ix_policy_versions_status", "policy_versions", ["status"])

    op.create_table(
        "policy_evaluations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("policy_id", sa.String(200), nullable=False),
        sa.Column(
            "policy_def_id",
            sa.Integer(),
            sa.ForeignKey("policy_definitions.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "policy_version_id",
            sa.Integer(),
            sa.ForeignKey("policy_versions.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("subject_type", sa.String(80), nullable=True),
        sa.Column("subject_id", sa.String(200), nullable=True),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=True),
        sa.Column("result", _json_type(), nullable=True),
        sa.Column("input_snapshot", _json_type(), nullable=True),
        sa.Column("evaluated_by", sa.Integer(), nullable=True),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_policy_evaluations_campus_id", "policy_evaluations", ["campus_id"])
    op.create_index("ix_policy_evaluations_policy_id", "policy_evaluations", ["policy_id"])
    op.create_index("ix_policy_evaluations_decision", "policy_evaluations", ["decision"])
    op.create_index(
        "ix_policy_evaluations_evaluated_at",
        "policy_evaluations",
        ["evaluated_at"],
    )
    op.create_index(
        "ix_policy_evaluations_subject_type",
        "policy_evaluations",
        ["subject_type"],
    )
    op.create_index(
        "ix_policy_evaluations_policy_version",
        "policy_evaluations",
        ["policy_id", "version"],
    )
    op.create_index(
        "ix_policy_evaluations_subject",
        "policy_evaluations",
        ["subject_type", "subject_id"],
    )


def downgrade() -> None:
    op.drop_table("policy_evaluations")
    op.drop_table("policy_versions")
    op.drop_table("policy_definitions")
