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
