"""Create attendance_intelligence tables: period_attendances,
period_attendance_records, absence_reasons, attendance_corrections,
attendance_thresholds.

Revision ID: 021
Revises: 020
Create Date: 2026-07-30
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "021"
down_revision: str | None = "020"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ── absence_reasons ────────────────────────────────────────────────
    op.create_table(
        "absence_reasons",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("campus_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campus_id"], ["campuses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_absence_reason_code"),
    )

    # ── period_attendances ─────────────────────────────────────────────
    op.create_table(
        "period_attendances",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("academic_year_id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("period_number", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.String(length=5), nullable=False),
        sa.Column("end_time", sa.String(length=5), nullable=False),
        sa.Column("campus_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["section_id"], ["sections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campus_id"], ["campuses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_period_attendances_section_id", "period_attendances", ["section_id"])
    op.create_index("ix_period_attendances_class_id", "period_attendances", ["class_id"])
    op.create_index("ix_period_attendances_subject_id", "period_attendances", ["subject_id"])
    op.create_index("ix_period_attendances_teacher_id", "period_attendances", ["teacher_id"])
    op.create_index("ix_period_attendances_academic_year_id", "period_attendances", ["academic_year_id"])
    op.create_index("ix_period_attendances_attendance_date", "period_attendances", ["attendance_date"])
    op.create_index("ix_period_attendances_campus_id", "period_attendances", ["campus_id"])

    # ── period_attendance_records ──────────────────────────────────────
    op.create_table(
        "period_attendance_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("period_attendance_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="present"),
        sa.Column("arrival_time", sa.String(length=5), nullable=True),
        sa.Column("departure_time", sa.String(length=5), nullable=True),
        sa.Column("late_minutes", sa.Integer(), nullable=True),
        sa.Column("early_departure_minutes", sa.Integer(), nullable=True),
        sa.Column("absence_reason_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["period_attendance_id"], ["period_attendances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["absence_reason_id"], ["absence_reasons.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("period_attendance_id", "student_id", name="uq_period_attendance_student"),
    )
    op.create_index("ix_period_attendance_records_student_id", "period_attendance_records", ["student_id"])
    op.create_index("ix_period_attendance_records_status", "period_attendance_records", ["status"])
    op.create_index("ix_period_attendance_records_absence_reason_id", "period_attendance_records", ["absence_reason_id"])

    # ── attendance_corrections ─────────────────────────────────────────
    op.create_table(
        "attendance_corrections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("record_type", sa.String(length=20), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("requested_by", sa.Integer(), nullable=False),
        sa.Column("requested_status", sa.String(length=20), nullable=False),
        sa.Column("previous_status", sa.String(length=20), nullable=True),
        sa.Column("absence_reason_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("campus_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["absence_reason_id"], ["absence_reasons.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["campus_id"], ["campuses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attendance_corrections_status", "attendance_corrections", ["status"])
    op.create_index("ix_attendance_corrections_record_type", "attendance_corrections", ["record_type"])
    op.create_index("ix_attendance_corrections_requested_by", "attendance_corrections", ["requested_by"])

    # ── attendance_thresholds ──────────────────────────────────────────
    op.create_table(
        "attendance_thresholds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("campus_id", sa.Integer(), nullable=True),
        sa.Column("academic_year_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("threshold_type", sa.String(length=20), nullable=False),
        sa.Column("percentage", sa.Float(), nullable=False),
        sa.Column("days_absent_threshold", sa.Integer(), nullable=True),
        sa.Column("consecutive_absences", sa.Integer(), nullable=True),
        sa.Column("notification_enabled", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("notification_channels", sa.String(length=100), nullable=True, server_default="in_app"),
        sa.Column("applies_to", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campus_id"], ["campuses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campus_id", "academic_year_id", "name", name="uq_attendance_threshold"),
    )
    op.create_index("ix_attendance_thresholds_campus_id", "attendance_thresholds", ["campus_id"])
    op.create_index("ix_attendance_thresholds_threshold_type", "attendance_thresholds", ["threshold_type"])
    op.create_index("ix_attendance_thresholds_status", "attendance_thresholds", ["status"])


def downgrade() -> None:
    op.drop_table("attendance_thresholds")
    op.drop_table("attendance_corrections")
    op.drop_table("period_attendance_records")
    op.drop_table("period_attendances")
    op.drop_table("absence_reasons")
