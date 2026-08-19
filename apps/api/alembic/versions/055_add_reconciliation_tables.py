"""Add universal reconciliation engine tables.

Revision ID: 055_add_reconciliation_tables
Revises: 054_add_lineage_tables
Create Date: 2026-08-17

Adds the universal reconciliation engine (app/platform/reconciliation):

- ``reconciliation_runs``           — one reconciliation pass between a
  source and a target dataset (status, summary, approval)
- ``reconciliation_rule_configs``   — named, reusable matching/comparison
  rules (match keys + normalizers + tolerance fields)
- ``reconciliation_matches``        — per-record result with differences
- ``reconciliation_exceptions``     — out-of-tolerance / unmatched records
  requiring manual review
- ``reconciliation_approvals``      — approval trail (approve/reject/escalate)
- ``reconciliation_evidence``       — evidence pointers (audit, files,
  source records, reports)

This is a *generic* framework for future use cases (payment↔invoice,
legacy student↔canonical student, attendance↔biometric, transport↔boarding,
source↔migrated target, inventory↔physical count) — the domain-specific
``payment_reconciliations`` / ``reconciliation_items`` tables in
``school_finance`` are untouched.  Runs are idempotent via
``idempotency_key`` (UNIQUE per campus).

JSON columns use the dialect-aware helper (JSONB on PostgreSQL, JSON
elsewhere) mirroring the model ``JSONType`` decorator.  Every table carries
``campus_id`` (direct tenant scoping).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "055_add_reconciliation_tables"
down_revision: str | None = "054_add_lineage_tables"
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
        "reconciliation_rule_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("run_type", sa.String(80), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("match_keys", _json_type(), nullable=True),
        sa.Column("comparison_fields", _json_type(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.UniqueConstraint("campus_id", "name", name="uq_reconciliation_rule_name"),
    )
    op.create_index(
        "ix_reconciliation_rule_configs_campus_id",
        "reconciliation_rule_configs",
        ["campus_id"],
    )
    op.create_index(
        "ix_reconciliation_rule_configs_run_type",
        "reconciliation_rule_configs",
        ["run_type"],
    )

    op.create_table(
        "reconciliation_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("run_type", sa.String(80), nullable=False),
        sa.Column("source_dataset", sa.String(255), nullable=False),
        sa.Column("target_dataset", sa.String(255), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("match_keys", _json_type(), nullable=True),
        sa.Column("comparison_fields", _json_type(), nullable=True),
        sa.Column("idempotency_key", sa.String(200), nullable=True),
        sa.Column(
            "rule_config_id",
            sa.Integer(),
            sa.ForeignKey("reconciliation_rule_configs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("summary", _json_type(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint(
            "campus_id", "idempotency_key", name="uq_reconciliation_run_idempotency"
        ),
    )
    op.create_index("ix_reconciliation_runs_campus_id", "reconciliation_runs", ["campus_id"])
    op.create_index("ix_reconciliation_runs_run_type", "reconciliation_runs", ["run_type"])
    op.create_index("ix_reconciliation_runs_status", "reconciliation_runs", ["status"])

    op.create_table(
        "reconciliation_matches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("reconciliation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_ref", sa.String(255), nullable=False),
        sa.Column("source_payload", _json_type(), nullable=True),
        sa.Column("target_ref", sa.String(255), nullable=True),
        sa.Column("target_payload", _json_type(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="matched"),
        sa.Column("differences", _json_type(), nullable=True),
        sa.Column("within_tolerance", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("exception_code", sa.String(80), nullable=True),
        sa.Column("exception_reason", sa.String(1000), nullable=True),
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
        sa.UniqueConstraint("run_id", "source_ref", name="uq_reconciliation_match_source"),
    )
    op.create_index("ix_reconciliation_matches_campus_id", "reconciliation_matches", ["campus_id"])
    op.create_index("ix_reconciliation_matches_run_id", "reconciliation_matches", ["run_id"])
    op.create_index("ix_reconciliation_matches_status", "reconciliation_matches", ["status"])

    op.create_table(
        "reconciliation_exceptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("reconciliation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "match_id",
            sa.Integer(),
            sa.ForeignKey("reconciliation_matches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="warning"),
        sa.Column("reason", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("resolution", _json_type(), nullable=True),
        sa.Column("resolved_by", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
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
    )
    op.create_index(
        "ix_reconciliation_exceptions_campus_id",
        "reconciliation_exceptions",
        ["campus_id"],
    )
    op.create_index("ix_reconciliation_exceptions_run_id", "reconciliation_exceptions", ["run_id"])
    op.create_index(
        "ix_reconciliation_exceptions_match_id",
        "reconciliation_exceptions",
        ["match_id"],
    )
    op.create_index(
        "ix_reconciliation_exceptions_status",
        "reconciliation_exceptions",
        ["status"],
    )

    op.create_table(
        "reconciliation_approvals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("reconciliation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("approver_id", sa.Integer(), nullable=True),
        sa.Column("comment", sa.String(1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_reconciliation_approvals_campus_id",
        "reconciliation_approvals",
        ["campus_id"],
    )
    op.create_index("ix_reconciliation_approvals_run_id", "reconciliation_approvals", ["run_id"])

    op.create_table(
        "reconciliation_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("reconciliation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("match_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(30), nullable=False, server_default="audit"),
        sa.Column("reference", sa.String(512), nullable=False),
        sa.Column("checksum", sa.String(128), nullable=True),
        sa.Column("note", sa.String(1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_reconciliation_evidence_campus_id",
        "reconciliation_evidence",
        ["campus_id"],
    )
    op.create_index("ix_reconciliation_evidence_run_id", "reconciliation_evidence", ["run_id"])
    op.create_index("ix_reconciliation_evidence_kind", "reconciliation_evidence", ["kind"])
    op.create_index(
        "ix_reconciliation_evidence_run_kind_ref",
        "reconciliation_evidence",
        ["run_id", "kind", "reference"],
    )


def downgrade() -> None:
    op.drop_table("reconciliation_evidence")
    op.drop_table("reconciliation_approvals")
    op.drop_table("reconciliation_exceptions")
    op.drop_table("reconciliation_matches")
    op.drop_table("reconciliation_runs")
    op.drop_table("reconciliation_rule_configs")
