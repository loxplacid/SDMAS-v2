"""create risk engine tables (risk_rule_configs, risk_findings)

Revision ID: 031_create_risk_engine_tables
Revises: 030_create_user_school_memberships
Create Date: 2026-08-01 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "031_create_risk_engine_tables"
down_revision: Union[str, None] = "030_create_user_school_memberships"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "risk_rule_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("campus_id", sa.Integer(), nullable=True),
        sa.Column("rule_code", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("thresholds", sa.JSON(), nullable=False),
        sa.Column("severity_overrides", sa.JSON(), nullable=True),
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
            "campus_id", "rule_code", name="uq_risk_rule_config_campus_rule"
        ),
    )
    op.create_index(
        op.f("ix_risk_rule_configs_campus_id"),
        "risk_rule_configs",
        ["campus_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_risk_rule_configs_rule_code"),
        "risk_rule_configs",
        ["rule_code"],
        unique=False,
    )

    op.create_table(
        "risk_findings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("campus_id", sa.Integer(), nullable=True),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=True),
        sa.Column("rule_code", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_verified_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.Integer(), nullable=True),
        sa.Column("resolved_reason", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "campus_id",
            "entity_type",
            "entity_id",
            "rule_code",
            "status",
            name="uq_risk_finding_entity_rule",
        ),
    )
    op.create_index(
        op.f("ix_risk_findings_campus_id"),
        "risk_findings",
        ["campus_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_risk_findings_entity_type"),
        "risk_findings",
        ["entity_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_risk_findings_entity_id"),
        "risk_findings",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_risk_findings_student_id"),
        "risk_findings",
        ["student_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_risk_findings_rule_code"),
        "risk_findings",
        ["rule_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_risk_findings_category"),
        "risk_findings",
        ["category"],
        unique=False,
    )
    op.create_index(
        op.f("ix_risk_findings_severity"),
        "risk_findings",
        ["severity"],
        unique=False,
    )
    op.create_index(
        op.f("ix_risk_findings_status"),
        "risk_findings",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("risk_findings")
    op.drop_table("risk_rule_configs")
