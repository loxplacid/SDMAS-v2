"""create attendance_records table

Revision ID: 003_create_attendance
Revises: c7e7eca3b567
Create Date: 2026-07-28
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "003_create_attendance"
down_revision: Union[str, None] = "c7e7eca3b567"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attendance_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("academic_year_id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=False),
        sa.Column("attendance_date", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], ),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"], ),
        sa.ForeignKeyConstraint(["section_id"], ["sections.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "student_id", "attendance_date", "section_id",
            name="uq_attendance_student_date_section",
        ),
    )


def downgrade() -> None:
    op.drop_table("attendance_records")