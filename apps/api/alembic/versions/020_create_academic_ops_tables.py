"""Create academic_ops tables: rooms, time_slots, timetable_entries,
substitutions, exam_schedules, grading_structures, grade_records, curricula.

Revision ID: 020
Revises: 019
Create Date: 2026-07-30
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "020"
down_revision: str | None = "019"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ── rooms ──────────────────────────────────────────────────────────
    op.create_table(
        "rooms",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("building", sa.String(length=100), nullable=True),
        sa.Column("floor", sa.String(length=20), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("room_type", sa.String(length=50), nullable=False, server_default="classroom"),
        sa.Column("campus_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campus_id"], ["campuses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_room_code"),
        sa.UniqueConstraint("name", "building", name="uq_room_name_building"),
    )
    op.create_index("ix_rooms_campus_id", "rooms", ["campus_id"])
    op.create_index("ix_rooms_status", "rooms", ["status"])
    op.create_index("ix_rooms_room_type", "rooms", ["room_type"])

    # ── time_slots ─────────────────────────────────────────────────────
    op.create_table(
        "time_slots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.String(length=5), nullable=False),
        sa.Column("end_time", sa.String(length=5), nullable=False),
        sa.Column("slot_type", sa.String(length=20), nullable=False, server_default="regular"),
        sa.Column("campus_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campus_id"], ["campuses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("day_of_week", "start_time", "end_time", name="uq_timeslot_day_time"),
    )
    op.create_index("ix_time_slots_campus_id", "time_slots", ["campus_id"])
    op.create_index("ix_time_slots_status", "time_slots", ["status"])
    op.create_index("ix_time_slots_day_of_week", "time_slots", ["day_of_week"])

    # ── timetable_entries ──────────────────────────────────────────────
    op.create_table(
        "timetable_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("academic_year_id", sa.Integer(), nullable=False),
        sa.Column("term_id", sa.Integer(), nullable=True),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=True),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("time_slot_id", sa.Integer(), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("campus_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["term_id"], ["terms.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["section_id"], ["sections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["time_slot_id"], ["time_slots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campus_id"], ["campuses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "class_id", "section_id", "time_slot_id", "day_of_week",
            name="uq_timetable_entry",
        ),
    )
    op.create_index("ix_timetable_entries_academic_year_id", "timetable_entries", ["academic_year_id"])
    op.create_index("ix_timetable_entries_class_id", "timetable_entries", ["class_id"])
    op.create_index("ix_timetable_entries_section_id", "timetable_entries", ["section_id"])
    op.create_index("ix_timetable_entries_teacher_id", "timetable_entries", ["teacher_id"])
    op.create_index("ix_timetable_entries_room_id", "timetable_entries", ["room_id"])
    op.create_index("ix_timetable_entries_time_slot_id", "timetable_entries", ["time_slot_id"])
    op.create_index("ix_timetable_entries_day_of_week", "timetable_entries", ["day_of_week"])
    op.create_index("ix_timetable_entries_status", "timetable_entries", ["status"])
    op.create_index("ix_timetable_entries_campus_id", "timetable_entries", ["campus_id"])

    # ── substitutions ──────────────────────────────────────────────────
    op.create_table(
        "substitutions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("timetable_entry_id", sa.Integer(), nullable=False),
        sa.Column("original_teacher_id", sa.Integer(), nullable=False),
        sa.Column("substitute_teacher_id", sa.Integer(), nullable=False),
        sa.Column("substitution_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("campus_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["timetable_entry_id"], ["timetable_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["original_teacher_id"], ["teachers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["substitute_teacher_id"], ["teachers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campus_id"], ["campuses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_substitutions_timetable_entry_id", "substitutions", ["timetable_entry_id"])
    op.create_index("ix_substitutions_original_teacher_id", "substitutions", ["original_teacher_id"])
    op.create_index("ix_substitutions_substitute_teacher_id", "substitutions", ["substitute_teacher_id"])
    op.create_index("ix_substitutions_substitution_date", "substitutions", ["substitution_date"])
    op.create_index("ix_substitutions_status", "substitutions", ["status"])
    op.create_index("ix_substitutions_campus_id", "substitutions", ["campus_id"])

    # ── exam_schedules ─────────────────────────────────────────────────
    op.create_table(
        "exam_schedules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("academic_year_id", sa.Integer(), nullable=False),
        sa.Column("term_id", sa.Integer(), nullable=True),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=True),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("exam_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.String(length=5), nullable=False),
        sa.Column("end_time", sa.String(length=5), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("invigilator_id", sa.Integer(), nullable=True),
        sa.Column("max_marks", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("pass_marks", sa.Integer(), nullable=True),
        sa.Column("campus_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="scheduled"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["term_id"], ["terms.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["section_id"], ["sections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["invigilator_id"], ["teachers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["campus_id"], ["campuses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exam_schedules_academic_year_id", "exam_schedules", ["academic_year_id"])
    op.create_index("ix_exam_schedules_class_id", "exam_schedules", ["class_id"])
    op.create_index("ix_exam_schedules_subject_id", "exam_schedules", ["subject_id"])
    op.create_index("ix_exam_schedules_exam_date", "exam_schedules", ["exam_date"])
    op.create_index("ix_exam_schedules_room_id", "exam_schedules", ["room_id"])
    op.create_index("ix_exam_schedules_status", "exam_schedules", ["status"])
    op.create_index("ix_exam_schedules_campus_id", "exam_schedules", ["campus_id"])

    # ── grading_structures ─────────────────────────────────────────────
    op.create_table(
        "grading_structures",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("academic_year_id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=True),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("min_percentage", sa.Float(), nullable=False),
        sa.Column("max_percentage", sa.Float(), nullable=False),
        sa.Column("grade_point", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("campus_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["campus_id"], ["campuses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "academic_year_id", "class_id", "subject_id", "name",
            name="uq_grading_structure",
        ),
    )
    op.create_index("ix_grading_structures_academic_year_id", "grading_structures", ["academic_year_id"])
    op.create_index("ix_grading_structures_class_id", "grading_structures", ["class_id"])
    op.create_index("ix_grading_structures_subject_id", "grading_structures", ["subject_id"])
    op.create_index("ix_grading_structures_status", "grading_structures", ["status"])
    op.create_index("ix_grading_structures_campus_id", "grading_structures", ["campus_id"])

    # ── grade_records ──────────────────────────────────────────────────
    op.create_table(
        "grade_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("enrollment_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("grading_structure_id", sa.Integer(), nullable=True),
        sa.Column("marks_obtained", sa.Float(), nullable=True),
        sa.Column("max_marks", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("grade", sa.String(length=5), nullable=True),
        sa.Column("grade_point", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("term_id", sa.Integer(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("campus_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["enrollment_id"], ["enrollments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["grading_structure_id"], ["grading_structures.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["term_id"], ["terms.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["campus_id"], ["campuses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "enrollment_id", "subject_id", "term_id", name="uq_grade_record",
        ),
    )
    op.create_index("ix_grade_records_enrollment_id", "grade_records", ["enrollment_id"])
    op.create_index("ix_grade_records_subject_id", "grade_records", ["subject_id"])
    op.create_index("ix_grade_records_term_id", "grade_records", ["term_id"])
    op.create_index("ix_grade_records_status", "grade_records", ["status"])
    op.create_index("ix_grade_records_campus_id", "grade_records", ["campus_id"])

    # ── curricula ──────────────────────────────────────────────────────
    op.create_table(
        "curricula",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("academic_year_id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("term_id", sa.Integer(), nullable=True),
        sa.Column("topics", sa.Text(), nullable=True),
        sa.Column("objectives", sa.Text(), nullable=True),
        sa.Column("total_hours", sa.Integer(), nullable=True),
        sa.Column("syllabus", sa.Text(), nullable=True),
        sa.Column("textbook", sa.Text(), nullable=True),
        sa.Column("campus_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["term_id"], ["terms.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["campus_id"], ["campuses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "academic_year_id", "class_id", "subject_id", name="uq_curriculum",
        ),
    )
    op.create_index("ix_curricula_academic_year_id", "curricula", ["academic_year_id"])
    op.create_index("ix_curricula_class_id", "curricula", ["class_id"])
    op.create_index("ix_curricula_subject_id", "curricula", ["subject_id"])
    op.create_index("ix_curricula_status", "curricula", ["status"])
    op.create_index("ix_curricula_campus_id", "curricula", ["campus_id"])


def downgrade() -> None:
    op.drop_table("curricula")
    op.drop_table("grade_records")
    op.drop_table("grading_structures")
    op.drop_table("exam_schedules")
    op.drop_table("substitutions")
    op.drop_table("timetable_entries")
    op.drop_table("time_slots")
    op.drop_table("rooms")
