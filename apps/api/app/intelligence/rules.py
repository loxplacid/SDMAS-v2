"""Detector metadata — mirrors the risk domain's rule registry.

Every detector declares a stable id, a category, human metadata, default
thresholds (mirroring ``risk_rule_configs``) and a recommended action. The
catalog lists all eleven detection types from the product brief; the working
core implements the five marked *core*; the rest are spec-only roadmap items.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DetectorDefinition:
    detector_id: str
    category: str  # duplicate | anomaly | cluster | integrity | social
    name: str
    description: str
    entity_type: str
    defaults: dict[str, Any]
    recommended_action: str
    implemented: bool = False


DEFAULT_DETECTORS: list[DetectorDefinition] = [
    DetectorDefinition(
        detector_id="duplicate_students",
        category="duplicate",
        name="Duplicate students",
        description="Student records referring to the same person (blocking + similarity).",
        entity_type="student",
        defaults={"similarity_threshold": 0.85},
        recommended_action="Review the pair and merge the records.",
        implemented=True,
    ),
    DetectorDefinition(
        detector_id="duplicate_parents",
        category="duplicate",
        name="Duplicate parents",
        description="Guardian records referring to the same person across families.",
        entity_type="parent",
        defaults={"similarity_threshold": 0.85},
        recommended_action="Review the pair and merge guardian records.",
    ),
    DetectorDefinition(
        detector_id="attendance_anomaly",
        category="anomaly",
        name="Attendance anomaly",
        description=(
            "Students deviating from their cohort's attendance pattern "
            "(robust z-score + seeded isolation forest consensus)."
        ),
        entity_type="student",
        defaults={"mad_z_threshold": 3.5, "contamination": 0.1, "iso_threshold": 0.8},
        recommended_action="Reach out to the family; verify records with the class teacher.",
        implemented=True,
    ),
    DetectorDefinition(
        detector_id="fee_anomaly",
        category="anomaly",
        name="Fee anomaly",
        description=(
            "Unusual payment amounts, timing or reversal patterns around a student or family."
        ),
        entity_type="student",
        defaults={"z_threshold": 3.0},
        recommended_action="Ask the finance office to verify the payment trail.",
    ),
    DetectorDefinition(
        detector_id="fraud",
        category="integrity",
        name="Fraud pattern",
        description=(
            "Multi-signal rule engine: fabricated documents, ghost students, payment diversion."
        ),
        entity_type="student",
        defaults={},
        recommended_action="Escalate to the fraud review queue; never auto-act.",
    ),
    DetectorDefinition(
        detector_id="cheating_cluster",
        category="cluster",
        name="Cheating cluster",
        description=(
            "Answer sheets with statistically implausible agreement (DBSCAN on hamming distance)."
        ),
        entity_type="student",
        defaults={"eps": 0.2, "min_samples": 3, "agreement_threshold": 0.85},
        recommended_action="Notify the examination office; re-invigilate future sittings.",
        implemented=True,
    ),
    DetectorDefinition(
        detector_id="bullying_cluster",
        category="cluster",
        name="Bullying cluster",
        description=(
            "Repeated directed-harassment signals (reports, absences, "
            "disciplinary events) forming a directed cluster."
        ),
        entity_type="student",
        defaults={"min_reports": 3, "min_directed_edges": 2},
        recommended_action="Hand to the safeguarding team; do not notify students directly.",
    ),
    DetectorDefinition(
        detector_id="teacher_favoritism",
        category="integrity",
        name="Teacher favoritism",
        description=(
            "A teacher's marks for one student persistently exceed the class "
            "average beyond the ability control."
        ),
        entity_type="student",
        defaults={"gap_threshold": 15.0, "min_exams": 3, "ability_floor": 60.0},
        recommended_action="Discuss with the academic head; sample-mark the teacher's grading.",
        implemented=True,
    ),
    DetectorDefinition(
        detector_id="social_cluster",
        category="social",
        name="Social cluster",
        description="Co-attendance / co-enrolment communities (greedy label propagation).",
        entity_type="student",
        defaults={"min_cluster_size": 5, "min_density": 0.5},
        recommended_action="Informational: peer-group analytics, tutoring, pastoral care.",
        implemented=True,
    ),
    DetectorDefinition(
        detector_id="hidden_relationships",
        category="social",
        name="Hidden relationships",
        description=(
            "Unstated links inferred from shared contact/bank/address "
            "signals across different surnames."
        ),
        entity_type="student",
        defaults={"shared_signal_threshold": 2},
        recommended_action="Verify with the family; update guardian records if confirmed.",
    ),
    DetectorDefinition(
        detector_id="recommendations",
        category="social",
        name="Graph-based recommendations",
        description=(
            "Co-enrolment affinity and centrality-ranked study-group / peer "
            "matches (opt-in, low-stakes)."
        ),
        entity_type="student",
        defaults={"min_affinity": 0.6, "top_k": 5},
        recommended_action="Surface as suggestions; students always opt in.",
    ),
]

DETECTOR_REGISTRY: dict[str, DetectorDefinition] = {d.detector_id: d for d in DEFAULT_DETECTORS}


def get_detector(detector_id: str) -> DetectorDefinition:
    if detector_id not in DETECTOR_REGISTRY:
        raise KeyError(f"Unknown detector: {detector_id}")
    return DETECTOR_REGISTRY[detector_id]
