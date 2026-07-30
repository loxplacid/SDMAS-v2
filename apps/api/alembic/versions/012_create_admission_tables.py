"""create admission management tables

Revision ID: 012_create_admission_tables
Revises: 011_add_campus_id_columns
Create Date: 2026-07-29
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "012_create_admission_tables"
down_revision: Union[str, None] = "011_add_campus_id_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Admission Applications — core entity with workflow state
    # ------------------------------------------------------------------
    op.create_table(
        "admission_applications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("campus_id", sa.Integer(), nullable=True),
        sa.Column("academic_year_id", sa.Integer(), nullable=True),
        sa.Column("program_id", sa.Integer(), nullable=True),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("semester_id", sa.Integer(), nullable=True),
        sa.Column("applicant_name", sa.String(200), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("previous_education", sa.Text(), nullable=True),
        sa.Column("entrance_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="inquiry"),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campus_id"], ["campuses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["semester_id"], ["semesters.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admission_applications_status", "admission_applications", ["status"])
    op.create_index("ix_admission_applications_campus_id", "admission_applications", ["campus_id"])
    op.create_index("ix_admission_applications_program_id", "admission_applications", ["program_id"])
    op.create_index("ix_admission_applications_academic_year_id", "admission_applications", ["academic_year_id"])

    # ------------------------------------------------------------------
    # Admission Documents
    # ------------------------------------------------------------------
    op.create_table(
        "admission_documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("document_type", sa.String(100), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_url", sa.String(500), nullable=True),
        sa.Column("verification_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("verified_by", sa.Integer(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["admission_applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admission_documents_application_id", "admission_documents", ["application_id"])

    # ------------------------------------------------------------------
    # Admission Interviews
    # ------------------------------------------------------------------
    op.create_table(
        "admission_interviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("scheduled_date", sa.String(10), nullable=True),
        sa.Column("interview_mode", sa.String(50), nullable=True),
        sa.Column("panel_members", sa.Text(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["admission_applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admission_interviews_application_id", "admission_interviews", ["application_id"])

    # ------------------------------------------------------------------
    # Admission Merit Entries
    # ------------------------------------------------------------------
    op.create_table(
        "admission_merit_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("academic_year_id", sa.Integer(), nullable=False),
        sa.Column("total_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["admission_applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admission_merit_entries_application_id", "admission_merit_entries", ["application_id"])
    op.create_index("ix_admission_merit_entries_program_id", "admission_merit_entries", ["program_id"])
    op.create_index("ix_admission_merit_entries_academic_year_id", "admission_merit_entries", ["academic_year_id"])

    # ------------------------------------------------------------------
    # Admission Seat Allocations
    # ------------------------------------------------------------------
    op.create_table(
        "admission_seat_allocations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("merit_entry_id", sa.Integer(), nullable=True),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("fee_amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("allocated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="allocated"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["admission_applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["merit_entry_id"], ["admission_merit_entries.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admission_seat_allocations_application_id", "admission_seat_allocations", ["application_id"])
    op.create_index("ix_admission_seat_allocations_program_id", "admission_seat_allocations", ["program_id"])


def downgrade() -> None:
    op.drop_table("admission_seat_allocations")
    op.drop_table("admission_merit_entries")
    op.drop_table("admission_interviews")
    op.drop_table("admission_documents")
    op.drop_table("admission_applications")
