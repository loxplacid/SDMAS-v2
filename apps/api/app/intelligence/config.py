"""Detector configuration — thresholds and weights, all data not code.

Mirrors the ``risk_rule_configs`` model: every detector reads its numeric
assumptions from a :class:`IntelligenceConfig` (seeded with defaults,
overridable per detector), never from code constants. Determinism is a
configuration property: the isolation-forest seed lives here, so a campus
can pin it.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any


@dataclass(frozen=True)
class DetectorConfig:
    """Per-detector knobs."""

    enabled: bool = True
    min_score: float = 40.0
    # The isolation-forest seed is pinned here so anomaly scores are
    # reproducible across runs and campuses can opt into a different seed.
    random_state: int = 0
    thresholds: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IntelligenceConfig:
    """All detector configurations; overrides validate detector ids."""

    detectors: dict[str, DetectorConfig] = field(
        default_factory=lambda: {
            "duplicate_students": DetectorConfig(
                min_score=45.0,
                thresholds={"similarity_threshold": 0.85},
            ),
            "attendance_anomaly": DetectorConfig(
                min_score=50.0,
                thresholds={"mad_z_threshold": 3.5, "contamination": 0.1, "iso_threshold": 0.8},
            ),
            "cheating_cluster": DetectorConfig(
                min_score=55.0,
                thresholds={"eps": 0.2, "min_samples": 3, "agreement_threshold": 0.85},
            ),
            "teacher_favoritism": DetectorConfig(
                min_score=50.0,
                thresholds={"gap_threshold": 15.0, "min_exams": 3, "ability_floor": 60.0},
            ),
            "social_cluster": DetectorConfig(
                min_score=30.0,
                thresholds={"min_cluster_size": 5, "min_density": 0.5},
            ),
        }
    )

    def for_detector(self, detector_id: str) -> DetectorConfig:
        config = self.detectors.get(detector_id)
        if config is None:
            raise ValueError(f"Unknown detector: {detector_id}")
        return config

    def merged(self, overrides: dict[str, dict[str, Any]]) -> "IntelligenceConfig":
        """Return a copy with per-detector field/threshold overrides applied.

        Raises:
            ValueError: if an override names an unknown detector or key.
        """
        detectors = dict(self.detectors)
        for detector_id, patch in overrides.items():
            if detector_id not in detectors:
                raise ValueError(f"Unknown detector: {detector_id}")
            current = detectors[detector_id]
            known = {f.name for f in DetectorConfig.__dataclass_fields__.values()}
            unknown = set(patch) - known - {"thresholds"}
            if unknown:
                raise ValueError(f"Unknown {detector_id} config key(s): {sorted(unknown)}")
            thresholds = dict(current.thresholds)
            if "thresholds" in patch:
                thresholds.update(patch["thresholds"])
            field_patch = {k: v for k, v in patch.items() if k != "thresholds" and k in known}
            detectors[detector_id] = replace(current, **field_patch, thresholds=thresholds)
        return IntelligenceConfig(detectors=detectors)
