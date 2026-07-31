from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.pagination import Page


class GlobalSearchQuery(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)
    types: Optional[list[str]] = Field(
        default=None,
        description="Filter to specific entity types. "
        "Options: student, teacher, class, section, payment, fee, notification, document. "
        "Null means search all.",
    )
    page: int = Field(default=1, ge=1, le=100)
    size: int = Field(default=20, ge=1, le=100)

    model_config = ConfigDict(extra="forbid")


class SearchResultItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="Composite ID: {entity_type}-{entity_id}")
    entity_type: str
    entity_id: int
    label: str
    description: Optional[str] = None
    route: str = Field(description="Frontend route path")
    match_field: Optional[str] = Field(
        default=None, description="Which field produced the match"
    )
    score: Optional[float] = Field(
        default=None, description="Relevance score (0-1), higher is better"
    )


class GroupedSearchResult(BaseModel):
    entity_type: str
    label: str
    icon: str
    items: list[SearchResultItem]


class GlobalSearchResponse(BaseModel):
    query: str
    total: int
    page: int
    size: int
    results: list[SearchResultItem]
    grouped: list[GroupedSearchResult]
    took_ms: float


class SearchHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    query: str
    entity_type: Optional[str] = None
    result_count: int
    created_at: datetime.datetime


class SearchHistoryClear(BaseModel):
    id: Optional[int] = Field(
        default=None, description="Clear a specific search, or null to clear all"
    )


class FrequentSearchResponse(BaseModel):
    query: str
    count: int


SearchHistoryPage = Page[SearchHistoryResponse]
