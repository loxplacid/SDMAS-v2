from __future__ import annotations

import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class DocumentCategoryResponse(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str]
    allowed_roles: list[str]
    owner_type: str
    max_file_size_mb: Optional[int]
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime


class DocumentCreate(BaseModel):
    category_id: int
    student_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    lifecycle_state: Optional[str] = None


class DocumentVersionResponse(BaseModel):
    id: int
    document_id: int
    version_number: int
    original_filename: str
    mime_type: str
    file_size: int
    change_notes: Optional[str]
    uploaded_by: int
    created_at: datetime.datetime


class DocumentShareCreate(BaseModel):
    expires_in_hours: int = Field(default=24, ge=1, le=720)
    max_downloads: Optional[int] = Field(default=None, ge=1)


class DocumentShareResponse(BaseModel):
    id: int
    document_id: int
    token: str
    signed_url: str
    expires_at: datetime.datetime
    max_downloads: Optional[int]
    download_count: int
    is_revoked: bool
    created_at: datetime.datetime


class DocumentResponse(BaseModel):
    id: int
    category_id: int
    owner_id: Optional[int]
    owner_type: str
    student_id: Optional[int]
    original_filename: str
    mime_type: str
    file_size: int
    title: Optional[str]
    description: Optional[str]
    tags: Optional[list[str]]
    lifecycle_state: str
    campus_id: Optional[int]
    uploaded_by: int
    uploaded_at: datetime.datetime
    updated_at: datetime.datetime
    archived_at: Optional[datetime.datetime]
    deleted_at: Optional[datetime.datetime]
    current_version: Optional[DocumentVersionResponse] = None
    share_count: int = 0


class DocumentPage(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int
    size: int
    pages: int


class DocumentUploadResponse(BaseModel):
    id: int
    filename: str
    mime_type: str
    file_size: int
    title: Optional[str]
    storage_key: str
    uploaded_at: datetime.datetime
    download_url: str
