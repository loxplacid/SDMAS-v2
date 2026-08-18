"""Data lineage foundation (platform).

Answers the question *"where did this value come from?"* with a clean,
lightweight graph over named nodes:

- ``lineage_data_sources``          — source systems / tables / files
  (legacy ERP, CSV uploads, `sdmas.students`, …)
- ``lineage_data_assets``           — datasets, metrics, dashboards, reports
- ``lineage_transformations``       — the step between source and asset
  (SQL, mapping, aggregation, import)
- ``lineage_edges``                 — directed edges between any two nodes
- ``lineage_calculation_versions``  — versioned calculation/metric definitions
- ``lineage_evidence_refs``         — pointers to evidence (audit entries,
  migration runs, files, reports)

Edges are polymorphic: an edge connects ``(node_type, node_id)`` endpoints
where ``node_type`` is ``data_source`` / ``data_asset`` / ``transformation``,
so the graph can later span reports, migration runs, and reconciliation
without schema churn.  Every table is tenant-scoped (``campus_id``) and all
access goes through the tenant-scoped repository.

The integration hook :meth:`LineageService.register_migration_import`
records lineage when the migration engine completes an import, so every
migrated value can be traced back to its source file and run.
"""

from app.platform.lineage.models import (
    ASSET_TYPES,
    EDGE_EDGE_TYPES,
    EVIDENCE_TYPES,
    NODE_TYPES,
    SOURCE_TYPES,
    TRANSFORM_TYPES,
    CalculationVersion,
    DataAsset,
    DataSource,
    EvidenceReference,
    LineageEdge,
    Transformation,
)
from app.platform.lineage.repository import LineageRepository
from app.platform.lineage.service import LineageService

__all__ = [
    "ASSET_TYPES",
    "EDGE_EDGE_TYPES",
    "EVIDENCE_TYPES",
    "NODE_TYPES",
    "SOURCE_TYPES",
    "TRANSFORM_TYPES",
    "CalculationVersion",
    "DataAsset",
    "DataSource",
    "EvidenceReference",
    "LineageEdge",
    "Transformation",
    "LineageRepository",
    "LineageService",
]
