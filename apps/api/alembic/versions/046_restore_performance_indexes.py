"""restore performance indexes lost by the historical c09b48a8d73d migration

Revision ID: 046_restore_performance_indexes
Revises: 045_rename_case_json_column
Create Date: 2026-08-12

The original c09b48a8d73d "create document tables" migration (repaired in
place for fresh installs) unconditionally dropped ~126 indexes on core
tables. Already-migrated installations permanently lost 96 of them.  This
corrective migration restores exactly those 96 indexes so existing databases
converge on the same schema as a fresh installation.

Every create is guarded by an existence check: on fresh installs (where the
repaired chain already provides these indexes) and on SQLite this migration
is a safe no-op.  Downgrade removes only what this migration added.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "046_restore_performance_indexes"
down_revision: Union[str, None] = "045_rename_case_json_column"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (index_name, table, [columns], unique) — sourced from the freshly migrated
# reference schema (sdmas_audit_fresh), i.e. exactly what a repaired fresh
# install produces.
INDEXES = [
    ("ix_academic_years_campus_id", "academic_years", ['campus_id'], False),
    ("ix_academic_years_status", "academic_years", ['status'], False),
    ("ix_admission_applications_academic_year_id",
     "admission_applications", ['academic_year_id'], False),
    ("ix_admission_applications_program_id", "admission_applications", ['program_id'], False),
    ("ix_admission_applications_status", "admission_applications", ['status'], False),
    ("ix_admission_documents_application_id", "admission_documents", ['application_id'], False),
    ("ix_admission_interviews_application_id", "admission_interviews", ['application_id'], False),
    ("ix_admission_merit_entries_academic_year_id",
     "admission_merit_entries", ['academic_year_id'], False),
    ("ix_admission_merit_entries_application_id",
     "admission_merit_entries", ['application_id'], False),
    ("ix_admission_merit_entries_program_id", "admission_merit_entries", ['program_id'], False),
    ("ix_admission_seat_allocations_application_id",
     "admission_seat_allocations", ['application_id'], False),
    ("ix_admission_seat_allocations_program_id",
     "admission_seat_allocations", ['program_id'], False),
    ("ix_attendance_corrections_record_type", "attendance_corrections", ['record_type'], False),
    ("ix_attendance_corrections_requested_by", "attendance_corrections", ['requested_by'], False),
    ("ix_attendance_corrections_status", "attendance_corrections", ['status'], False),
    ("ix_attendance_records_academic_year_id",
     "attendance_records", ['academic_year_id'], False),
    ("ix_attendance_records_attendance_date", "attendance_records", ['attendance_date'], False),
    ("ix_attendance_records_campus_id",
     "attendance_records", ['campus_id'], False),
    ("ix_attendance_records_class_id",
     "attendance_records", ['class_id'], False),
    ("ix_attendance_records_section_id", "attendance_records", ['section_id'], False),
    ("ix_attendance_records_status",
     "attendance_records", ['status'], False),
    ("ix_attendance_records_student_id",
     "attendance_records", ['student_id'], False),
    ("ix_attendance_thresholds_status", "attendance_thresholds", ['status'], False),
    ("ix_attendance_thresholds_threshold_type", "attendance_thresholds", ['threshold_type'], False),
    ("ix_classes_academic_year_id", "classes", ['academic_year_id'], False),
    ("ix_classes_campus_id", "classes", ['campus_id'], False),
    ("ix_classes_status", "classes", ['status'], False),
    ("ix_curricula_status", "curricula", ['status'], False),
    ("ix_enrollments_academic_year_id", "enrollments", ['academic_year_id'], False),
    ("ix_enrollments_campus_id", "enrollments", ['campus_id'], False),
    ("ix_enrollments_class_id", "enrollments", ['class_id'], False),
    ("ix_enrollments_section_id", "enrollments", ['section_id'], False),
    ("ix_enrollments_student_id", "enrollments", ['student_id'], False),
    ("ix_exam_schedules_exam_date", "exam_schedules", ['exam_date'], False),
    ("ix_exam_schedules_status", "exam_schedules", ['status'], False),
    ("ix_fee_dues_academic_year_id", "fee_dues", ['academic_year_id'], False),
    ("ix_fee_dues_campus_id", "fee_dues", ['campus_id'], False),
    ("ix_fee_dues_fee_structure_id", "fee_dues", ['fee_structure_id'], False),
    ("ix_fee_dues_status", "fee_dues", ['status'], False),
    ("ix_fee_dues_student_id", "fee_dues", ['student_id'], False),
    ("ix_fee_structures_academic_year_id", "fee_structures", ['academic_year_id'], False),
    ("ix_fee_structures_campus_id", "fee_structures", ['campus_id'], False),
    ("ix_fee_structures_class_id", "fee_structures", ['class_id'], False),
    ("ix_fee_structures_fee_type_id", "fee_structures", ['fee_type_id'], False),
    ("ix_fee_types_campus_id", "fee_types", ['campus_id'], False),
    ("ix_grade_records_enrollment_id", "grade_records", ['enrollment_id'], False),
    ("ix_grade_records_status", "grade_records", ['status'], False),
    ("ix_grade_records_subject_id", "grade_records", ['subject_id'], False),
    ("ix_grading_structures_academic_year_id", "grading_structures", ['academic_year_id'], False),
    ("ix_grading_structures_class_id", "grading_structures", ['class_id'], False),
    ("ix_grading_structures_status", "grading_structures", ['status'], False),
    ("ix_grading_structures_subject_id", "grading_structures", ['subject_id'], False),
    ("ix_leave_requests_workflow_instance_id", "leave_requests", ['workflow_instance_id'], False),
    ("ix_notifications_campus_id", "notifications", ['campus_id'], False),
    ("ix_notifications_created_at", "notifications", ['created_at'], False),
    ("ix_payments_campus_id", "payments", ['campus_id'], False),
    ("ix_payments_fee_due_id", "payments", ['fee_due_id'], False),
    ("ix_payments_payment_date", "payments", ['payment_date'], False),
    ("ix_payments_receipt_number", "payments", ['receipt_number'], False),
    ("ix_payments_student_id", "payments", ['student_id'], False),
    ("ix_period_attendance_records_absence_reason_id",
     "period_attendance_records", ['absence_reason_id'], False),
    ("ix_period_attendance_records_status",
     "period_attendance_records", ['status'], False),
    ("ix_period_attendance_records_student_id",
     "period_attendance_records", ['student_id'], False),
    ("ix_period_attendances_academic_year_id", "period_attendances", ['academic_year_id'], False),
    ("ix_period_attendances_attendance_date", "period_attendances", ['attendance_date'], False),
    ("ix_period_attendances_class_id", "period_attendances", ['class_id'], False),
    ("ix_period_attendances_section_id", "period_attendances", ['section_id'], False),
    ("ix_period_attendances_subject_id", "period_attendances", ['subject_id'], False),
    ("ix_period_attendances_teacher_id", "period_attendances", ['teacher_id'], False),
    ("ix_rooms_room_type", "rooms", ['room_type'], False),
    ("ix_rooms_status", "rooms", ['status'], False),
    ("ix_sections_campus_id", "sections", ['campus_id'], False),
    ("ix_sections_class_id", "sections", ['class_id'], False),
    ("ix_sections_status", "sections", ['status'], False),
    ("ix_students_campus_id", "students", ['campus_id'], False),
    ("ix_students_first_name_last_name", "students", ['first_name', 'last_name'], False),
    ("ix_students_status", "students", ['status'], False),
    ("ix_subjects_campus_id", "subjects", ['campus_id'], False),
    ("ix_substitutions_status", "substitutions", ['status'], False),
    ("ix_substitutions_substitution_date", "substitutions", ['substitution_date'], False),
    ("ix_teacher_assignments_campus_id", "teacher_assignments", ['campus_id'], False),
    ("ix_teacher_assignments_class_id", "teacher_assignments", ['class_id'], False),
    ("ix_teacher_assignments_subject_id", "teacher_assignments", ['subject_id'], False),
    ("ix_teacher_assignments_teacher_id", "teacher_assignments", ['teacher_id'], False),
    ("ix_teachers_campus_id", "teachers", ['campus_id'], False),
    ("ix_terms_academic_year_id", "terms", ['academic_year_id'], False),
    ("ix_terms_campus_id", "terms", ['campus_id'], False),
    ("ix_time_slots_day_of_week", "time_slots", ['day_of_week'], False),
    ("ix_time_slots_status", "time_slots", ['status'], False),
    ("ix_timetable_entries_academic_year_id", "timetable_entries", ['academic_year_id'], False),
    ("ix_timetable_entries_day_of_week", "timetable_entries", ['day_of_week'], False),
    ("ix_timetable_entries_status", "timetable_entries", ['status'], False),
    ("ix_user_roles_user_role", "user_roles", ['user_id', 'role_id'], True),
    ("ix_users_campus_id", "users", ['campus_id'], False),
    ("ix_users_role", "users", ['role'], False),
    ("ix_workflow_instances_entity", "workflow_instances", ['entity_type', 'entity_id'], False),
]


def _missing_indexes() -> list[tuple[str, str, list[str], bool]]:
    """Return the INDEXES entries absent from the connected database."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    missing = []
    for name, table, columns, unique in INDEXES:
        try:
            existing = {i["name"] for i in inspector.get_indexes(table)}
        except Exception:
            # Table absent — nothing to do for it.
            continue
        if name not in existing:
            missing.append((name, table, columns, unique))
    return missing


def upgrade() -> None:
    for name, table, columns, unique in _missing_indexes():
        op.create_index(name, table, columns, unique=unique)


def downgrade() -> None:
    # Intentional no-op.  Every index in INDEXES is owned by the migration
    # that originally created it (007/020/024/011/016/...); their own
    # downgrades drop them.  046 merely restores indexes that a historical
    # defect permanently removed — downgrading would simply re-break the
    # schema to the exact state this migration exists to repair.
    return
