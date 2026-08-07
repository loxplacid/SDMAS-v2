"""Attendance anomaly detection.

Two independent signals per student, combined by **consensus**:

- *statistical* — robust modified z-score (median + MAD) against the cohort
  on attendance-rate features; resilient to the outliers it is hunting;
- *model* — seeded Isolation Forest anomaly strength over the same features.

A student is flagged only when both signals agree (``stat & iso``) — the
working core's primary false-positive reduction. Evidence carries the
normalised strength of each signal plus the raw rate.
"""

from __future__ import annotations

from statistics import median

from app.intelligence.config import IntelligenceConfig
from app.intelligence.detectors.base import Detector
from app.intelligence.graph import EntityGraph
from app.intelligence.isolation import isolation_anomaly_scores
from app.intelligence.scoring import Evidence, EvidenceScorer, Finding
from app.intelligence.stats import mad, modified_z_score


class AttendanceAnomalyDetector(Detector):
    detector_id = "attendance_anomaly"
    name = "Attendance anomaly"
    category = "anomaly"

    def run(self, graph: EntityGraph, config: IntelligenceConfig) -> list[Finding]:
        cfg = config.for_detector(self.detector_id)
        t = cfg.thresholds
        z_threshold = float(t.get("mad_z_threshold", 3.5))
        iso_threshold = float(t.get("iso_threshold", 0.8))
        contamination = float(t.get("contamination", 0.1))
        random_state = cfg.random_state

        students = graph.records_with_label("student")
        if len(students) < 5:
            return []
        rows = [(s.entity_id, s.props) for s in students]
        # Features: overall rate, recent rate, capped absence-streak score.
        features = [
            [
                _rate(props, "attendance_rate"),
                _rate(props, "recent_rate", _rate(props, "attendance_rate")),
                min(int(props.get("max_consecutive_absences", 0)), 20) / 20.0,
            ]
            for _, props in rows
        ]

        # --- Statistical signal: robust z-score per feature column ----------
        # Track the *max* |z| across columns per row so evidence reports the
        # column that actually triggered the flag, not just the rate column.
        statistical: set[int] = set()
        max_abs_z: list[float] = [0.0] * len(features)
        for col in range(len(features[0])):
            column = [row[col] for row in features]
            med, spread = median(column), mad(column)
            for idx, value in enumerate(column):
                z = abs(modified_z_score(value, med, spread))
                max_abs_z[idx] = max(max_abs_z[idx], z)
                if z > z_threshold:
                    statistical.add(idx)

        # --- Model signal: seeded isolation forest --------------------------
        iso_scores = isolation_anomaly_scores(
            features, random_state=random_state, contamination=contamination
        )
        model_flagged = {i for i, s in enumerate(iso_scores) if s > iso_threshold}

        # --- Consensus --------------------------------------------------------
        scorer = EvidenceScorer(cfg.min_score)
        findings: list[Finding] = []
        for idx in sorted(statistical & model_flagged):
            entity_id, props = rows[idx]
            rate = _rate(props, "attendance_rate")
            recent = _rate(props, "recent_rate", rate)
            z = max_abs_z[idx]
            evidence = [
                Evidence(
                    "attendance_rate",
                    round(1 - rate, 4),
                    0.4,
                    f"attendance rate {rate:.0%}",
                ),
                Evidence(
                    "recent_trend",
                    round(max(1 - recent, 0.0), 4),
                    0.3,
                    f"recent window rate {recent:.0%}",
                ),
                Evidence(
                    "isolation_anomaly",
                    iso_scores[idx],
                    0.2,
                    f"seeded isolation forest strength {iso_scores[idx]:.2f}",
                ),
                Evidence(
                    "statistical_anomaly",
                    round(min(z / z_threshold, 1.0), 4),
                    0.1,
                    f"robust z-score {z:.1f}",
                ),
            ]
            finding = scorer.finding(
                rule_code=self.detector_id,
                category=self.category,
                entity_type="student",
                entity_id=entity_id,
                evidence=evidence,
                reason=(
                    f"Student {entity_id} deviates from the cohort attendance "
                    f"pattern (rate {rate:.0%}, recent {recent:.0%})"
                ),
                recommended_action=(
                    "Reach out to the family; verify records with the class teacher."
                ),
            )
            if finding is not None:
                findings.append(finding)
        return sorted(findings, key=lambda f: (-f.score, f.entity_id))


def _rate(props: dict, key: str, fallback: float = 0.0) -> float:
    return float(props.get(key, fallback))
