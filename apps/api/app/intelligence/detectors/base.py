"""Detector protocol.

A detector is the only domain-specific unit in the layer. It reads a
campus-scoped :class:`EntityGraph` and an :class:`IntelligenceConfig`, and
returns risk-shaped :class:`Finding` objects whose evidence is fully
explainable. Detectors are pure: same graph + same config → same findings.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.intelligence.config import IntelligenceConfig
from app.intelligence.graph import EntityGraph
from app.intelligence.scoring import Finding


class Detector(ABC):
    """One detection type (duplicates, anomaly, cluster, rule engine…)."""

    detector_id: str = "detector"
    name: str = "Detector"
    category: str = "general"

    @abstractmethod
    def run(self, graph: EntityGraph, config: IntelligenceConfig) -> list[Finding]:
        """Detect on one campus-scoped graph; return sorted findings."""
