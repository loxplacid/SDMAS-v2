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

    # D2: migration projects own their runs.  ``campus_id`` pins the run to
    # the tenant that created it so worker-executed runs stay tenant-scoped.
    project_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True,
        comment="Owning migration project (migration_projects.id)",
    )
    campus_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True,
        comment="Campus (tenant) the run belongs to",
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


# ── D2: Migration Project workspace ───────────────────────────────────
#
# A migration *project* is the operator-facing workspace that wraps the
# batch-migrator engine: upload → discover → map → transform → validate
# → preview → import → reconcile → report.  The project is the tenant
# boundary — every row is pinned to a ``campus_id`` and every mutation
# is audited.  The engine's ``MigrationRun`` rows remain the immutable
# execution record; a project references the run it produced.


#: Deterministic project lifecycle (D2.1).
MIGRATION_STATUS_DRAFT = "DRAFT"
MIGRATION_STATUS_DISCOVERING = "DISCOVERING"
MIGRATION_STATUS_MAPPING = "MAPPING"
MIGRATION_STATUS_VALIDATING = "VALIDATING"
MIGRATION_STATUS_READY = "READY"
MIGRATION_STATUS_IMPORTING = "IMPORTING"
MIGRATION_STATUS_RECONCILING = "RECONCILING"
MIGRATION_STATUS_COMPLETED = "COMPLETED"
MIGRATION_STATUS_FAILED = "FAILED"
MIGRATION_STATUS_CANCELLED = "CANCELLED"
MIGRATION_STATUS_ROLLED_BACK = "ROLLED_BACK"

MIGRATION_STATUSES = frozenset({
    MIGRATION_STATUS_DRAFT,
    MIGRATION_STATUS_DISCOVERING,
    MIGRATION_STATUS_MAPPING,
    MIGRATION_STATUS_VALIDATING,
    MIGRATION_STATUS_READY,
    MIGRATION_STATUS_IMPORTING,
    MIGRATION_STATUS_RECONCILING,
    MIGRATION_STATUS_COMPLETED,
    MIGRATION_STATUS_FAILED,
    MIGRATION_STATUS_CANCELLED,
    MIGRATION_STATUS_ROLLED_BACK,
})

#: Transitions the operator may trigger explicitly (state machine).
MIGRATION_TRANSITIONS: dict[str, set[str]] = {
    MIGRATION_STATUS_DRAFT: {MIGRATION_STATUS_DISCOVERING},
    MIGRATION_STATUS_DISCOVERING: {MIGRATION_STATUS_MAPPING, MIGRATION_STATUS_FAILED},
    MIGRATION_STATUS_MAPPING: {MIGRATION_STATUS_VALIDATING, MIGRATION_STATUS_DISCOVERING},
    MIGRATION_STATUS_VALIDATING: {MIGRATION_STATUS_READY, MIGRATION_STATUS_MAPPING},
    MIGRATION_STATUS_READY: {MIGRATION_STATUS_IMPORTING, MIGRATION_STATUS_VALIDATING},
    MIGRATION_STATUS_IMPORTING: {
        MIGRATION_STATUS_RECONCILING, MIGRATION_STATUS_FAILED, MIGRATION_STATUS_CANCELLED,
    },
    MIGRATION_STATUS_RECONCILING: {MIGRATION_STATUS_COMPLETED, MIGRATION_STATUS_FAILED},
    MIGRATION_STATUS_COMPLETED: {MIGRATION_STATUS_ROLLED_BACK},
    MIGRATION_STATUS_FAILED: set(),
    MIGRATION_STATUS_CANCELLED: set(),
    MIGRATION_STATUS_ROLLED_BACK: set(),
}


class MigrationProject(Base):
    """A tenant-scoped migration workspace (D2.1).

    Holds the operator's intent (source, mapping, transformations), the
    live progress counters, and the reconciliation report.  The actual
    row-level execution happens in :class:`MigrationRun` via the
    background import job.
    """

    __tablename__ = "migration_projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True,
        comment="Tenant boundary — projects never cross campuses",
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_system: Mapped[str] = mapped_column(
        String(100), nullable=False, default="Generic CSV",
        comment="e.g. Generic CSV, PowerSchool-style export, Legacy ERP export",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=MIGRATION_STATUS_DRAFT, index=True,
    )

    # Uploaded source file — stored under a generated key, never under a
    # user-controlled path (D2.15).
    file_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_mime: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Workspace state (JSON blobs, all operator-authored).
    discovery: Mapped[dict[str, Any] | None] = mapped_column(
        JSONType, nullable=True, default=None,
        comment="Column profiles + inferred mapping suggestions (D2.3)",
    )
    mapping: Mapped[dict[str, Any] | None] = mapped_column(
        JSONType, nullable=True, default=None,
        comment="{source_field: {target, confidence, reason, transforms}} (D2.4)",
    )
    validation: Mapped[dict[str, Any] | None] = mapped_column(
        JSONType, nullable=True, default=None,
        comment="Validation summary + blocking/warning/info counts (D2.6)",
    )
    reconciliation: Mapped[dict[str, Any] | None] = mapped_column(
        JSONType, nullable=True, default=None,
        comment="Post-import reconciliation report (D2.9)",
    )

    # Progress counters (survive browser refresh — always server-side).
    records_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_imported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Operator + execution linkage.
    operator_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True,
        comment="User who created the project",
    )
    run_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True,
        comment="MigrationRun produced by the import job",
    )
    job_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True,
        comment="Background job executing the import",
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    last_activity_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    started_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<MigrationProject id={self.id} name={self.name!r} "
            f"status={self.status} campus={self.campus_id}>"
        )
