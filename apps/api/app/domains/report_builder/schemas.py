from __future__ import annotations

import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ReportFilterSchema(BaseModel):
    key: str
    label: str
    type: str
    required: bool = False
    options: Optional[list[dict[str, str]]] = None
    placeholder: Optional[str] = None


class ReportColumnSchema(BaseModel):
    key: str
    header: str
    type: str = "string"
    format: Optional[str] = None


class ReportDefinitionResponse(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str]
    category: str
    allowed_roles: list[str]
    config: Optional[dict]
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime


class SavedReportCreate(BaseModel):
    report_definition_id: int
    name: str
    params: dict[str, Any] = Field(default_factory=dict)
    schedule: Optional[dict] = None


class SavedReportUpdate(BaseModel):
    name: Optional[str] = None
    params: Optional[dict[str, Any]] = None
    schedule: Optional[dict] = None


class SavedReportResponse(BaseModel):
    id: int
    user_id: int
    report_definition_id: int
    name: str
    params: dict[str, Any]
    schedule: Optional[dict]
    created_at: datetime.datetime
    updated_at: datetime.datetime


class ExportJobCreate(BaseModel):
    report_definition_id: int
    params: dict[str, Any] = Field(default_factory=dict)
    format: str = "csv"


class ExportJobResponse(BaseModel):
    id: int
    user_id: int
    report_definition_id: int
    params: dict[str, Any]
    format: str
    status: str
    progress: int
    total_rows: Optional[int]
    error_message: Optional[str]
    created_at: datetime.datetime
    updated_at: datetime.datetime


class ExportJobPage(BaseModel):
    items: list[ExportJobResponse]
    total: int
    page: int
    size: int
    pages: int


class ReportExecuteRequest(BaseModel):
    report_definition_id: int
    params: dict[str, Any] = Field(default_factory=dict)


class ReportExecuteResponse(BaseModel):
    columns: list[ReportColumnSchema]
    rows: list[dict[str, Any]]
    summary: dict[str, Any]
    total_rows: int
