"""create fees tables (fee_types, fee_structures, fee_dues, payments)

Revision ID: 004_create_fees
Revises: 003_create_attendance
Create Date: 2026-07-28
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "004_create_fees"
down_revision: Union[str, None] = "003_create_attendance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fee_types",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_fee_type_name"),
    )

    op.create_table(
        "fee_structures",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("academic_year_id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("fee_type_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("frequency", sa.String(length=50), nullable=False, server_default="annual"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], ),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"], ),
        sa.ForeignKeyConstraint(["fee_type_id"], ["fee_types.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "academic_year_id", "class_id", "fee_type_id",
            name="uq_fee_structure_per_year_class_type",
        ),
    )

    op.create_table(
        "fee_dues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("academic_year_id", sa.Integer(), nullable=False),
        sa.Column("fee_structure_id", sa.Integer(), nullable=False),
        sa.Column("original_amount", sa.Integer(), nullable=False),
        sa.Column("amount_paid", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("due_date", sa.String(length=10), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="unpaid"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], ),
        sa.ForeignKeyConstraint(["fee_structure_id"], ["fee_structures.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "student_id", "fee_structure_id",
            name="uq_fee_due_per_student_structure",
        ),
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("fee_due_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("payment_date", sa.String(length=10), nullable=True),
        sa.Column("payment_method", sa.String(length=50), nullable=True),
        sa.Column("receipt_number", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ),
        sa.ForeignKeyConstraint(["fee_due_id"], ["fee_dues.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("receipt_number", name="uq_payment_receipt_number"),
    )


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("fee_dues")
    op.drop_table("fee_structures")
    op.drop_table("fee_types")