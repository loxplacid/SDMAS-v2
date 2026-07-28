from __future__ import annotations

from app.domains.auth.models import User
from app.infrastructure.database import Base


def test_model_registered():
    assert "users" in Base.metadata.tables


def test_table_name():
    assert User.__tablename__ == "users"


def test_columns():
    table = Base.metadata.tables["users"]
    cols = {c.name: c for c in table.columns}

    assert cols["id"].primary_key is True
    assert cols["email"].nullable is False
    assert cols["email"].type.length == 255
    assert cols["email"].unique is True
    assert cols["username"].nullable is False
    assert cols["username"].type.length == 100
    assert cols["username"].unique is True
    assert cols["password_hash"].nullable is False
    assert cols["password_hash"].type.length == 255
    assert cols["display_name"].nullable is False
    assert cols["display_name"].type.length == 200
    assert cols["role"].nullable is False
    assert cols["role"].type.length == 50
    assert cols["is_active"].nullable is False
    assert cols["created_at"].nullable is False
    assert cols["updated_at"].nullable is False


def test_model_repr():
    user = User(id=1, username="admin", role="admin")
    assert "User" in repr(user)
    assert "admin" in repr(user)