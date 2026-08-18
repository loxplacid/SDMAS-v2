"""Data lineage foundation — Pydantic schemas (API contract)."""

from __future__ import annotations

import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# DataSource
# ---------------------------------------------------------------------------


class DataSourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    source_type: str = Field(default="table", max_length=30)
    external_ref: Optional[str] = Field(default=None, max_length=512)
    description: Optional[str] = Field(default=None, max_length=1000)
    record_ref: Optional[str] = Field(default=None, max_length=255)


class DataSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    name: str
    source_type: str
    external_ref: Optional[str] = None
    description: Optional[str] = None
    record_ref: Optional[str] = None
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# DataAsset
# ---------------------------------------------------------------------------


class DataAssetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    asset_type: str = Field(default="dataset", max_length=30)
    description: Optional[str] = Field(default=None, max_length=1000)
    ref: Optional[str] = Field(default=None, max_length=255)
    schema_info: Optional[dict[str, Any]] = None


class DataAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    name: str
    asset_type: str
    description: Optional[str] = None
    ref: Optional[str] = None
    schema_info: Optional[dict[str, Any]] = None
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# Transformation
# ---------------------------------------------------------------------------


class TransformationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    transform_type: str = Field(default="mapping", max_length=30)
    description: Optional[str] = Field(default=None, max_length=1000)
    definition: Optional[dict[str, Any]] = None


class TransformationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    name: str
    transform_type: str
    description: Optional[str] = None
    definition: Optional[dict[str, Any]] = None
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# LineageEdge
# ---------------------------------------------------------------------------


class LineageEdgeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upstream_type: str = Field(max_length=30)
    upstream_id: int
    downstream_type: str = Field(max_length=30)
    downstream_id: int
    edge_type: str = Field(default="derives_from", max_length=30)
    transformation_id: Optional[int] = None


class LineageEdgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    upstream_type: str
    upstream_id: int
    downstream_type: str
    downstream_id: int
    edge_type: str
    transformation_id: Optional[int] = None
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# CalculationVersion
# ---------------------------------------------------------------------------


class CalculationVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calc_name: str = Field(min_length=1, max_length=255)
    formula: str = Field(min_length=1, max_length=2000)
    definition: Optional[dict[str, Any]] = None
    asset_id: Optional[int] = None


class CalculationVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    calc_name: str
    version: int
    formula: str
    definition: Optional[dict[str, Any]] = None
    asset_id: Optional[int] = None
    superseded_by: Optional[int] = None
    is_current: bool
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# EvidenceReference
# ---------------------------------------------------------------------------


class EvidenceReferenceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_type: str = Field(max_length=30)
    node_id: int
    kind: str = Field(default="audit", max_length=30)
    reference: str = Field(min_length=1, max_length=512)
    checksum: Optional[str] = Field(default=None, max_length=128)
    note: Optional[str] = Field(default=None, max_length=1000)


class EvidenceReferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    node_type: str
    node_id: int
    kind: str
    reference: str
    checksum: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# Provenance (the headline query: "where did this value come from?")
# ---------------------------------------------------------------------------


class ProvenanceNode(BaseModel):
    """A node on the provenance path with its lineage metadata."""

    node_type: str
    node_id: int
    name: str
    kind: str  # source | asset | transformation (denormalized for the UI)
    details: dict[str, Any] = {}


class ProvenanceEdge(BaseModel):
    """The edge traversed between two provenance nodes."""

    upstream_type: str
    upstream_id: int
    downstream_type: str
    downstream_id: int
    edge_type: str
    transformation_id: Optional[int] = None


class ProvenanceReport(BaseModel):
    """Full provenance for a target node: nodes + edges + evidence."""

    target_type: str
    target_id: int
    target_name: str
    nodes: list[ProvenanceNode]
    edges: list[ProvenanceEdge]
    evidence: list[EvidenceReferenceRead]


__all__ = [
    "DataSourceCreate",
    "DataSourceRead",
    "DataAssetCreate",
    "DataAssetRead",
    "TransformationCreate",
    "TransformationRead",
    "LineageEdgeCreate",
    "LineageEdgeRead",
    "CalculationVersionCreate",
    "CalculationVersionRead",
    "EvidenceReferenceCreate",
    "EvidenceReferenceRead",
    "ProvenanceNode",
    "ProvenanceEdge",
    "ProvenanceReport",
]
