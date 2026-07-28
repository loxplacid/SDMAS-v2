from __future__ import annotations

import pytest
from sqlalchemy import inspect

from app.domains.student.models import Student
from app.infrastructure.database import Base


def test_student_model_registered():
    assert "students" in Base.metadata.tables


def test_student_table_name():
    assert Student.__tablename__ == "students"


def test_student_columns():
    table = Base.metadata.tables["students"]
    columns = {c.name: c for c in table.columns}

    assert columns["id"].primary_key is True

    assert columns["first_name"].nullable is False
    assert columns["first_name"].type.length == 100

    assert columns["last_name"].nullable is False
    assert columns["last_name"].type.length == 100

    assert columns["student_number"].nullable is False
    assert columns["student_number"].type.length == 50
    assert columns["student_number"].unique is True

    assert columns["email"].nullable is True
    assert columns["email"].type.length == 255

    assert columns["date_of_birth"].nullable is True

    assert columns["status"].nullable is False
    assert columns["status"].type.length == 20

    assert columns["created_at"].nullable is False
    assert columns["updated_at"].nullable is False


def test_student_model_attributes():
    attrs = [c.key for c in Student.__table__.columns]
    assert "id" in attrs
    assert "first_name" in attrs
    assert "last_name" in attrs
    assert "student_number" in attrs
    assert "email" in attrs
    assert "date_of_birth" in attrs
    assert "status" in attrs
    assert "created_at" in attrs
    assert "updated_at" in attrs