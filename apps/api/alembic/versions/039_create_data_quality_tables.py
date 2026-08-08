"""create data quality findings table

Revision ID: 039_create_data_quality_tables
Revises: 038_add_invoice_period_unique
Create Date: 2026-08-06 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "039_create_data_quality_tables"
down_revision: Union[str, None] = "038_add_invoice_period_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "data_quality_findings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("campus_id", sa.Integer(), nullable=True),
        sa.Column("check_code", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=True),
        sa.Column("field", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False),
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
            "check_code",
            "entity_type",
            "entity_id",
            "field",
            name="uq_data_quality_finding_entity_check",
        ),
    )
    op.create_index(
        op.f("ix_data_quality_findings_campus_id"),
        "data_quality_findings",
        ["campus_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_data_quality_findings_check_code"),
        "data_quality_findings",
        ["check_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_data_quality_findings_category"),
        "data_quality_findings",
        ["category"],
        unique=False,
    )
    op.create_index(
        op.f("ix_data_quality_findings_severity"),
        "data_quality_findings",
        ["severity"],
        unique=False,
    )
    op.create_index(
        op.f("ix_data_quality_findings_entity_type"),
        "data_quality_findings",
        ["entity_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_data_quality_findings_entity_id"),
        "data_quality_findings",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_data_quality_findings_student_id"),
        "data_quality_findings",
        ["student_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_data_quality_findings_status"),
        "data_quality_findings",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("data_quality_findings")
