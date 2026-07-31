from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domains.jobs.models import JSONType
from app.infrastructure.database import Base


class MigrationRun(Base):
    """A single migration attempt for a specific entity type.

    One run is created per migration execution.  It tracks the source,
    status, and summary counts so operators can inspect what happened.
    """

    __tablename__ = "migration_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="e.g. users, students, academic_years, attendance, fees",
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True,
        comment="pending | validating | running | completed | failed | rolled_back",
    )
    source: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Description of the data source (file path, DB URL, etc.)",
    )

    total_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    is_dry_run: Mapped[bool] = mapped_column(nullable=False, default=False)
    summary: Mapped[dict[str, Any] | None] = mapped_column(
        JSONType, nullable=True, default=None,
    )

    started_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<MigrationRun id={self.id} entity={self.entity_type} "
            f"status={self.status} dry={self.is_dry_run}>"
        )


class MigrationLog(Base):
    """Row-level log for every record processed during a migration.

    Every legacy record produces exactly one log entry.  No record is
    ever silently discarded — even skipped/errored records are logged
    with a reason.
    """

    __tablename__ = "migration_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True,
    )
    level: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True,
        comment="imported | skipped | error | warning",
    )
    legacy_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Original ID from the legacy system",
    )
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
    )
    entity_subtype: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="e.g. academic_year, class, section",
    )
    message: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Human-readable description of what happened",
    )
    details: Mapped[dict[str, Any] | None] = mapped_column(
        JSONType, nullable=True, default=None,
        comment="Structured details (validation errors, field diffs, etc.)",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("run_id", "legacy_id", "entity_subtype", name="uq_migration_log_entry"),
    )

    def __repr__(self) -> str:
        return (
            f"<MigrationLog id={self.id} run={self.run_id} "
            f"level={self.level} legacy={self.legacy_id}>"
        )


class MigrationMapping(Base):
    """Maps legacy IDs to new SDMAS IDs for FK preservation.

    After a migration, this table allows downstream migrators to
    resolve legacy foreign keys to the correct new SDMAS IDs.
    """

    __tablename__ = "migration_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
    )
    legacy_id: Mapped[str] = mapped_column(
        String(255), nullable=False,
    )
    sdmas_id: Mapped[int] = mapped_column(
        Integer, nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "entity_type", "legacy_id",
            name="uq_migration_mapping_entity_legacy",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<MigrationMapping id={self.id} "
            f"{self.entity_type}[{self.legacy_id}] -> {self.sdmas_id}>"
        )
