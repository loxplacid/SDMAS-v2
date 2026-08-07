"""Evidence scoring and findings.

Every detection is decomposed into **evidence** — named, weighted, 0-1
normalised signals with human-readable detail. The :class:`EvidenceScorer`
combines them into a single 0-100 score whose severity banding reuses the
risk domain's ``severity_from_score``, so intelligence findings drop
straight into the existing ``risk_findings`` lifecycle (open →
acknowledged → resolved) in the integration phase.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domains.risk.rules import severity_from_score


@dataclass(frozen=True)
class Evidence:
    """One named, weighted signal behind a finding."""

    metric_id: str
    value: float  # normalised 0-1 signal strength
    weight: float = 1.0
    detail: str = ""


@dataclass(frozen=True)
class Finding:
    """A detected relationship-intelligence finding, risk-shaped."""

    rule_code: str
    category: str  # duplicate | anomaly | cluster | integrity | social
    entity_type: str  # student | parent | teacher ...
    entity_id: int
    score: float
    severity: str  # critical | high | medium | low
    reason: str
    recommended_action: str
    evidence: tuple[Evidence, ...] = ()
    status: str = "open"
    # Disambiguates multiple findings of one rule on one entity that are
    # genuinely distinct events (a cheating cluster in exam 101 vs 102, a
    # duplicate pair with partner A vs partner B). Empty = singleton rule.
    group_id: str = ""


class EvidenceScorer:
    """Weighted evidence → 0-100 score; emits nothing below ``min_score``."""

    def __init__(self, min_score: float = 40.0) -> None:
        self.min_score = min_score

    def score(self, evidence: list[Evidence]) -> float:
        total_weight = sum(e.weight for e in evidence)
        if total_weight <= 0:
            return 0.0
        weighted = sum(e.weight * e.value for e in evidence)
        return round(min(100.0 * weighted / total_weight, 100.0), 1)

    def finding(
        self,
        rule_code: str,
        category: str,
        entity_type: str,
        entity_id: int,
        evidence: list[Evidence],
        reason: str,
        recommended_action: str,
        group_id: str = "",
    ) -> Finding | None:
        """Return a Finding if the evidence clears the minimum score, else None.

        ``None`` is the first false-positive reduction: weak evidence never
        becomes a finding. ``group_id`` separates genuinely distinct events
        of the same rule on the same entity (exam id, duplicate partner id).
        """
        score = self.score(evidence)
        if score < self.min_score:
            return None
        return Finding(
            rule_code=rule_code,
            category=category,
            entity_type=entity_type,
            entity_id=entity_id,
            score=score,
            severity=severity_from_score(score),
            reason=reason,
            recommended_action=recommended_action,
            evidence=tuple(evidence),
            group_id=group_id,
        )
