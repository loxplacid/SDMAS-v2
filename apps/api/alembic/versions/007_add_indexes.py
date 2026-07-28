"""add database indexes for query performance

Revision ID: 007_add_indexes
Revises: 006_create_users
Create Date: 2026-07-28

"""

from collections.abc import Sequence

from alembic import op

revision: str = "007_add_indexes"
down_revision: str | None = "006_create_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- students ----
    op.create_index("ix_students_status", "students", ["status"])
    op.create_index(
        "ix_students_first_name_last_name",
        "students",
        ["first_name", "last_name"],
    )

    # ---- academic_years ----
    op.create_index("ix_academic_years_status", "academic_years", ["status"])

    # ---- classes ----
    op.create_index("ix_classes_academic_year_id", "classes", ["academic_year_id"])
    op.create_index("ix_classes_status", "classes", ["status"])

    # ---- sections ----
    op.create_index("ix_sections_class_id", "sections", ["class_id"])
    op.create_index("ix_sections_status", "sections", ["status"])

    # ---- enrollments ----
    op.create_index(
        "ix_enrollments_student_id", "enrollments", ["student_id"]
    )
    op.create_index(
        "ix_enrollments_academic_year_id", "enrollments", ["academic_year_id"]
    )
    op.create_index("ix_enrollments_class_id", "enrollments", ["class_id"])
    op.create_index(
        "ix_enrollments_section_id", "enrollments", ["section_id"]
    )

    # ---- terms ----
    op.create_index(
        "ix_terms_academic_year_id", "terms", ["academic_year_id"]
    )

    # ---- teacher_assignments ----
    op.create_index(
        "ix_teacher_assignments_teacher_id",
        "teacher_assignments",
        ["teacher_id"],
    )
    op.create_index(
        "ix_teacher_assignments_class_id",
        "teacher_assignments",
        ["class_id"],
    )
    op.create_index(
        "ix_teacher_assignments_subject_id",
        "teacher_assignments",
        ["subject_id"],
    )

    # ---- attendance_records ----
    op.create_index(
        "ix_attendance_records_student_id",
        "attendance_records",
        ["student_id"],
    )
    op.create_index(
        "ix_attendance_records_academic_year_id",
        "attendance_records",
        ["academic_year_id"],
    )
    op.create_index(
        "ix_attendance_records_class_id",
        "attendance_records",
        ["class_id"],
    )
    op.create_index(
        "ix_attendance_records_section_id",
        "attendance_records",
        ["section_id"],
    )
    op.create_index(
        "ix_attendance_records_attendance_date",
        "attendance_records",
        ["attendance_date"],
    )
    op.create_index(
        "ix_attendance_records_status",
        "attendance_records",
        ["status"],
    )

    # ---- fee_structures ----
    op.create_index(
        "ix_fee_structures_academic_year_id",
        "fee_structures",
        ["academic_year_id"],
    )
    op.create_index(
        "ix_fee_structures_class_id",
        "fee_structures",
        ["class_id"],
    )
    op.create_index(
        "ix_fee_structures_fee_type_id",
        "fee_structures",
        ["fee_type_id"],
    )

    # ---- fee_dues ----
    op.create_index(
        "ix_fee_dues_student_id", "fee_dues", ["student_id"]
    )
    op.create_index(
        "ix_fee_dues_academic_year_id", "fee_dues", ["academic_year_id"]
    )
    op.create_index(
        "ix_fee_dues_fee_structure_id",
        "fee_dues",
        ["fee_structure_id"],
    )
    op.create_index("ix_fee_dues_status", "fee_dues", ["status"])

    # ---- payments ----
    op.create_index(
        "ix_payments_student_id", "payments", ["student_id"]
    )
    op.create_index(
        "ix_payments_fee_due_id", "payments", ["fee_due_id"]
    )
    op.create_index(
        "ix_payments_payment_date", "payments", ["payment_date"]
    )
    op.create_index(
        "ix_payments_receipt_number", "payments", ["receipt_number"]
    )

    # ---- users ----
    op.create_index("ix_users_role", "users", ["role"])


def downgrade() -> None:
    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_payments_receipt_number", table_name="payments")
    op.drop_index("ix_payments_payment_date", table_name="payments")
    op.drop_index("ix_payments_fee_due_id", table_name="payments")
    op.drop_index("ix_payments_student_id", table_name="payments")
    op.drop_index("ix_fee_dues_status", table_name="fee_dues")
    op.drop_index("ix_fee_dues_fee_structure_id", table_name="fee_dues")
    op.drop_index("ix_fee_dues_academic_year_id", table_name="fee_dues")
    op.drop_index("ix_fee_dues_student_id", table_name="fee_dues")
    op.drop_index("ix_fee_structures_fee_type_id", table_name="fee_structures")
    op.drop_index("ix_fee_structures_class_id", table_name="fee_structures")
    op.drop_index(
        "ix_fee_structures_academic_year_id", table_name="fee_structures"
    )
    op.drop_index(
        "ix_attendance_records_status", table_name="attendance_records"
    )
    op.drop_index(
        "ix_attendance_records_attendance_date",
        table_name="attendance_records",
    )
    op.drop_index(
        "ix_attendance_records_section_id", table_name="attendance_records"
    )
    op.drop_index(
        "ix_attendance_records_class_id", table_name="attendance_records"
    )
    op.drop_index(
        "ix_attendance_records_academic_year_id",
        table_name="attendance_records",
    )
    op.drop_index(
        "ix_attendance_records_student_id", table_name="attendance_records"
    )
    op.drop_index(
        "ix_teacher_assignments_subject_id",
        table_name="teacher_assignments",
    )
    op.drop_index(
        "ix_teacher_assignments_class_id", table_name="teacher_assignments"
    )
    op.drop_index(
        "ix_teacher_assignments_teacher_id",
        table_name="teacher_assignments",
    )
    op.drop_index("ix_terms_academic_year_id", table_name="terms")
    op.drop_index("ix_enrollments_section_id", table_name="enrollments")
    op.drop_index("ix_enrollments_class_id", table_name="enrollments")
    op.drop_index(
        "ix_enrollments_academic_year_id", table_name="enrollments"
    )
    op.drop_index("ix_enrollments_student_id", table_name="enrollments")
    op.drop_index("ix_sections_status", table_name="sections")
    op.drop_index("ix_sections_class_id", table_name="sections")
    op.drop_index("ix_classes_status", table_name="classes")
    op.drop_index("ix_classes_academic_year_id", table_name="classes")
    op.drop_index("ix_academic_years_status", table_name="academic_years")
    op.drop_index(
        "ix_students_first_name_last_name", table_name="students"
    )
    op.drop_index("ix_students_status", table_name="students")