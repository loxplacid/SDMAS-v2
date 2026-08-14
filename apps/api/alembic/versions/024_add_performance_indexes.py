"""add performance indexes for N+1 queries and notification polling

Revision ID: 024_add_performance_indexes
Revises: d29e45f87a2c
Create Date: 2026-07-31 22:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "024_add_performance_indexes"
down_revision: str | None = "d30_add_student_portal_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- timetable_entries ----
    # Single-column class/section/teacher/room/time_slot indexes already exist
    # from 020_create_academic_ops_tables; only the new composites and the
    # subject_id index are added here.
    op.create_index("ix_timetable_entries_subject_id", "timetable_entries", ["subject_id"])
    op.create_index(
        "ix_timetable_entries_class_day",
        "timetable_entries",
        ["class_id", "day_of_week"],
    )
    op.create_index(
        "ix_timetable_entries_teacher_day",
        "timetable_entries",
        ["teacher_id", "day_of_week"],
    )
    op.create_index(
        "ix_timetable_entries_room_day",
        "timetable_entries",
        ["room_id", "day_of_week"],
    )

    # ---- substitutions ----
    # Single-column teacher/timetable_entry indexes already exist from 020;
    # only the (timetable_entry_id, substitution_date) composite is new.
    op.create_index(
        "ix_substitutions_entry_date",
        "substitutions",
        ["timetable_entry_id", "substitution_date"],
    )

    # ---- exam_schedules ----
    # academic_year_id/class_id/subject_id/room_id single-column indexes already
    # exist from 020; only term_id/section_id/invigilator_id are new here.
    op.create_index("ix_exam_schedules_term_id", "exam_schedules", ["term_id"])
    op.create_index(
        "ix_exam_schedules_section_id", "exam_schedules", ["section_id"]
    )
    op.create_index(
        "ix_exam_schedules_invigilator_id",
        "exam_schedules",
        ["invigilator_id"],
    )

    # ---- grade_records ----
    # ix_grade_records_term_id already exists from 020; only the grading
    # structure index is new here.
    op.create_index(
        "ix_grade_records_grading_structure_id",
        "grade_records",
        ["grading_structure_id"],
    )

    # ---- curricula ----
    # academic_year_id/class_id/subject_id indexes already exist from 020; only
    # the term_id index is new here.
    op.create_index("ix_curricula_term_id", "curricula", ["term_id"])

    # ---- attendance_records (composite for duplicate check) ----
    op.create_index(
        "ix_attendance_records_student_section_date",
        "attendance_records",
        ["student_id", "section_id", "attendance_date"],
    )

    # ---- notifications (polling: WHERE user_id=? AND read_at IS NULL) ----
    op.create_index(
        "ix_notifications_user_read",
        "notifications",
        ["user_id", "read_at"],
    )

    # ---- fee_dues (composite for get_by_student_and_structure) ----
    op.create_index(
        "ix_fee_dues_student_structure",
        "fee_dues",
        ["student_id", "fee_structure_id"],
    )

    # ---- assignments ----
    op.create_index("ix_assignments_teacher_id", "assignments", ["teacher_id"])
    op.create_index("ix_assignments_term_id", "assignments", ["term_id"])


def downgrade() -> None:
    op.drop_index("ix_assignments_term_id", table_name="assignments")
    op.drop_index("ix_assignments_teacher_id", table_name="assignments")
    op.drop_index(
        "ix_fee_dues_student_structure", table_name="fee_dues"
    )
    op.drop_index(
        "ix_notifications_user_read", table_name="notifications"
    )
    op.drop_index(
        "ix_attendance_records_student_section_date",
        table_name="attendance_records",
    )
    op.drop_index("ix_curricula_term_id", table_name="curricula")
    op.drop_index(
        "ix_grade_records_grading_structure_id",
        table_name="grade_records",
    )
    op.drop_index(
        "ix_exam_schedules_invigilator_id",
        table_name="exam_schedules",
    )
    op.drop_index(
        "ix_exam_schedules_section_id", table_name="exam_schedules"
    )
    op.drop_index("ix_exam_schedules_term_id", table_name="exam_schedules")
    op.drop_index(
        "ix_substitutions_entry_date", table_name="substitutions"
    )
    op.drop_index(
        "ix_timetable_entries_room_day", table_name="timetable_entries"
    )
    op.drop_index(
        "ix_timetable_entries_teacher_day",
        table_name="timetable_entries",
    )
    op.drop_index(
        "ix_timetable_entries_class_day", table_name="timetable_entries"
    )
    op.drop_index(
        "ix_timetable_entries_subject_id", table_name="timetable_entries"
    )
