"""Relationship intelligence — deterministic detection over the entity graph.

The layer is deliberately shaped like the risk domain: detectors emit
risk-shaped :class:`Finding` objects with explainable evidence, and the
:class:`DetectionPipeline` orchestrates them with evidence scoring and
false-positive reduction. Nothing here is accusatory — every output is a
review signal for a human queue.
"""

from app.intelligence.config import DetectorConfig, IntelligenceConfig
from app.intelligence.graph import EdgeRecord, EntityGraph, EntityRecord
from app.intelligence.pipeline import DetectionPipeline, PipelineReport
from app.intelligence.rules import (
    DEFAULT_DETECTORS,
    DETECTOR_REGISTRY,
    DetectorDefinition,
    get_detector,
)
from app.intelligence.scoring import Evidence, EvidenceScorer, Finding

__all__ = [
    "DEFAULT_DETECTORS",
    "DETECTOR_REGISTRY",
    "DetectionPipeline",
    "DetectorConfig",
    "DetectorDefinition",
    "EdgeRecord",
    "EntityGraph",
    "EntityRecord",
    "Evidence",
    "EvidenceScorer",
    "Finding",
    "IntelligenceConfig",
    "PipelineReport",
    "get_detector",
]
