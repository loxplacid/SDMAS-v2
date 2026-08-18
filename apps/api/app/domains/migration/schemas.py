from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MigrationRunCreate(BaseModel):
    entity_type: str = Field(..., max_length=50)
    source: str = Field(..., description="Legacy data source path/URL")
    is_dry_run: bool = False


class MigrationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    status: str
    source: str
    total_records: int
    imported: int
    skipped: int
    errors: int
    warnings: int
    is_dry_run: bool
    summary: dict[str, Any] | None = None
    started_at: datetime.datetime | None = None
    completed_at: datetime.datetime | None = None
    created_at: datetime.datetime


class MigrationLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    level: str
    legacy_id: str | None = None
    entity_type: str
    entity_subtype: str | None = None
    message: str | None = None
    details: dict[str, Any] | None = None
    created_at: datetime.datetime


class MigrationMappingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    entity_type: str
    legacy_id: str
    sdmas_id: int


class MigrationSummary(BaseModel):
    entity_type: str
    total: int
    imported: int
    skipped: int
    errors: int
    warnings: int
    duration_seconds: float | None = None
    is_dry_run: bool
    status: str
    error_details: list[dict[str, Any]] = []


class BulkMigrationRequest(BaseModel):
    entities: list[str] = Field(
        ...,
        description="Ordered list of entity types to migrate",
    )
    source: str
    is_dry_run: bool = False


class BulkMigrationResponse(BaseModel):
    runs: list[MigrationRunResponse]
    summaries: list[MigrationSummary]
    overall_status: str


# ── D2 Migration Project workspace ────────────────────────────────────


class MigrationProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: int | None = None
    name: str
    source_system: str
    description: str | None = None
    status: str
    original_filename: str | None = None
    file_mime: str | None = None
    file_size: int = 0
    row_count: int = 0
    discovery: dict[str, Any] | None = None
    mapping: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    reconciliation: dict[str, Any] | None = None
    # TASK 15 — Migration Factory workspace state.
    profile: dict[str, Any] | None = None
    identity_match: dict[str, Any] | None = None
    mapping_versions: list[dict[str, Any]] | None = None
    verification: dict[str, Any] | None = None
    approval: dict[str, Any] | None = None
    cutover: dict[str, Any] | None = None
    records_processed: int = 0
    records_imported: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    records_rejected: int = 0
    warnings: int = 0
    operator_id: int | None = None
    run_id: int | None = None
    job_id: int | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    last_activity_at: datetime.datetime | None = None
    started_at: datetime.datetime | None = None
    completed_at: datetime.datetime | None = None


class MigrationProjectPage(BaseModel):
    items: list[MigrationProjectResponse]
    total: int
    page: int
    size: int
    pages: int


class MappingUpdate(BaseModel):
    mapping: dict[str, Any] = Field(
        ..., description="{source_field: {target, confidence, reason, transforms}}"
    )


class ValidationResult(BaseModel):
    blocking: int
    warnings: int
    info: int
    total: int
    samples: list[dict[str, Any]] = []
    is_ready: bool
    validated_at: str
    # Step 2 — per-category breakdown so the UI can explain what blocks
    # execution (errors) vs what merely needs attention (warnings).
    categories: dict[str, int] = {}  # e.g. {"missing_required": 3, "invalid_date": 1, ...}


class PreviewRow(BaseModel):
    row: int
    before: dict[str, Any]
    after: dict[str, Any]
    status: str
    # Step 2 — operational action classification shown to the operator.
    action: str = "CREATE"  # CREATE | UPDATE | SKIP | ERROR
    action_reason: str | None = None


class PreviewResult(BaseModel):
    total: int
    limit: int
    rows: list[PreviewRow]
    mapping: dict[str, Any] | None = None


class ImportProgress(BaseModel):
    project_id: int
    status: str
    records_processed: int
    records_imported: int
    records_updated: int
    records_skipped: int
    records_rejected: int
    warnings: int
    row_count: int
    job: dict[str, Any] | None = None


class ReconcileResult(BaseModel):
    source_records: int
    target_records: int
    created: int
    updated: int
    skipped: int
    rejected: int
    duplicates: int
    warnings: int
    run_id: int | None = None
    run_status: str | None = None
    entities: list[str] = []
    reconciled_at: str


# ── TASK 15 — Migration Factory capability schemas ──────────────────────


class ProfileResult(BaseModel):
    """Source profile: entity distribution, quality scorecard, PII columns,
    duplicate-key candidates."""

    row_count: int
    entities: dict[str, int]
    scorecard: dict[str, Any]
    pii_columns: list[str]
    duplicate_candidates: list[dict[str, Any]]
    profiled_at: str | None = None


class IdentityMatchRow(BaseModel):
    row: int
    decision: str  # match | no_match | ambiguous
    confidence: str
    method: str | None = None
    sdmas_id: int | None = None
    matched_name: str | None = None
    candidates: int = 0


class IdentityMatchResult(BaseModel):
    total: int
    matched: int
    no_match: int
    ambiguous: int
    matched_at: str | None = None
    rows: list[IdentityMatchRow]


class ClassifiedRow(BaseModel):
    row: int
    before: dict[str, Any]
    after: dict[str, Any]
    status: str
    action: str  # CREATE | UPDATE | SKIP | ERROR
    action_reason: str | None = None


class DryRunSummary(BaseModel):
    total: int
    create: int
    update: int
    skip: int
    error: int
    blocking: int
    warnings: int
    dry_run_at: str


class DryRunResult(BaseModel):
    snapshot_id: int
    summary: DryRunSummary
    rows: list[ClassifiedRow]


class MigrationSnapshotResponse(BaseModel):
    id: int
    project_id: int
    kind: str
    row_count: int
    summary: dict[str, Any] | None = None
    payload: dict[str, Any] | None = None
    created_by: int | None = None
    created_at: str


class ApprovalRequest(BaseModel):
    note: str | None = None


class ApprovalDecision(BaseModel):
    note: str | None = None
    approver_id: int | None = None


class ApprovalReject(BaseModel):
    reason: str | None = None


class CutoverRequest(BaseModel):
    note: str | None = None


class VerifyResult(BaseModel):
    source_row_count: int
    entities: list[dict[str, Any]]
    spot_checks: list[dict[str, Any]]
    passed: bool
    verified_at: str | None = None


class RollbackPlanItem(BaseModel):
    run_id: int
    entity_type: str
    records_to_remove: int
    tables_affected: list[str] = []
