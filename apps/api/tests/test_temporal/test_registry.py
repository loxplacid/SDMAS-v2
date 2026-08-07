"""Registry and history-mirror DDL unit tests (The Archive, M1)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base
from app.temporal import tt_range_index_definition
from app.temporal.registry import TemporalTableRegistry

T = datetime(2024, 6, 1, 9, 0)


class VersionedClass(Base):
    """Fixture current table for the registry tests."""

    __tablename__ = "versioned_class"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    tt_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    tt_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


def test_history_mirror_shape() -> None:
    registry = TemporalTableRegistry()
    spec = registry.register("versioned_class")
    hist = Base.metadata.tables["versioned_class_history"]

    assert spec.history == "versioned_class_history"
    # Surrogate PK + preserved business key, demoted to a plain column.
    assert hist.c.id.primary_key
    assert "entity_id" in hist.c
    assert "label" in hist.c
    assert "tt_from" in hist.c
    assert "tt_to" in hist.c
    # Portable btree index over the version range.
    assert {ix.name for ix in hist.indexes} == {"ix_versioned_class_history_tt"}

    # Registering again is idempotent.
    assert registry.register("versioned_class") is spec


def test_tt_range_index_dialect_contract() -> None:
    name, cols, kwargs = tt_range_index_definition(
        "student_history", "tt_from", "tt_to", dialect="postgresql"
    )
    assert name == "ix_student_history_tt_gist"
    assert kwargs == {"postgresql_using": "gist"}
    assert str(cols[0]) == "tstzrange(tt_from, tt_to)"

    name, cols, kwargs = tt_range_index_definition(
        "student_history", "tt_from", "tt_to", dialect="sqlite"
    )
    assert name == "ix_student_history_tt"
    assert cols == ["tt_from", "tt_to"]
    assert kwargs == {}
