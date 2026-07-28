from __future__ import annotations

import pytest
from sqlalchemy import inspect

from app.domains.attendance.models import AttendanceRecord
from app.infrastructure.database import Base


def test_attendance_model_registered():
    assert "attendance_records" in Base.metadata.tables


def test_attendance_table_name():
    assert AttendanceRecord.__tablename__ == "attendance_records"


def test_attendance_columns():
    table = Base.metadata.tables["attendance_records"]
    columns = {c.name: c for c in table.columns}

    assert columns["id"].primary_key is True

    assert columns["student_id"].nullable is False
    assert columns["academic_year_id"].nullable is False
    assert columns["class_id"].nullable is False
    assert columns["section_id"].nullable is False

    assert columns["attendance_date"].nullable is False
    assert columns["attendance_date"].type.length == 10

    assert columns["status"].nullable is False
    assert columns["status"].type.length == 20

    assert columns["notes"].nullable is True

    assert columns["recorded_at"].nullable is False
    assert columns["updated_at"].nullable is False


def test_attendance_model_attributes():
    attrs = [c.key for c in AttendanceRecord.__table__.columns]
    assert "id" in attrs
    assert "student_id" in attrs
    assert "academic_year_id" in attrs
    assert "class_id" in attrs
    assert "section_id" in attrs
    assert "attendance_date" in attrs
    assert "status" in attrs
    assert "notes" in attrs
    assert "recorded_at" in attrs
    assert "updated_at" in attrs