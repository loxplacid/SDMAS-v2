"""add optional campus_id columns to existing tables

Revision ID: 011_add_campus_id_columns
Revises: 010_create_institution_hierarchy
Create Date: 2026-07-29

NOTE: For SQLite, we add columns without FOREIGN KEY constraints because
SQLite does not support ALTER TABLE ADD CONSTRAINT. The ForeignKey is
enforced at the SQLAlchemy ORM level and can be added as a real DB
constraint on PostgreSQL via a separate migration.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "011_add_campus_id_columns"
down_revision: Union[str, None] = "010_create_institution_hierarchy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES_TO_UPDATE = [
    "students",
    "teachers",
    "academic_years",
    "classes",
    "sections",
    "terms",
    "subjects",
    "enrollments",
    "attendance_records",
    "fee_types",
    "fee_structures",
    "fee_dues",
    "payments",
    "teacher_assignments",
    "users",
    "notifications",
]


def upgrade() -> None:
    for table in TABLES_TO_UPDATE:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column("campus_id", sa.Integer(), nullable=True)
            )
            batch_op.create_index(
                f"ix_{table}_campus_id", ["campus_id"],
            )

    # Set campus_id = 1 (Main Campus) for all existing records
    for table in TABLES_TO_UPDATE:
        op.execute(
            sa.text(f"UPDATE {table} SET campus_id = 1 WHERE campus_id IS NULL")
        )


def downgrade() -> None:
    for table in TABLES_TO_UPDATE:
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_index(f"ix_{table}_campus_id")
            batch_op.drop_column("campus_id")
