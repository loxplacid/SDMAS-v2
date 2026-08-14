"""add student portal tables (assignments, assignment_submissions)

Revision ID: d30_add_student_portal_tables
Revises: d29e45f87a2c
Create Date: 2026-08-10

The ``assignments`` and ``assignment_submissions`` models
(``app.domains.student_portal.models``) were added to the ORM without a
corresponding migration, so the table never existed in any database built
through Alembic.  Migrations ``024`` (indexes) and ``034`` (tenant
``campus_id``) reference ``assignments`` and could never apply — the whole
chain therefore never bootstrapped a fresh database.

This migration creates the two tables from the models.  ``campus_id`` is
deliberately omitted from ``assignments``: migration ``034`` adds the column
+ tenant index in the hardening sequence, exactly as it does for
``guardian_links``.  ``assignment_submissions`` has no tenant column in the
model.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d30_add_student_portal_tables"
down_revision: str | None = "d29e45f87a2c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=True),
        sa.Column("teacher_id", sa.Integer(), nullable=True),
        sa.Column("academic_year_id", sa.Integer(), nullable=False),
        sa.Column("term_id", sa.Integer(), nullable=True),
        # NOTE: no campus_id here — migration 034 adds it as the tenant
        # hardening step (mirrors guardian_links).
        sa.Column("assignment_type", sa.String(length=30), nullable=False),
        sa.Column("max_score", sa.Float(), nullable=True),
        sa.Column("passing_score", sa.Float(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("available_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("available_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column("allow_late_submission", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("lms_external_id", sa.String(length=255), nullable=True),
        sa.Column("lms_source", sa.String(length=50), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["section_id"], ["sections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["academic_year_id"], ["academic_years.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["term_id"], ["terms.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assignments_subject_id", "assignments", ["subject_id"])
    op.create_index("ix_assignments_class_id", "assignments", ["class_id"])
    op.create_index("ix_assignments_section_id", "assignments", ["section_id"])
    op.create_index(
        "ix_assignments_academic_year_id", "assignments", ["academic_year_id"]
    )

    op.create_table(
        "assignment_submissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("submitted_text", sa.Text(), nullable=True),
        sa.Column("file_url", sa.String(length=500), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("grade", sa.String(length=10), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("graded_by", sa.Integer(), nullable=True),
        sa.Column("graded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_late", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("lms_external_id", sa.String(length=255), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"], ["assignments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["students.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["graded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assignment_id", "student_id", name="uq_submission_per_student"
        ),
    )
    op.create_index(
        "ix_assignment_submissions_assignment_id",
        "assignment_submissions",
        ["assignment_id"],
    )
    op.create_index(
        "ix_assignment_submissions_student_id",
        "assignment_submissions",
        ["student_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_assignment_submissions_student_id",
        table_name="assignment_submissions",
    )
    op.drop_index(
        "ix_assignment_submissions_assignment_id",
        table_name="assignment_submissions",
    )
    op.drop_table("assignment_submissions")
    op.drop_index("ix_assignments_academic_year_id", table_name="assignments")
    op.drop_index("ix_assignments_section_id", table_name="assignments")
    op.drop_index("ix_assignments_class_id", table_name="assignments")
    op.drop_index("ix_assignments_subject_id", table_name="assignments")
    op.drop_table("assignments")
