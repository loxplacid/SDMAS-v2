from __future__ import annotations

import datetime

import pytest
from sqlalchemy import inspect

from app.domains.academic.models import AcademicYear, Class, Section, Enrollment, Teacher, Subject, Term, TeacherAssignment
from app.infrastructure.database import Base


def test_academic_year_model_registered():
    assert "academic_years" in Base.metadata.tables


def test_academic_year_table_name():
    assert AcademicYear.__tablename__ == "academic_years"


def test_academic_year_columns():
    table = Base.metadata.tables["academic_years"]
    cols = {c.name: c for c in table.columns}

    assert cols["id"].primary_key is True
    assert cols["name"].nullable is False
    assert cols["name"].type.length == 100
    assert cols["name"].unique is True
    assert cols["start_date"].nullable is False
    assert cols["end_date"].nullable is False
    assert cols["status"].nullable is False
    assert cols["status"].type.length == 20
    assert cols["created_at"].nullable is False
    assert cols["updated_at"].nullable is False


def test_class_model_registered():
    assert "classes" in Base.metadata.tables


def test_class_table_name():
    assert Class.__tablename__ == "classes"


def test_class_columns():
    table = Base.metadata.tables["classes"]
    cols = {c.name: c for c in table.columns}

    assert cols["id"].primary_key is True
    assert cols["name"].nullable is False
    assert cols["name"].type.length == 100
    assert cols["academic_year_id"].nullable is False
    assert cols["status"].nullable is False
    assert cols["status"].type.length == 20
    assert cols["created_at"].nullable is False
    assert cols["updated_at"].nullable is False


def test_class_unique_constraint():
    table = Base.metadata.tables["classes"]
    uq_names = {getattr(c, "name", None) for c in table.constraints}
    assert "uq_class_name_per_year" in uq_names


def test_section_model_registered():
    assert "sections" in Base.metadata.tables


def test_section_table_name():
    assert Section.__tablename__ == "sections"


def test_section_columns():
    table = Base.metadata.tables["sections"]
    cols = {c.name: c for c in table.columns}

    assert cols["id"].primary_key is True
    assert cols["name"].nullable is False
    assert cols["name"].type.length == 100
    assert cols["class_id"].nullable is False
    assert cols["status"].nullable is False
    assert cols["status"].type.length == 20
    assert cols["created_at"].nullable is False
    assert cols["updated_at"].nullable is False


def test_enrollment_model_registered():
    assert "enrollments" in Base.metadata.tables


def test_enrollment_table_name():
    assert Enrollment.__tablename__ == "enrollments"


def test_enrollment_columns():
    table = Base.metadata.tables["enrollments"]
    cols = {c.name: c for c in table.columns}

    assert cols["id"].primary_key is True
    assert cols["student_id"].nullable is False
    assert cols["academic_year_id"].nullable is False
    assert cols["class_id"].nullable is True
    assert cols["section_id"].nullable is True
    assert cols["status"].nullable is False
    assert cols["status"].type.length == 20
    assert cols["enrolled_at"].nullable is False
    assert cols["created_at"].nullable is False
    assert cols["updated_at"].nullable is False


def test_enrollment_unique_constraint():
    table = Base.metadata.tables["enrollments"]
    uq_names = {getattr(c, "name", None) for c in table.constraints}
    assert "uq_student_enrollment_per_year" in uq_names


def test_model_repr():
    year = AcademicYear(id=1, name="2026")
    assert "AcademicYear" in repr(year)
    assert "2026" in repr(year)

    cls = Class(id=1, name="Grade 10", academic_year_id=1)
    assert "Class" in repr(cls)

    section = Section(id=1, name="A", class_id=1)
    assert "Section" in repr(section)

    enrollment = Enrollment(id=1, student_id=1, academic_year_id=1)
    assert "Enrollment" in repr(enrollment)

    teacher = Teacher(id=1, first_name="John", last_name="Doe")
    assert "Teacher" in repr(teacher)
    assert "John" in repr(teacher)

    subject = Subject(id=1, name="Math", code="MATH101")
    assert "Subject" in repr(subject)

    term = Term(id=1, name="Term 1", academic_year_id=1)
    assert "Term" in repr(term)

    assignment = TeacherAssignment(id=1, teacher_id=1, class_id=1)
    assert "TeacherAssignment" in repr(assignment)


# ---------------------------------------------------------------------------
# Teacher models
# ---------------------------------------------------------------------------


def test_teacher_model_registered():
    assert "teachers" in Base.metadata.tables


def test_teacher_table_name():
    assert Teacher.__tablename__ == "teachers"


def test_teacher_columns():
    table = Base.metadata.tables["teachers"]
    cols = {c.name: c for c in table.columns}

    assert cols["id"].primary_key is True
    assert cols["first_name"].nullable is False
    assert cols["first_name"].type.length == 100
    assert cols["last_name"].nullable is False
    assert cols["last_name"].type.length == 100
    assert cols["employee_number"].nullable is False
    assert cols["employee_number"].type.length == 50
    assert cols["employee_number"].unique is True
    assert cols["email"].nullable is True
    assert cols["status"].nullable is False
    assert cols["status"].type.length == 20
    assert cols["created_at"].nullable is False
    assert cols["updated_at"].nullable is False


# ---------------------------------------------------------------------------
# Subject models
# ---------------------------------------------------------------------------


def test_subject_model_registered():
    assert "subjects" in Base.metadata.tables


def test_subject_table_name():
    assert Subject.__tablename__ == "subjects"


def test_subject_columns():
    table = Base.metadata.tables["subjects"]
    cols = {c.name: c for c in table.columns}

    assert cols["id"].primary_key is True
    assert cols["name"].nullable is False
    assert cols["name"].type.length == 100
    assert cols["name"].unique is True
    assert cols["code"].nullable is False
    assert cols["code"].type.length == 50
    assert cols["code"].unique is True
    assert cols["description"].nullable is True
    assert cols["status"].nullable is False
    assert cols["status"].type.length == 20
    assert cols["created_at"].nullable is False
    assert cols["updated_at"].nullable is False


# ---------------------------------------------------------------------------
# Term models
# ---------------------------------------------------------------------------


def test_term_model_registered():
    assert "terms" in Base.metadata.tables


def test_term_table_name():
    assert Term.__tablename__ == "terms"


def test_term_columns():
    table = Base.metadata.tables["terms"]
    cols = {c.name: c for c in table.columns}

    assert cols["id"].primary_key is True
    assert cols["academic_year_id"].nullable is False
    assert cols["name"].nullable is False
    assert cols["name"].type.length == 100
    assert cols["start_date"].nullable is False
    assert cols["start_date"].type.length == 10
    assert cols["end_date"].nullable is False
    assert cols["end_date"].type.length == 10
    assert cols["status"].nullable is False
    assert cols["status"].type.length == 20
    assert cols["created_at"].nullable is False
    assert cols["updated_at"].nullable is False


# ---------------------------------------------------------------------------
# TeacherAssignment models
# ---------------------------------------------------------------------------


def test_teacher_assignment_model_registered():
    assert "teacher_assignments" in Base.metadata.tables


def test_teacher_assignment_table_name():
    assert TeacherAssignment.__tablename__ == "teacher_assignments"


def test_teacher_assignment_columns():
    table = Base.metadata.tables["teacher_assignments"]
    cols = {c.name: c for c in table.columns}

    assert cols["id"].primary_key is True
    assert cols["teacher_id"].nullable is False
    assert cols["class_id"].nullable is False
    assert cols["subject_id"].nullable is True
    assert cols["status"].nullable is False
    assert cols["status"].type.length == 20
    assert cols["created_at"].nullable is False
    assert cols["updated_at"].nullable is False


def test_teacher_assignment_unique_constraint():
    table = Base.metadata.tables["teacher_assignments"]
    uq_names = {getattr(c, "name", None) for c in table.constraints}
    assert "uq_assignment_class_subject" in uq_names