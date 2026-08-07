"""Detection pipeline — orchestration, false-positive reduction, reporting.

The pipeline is the deterministic front door of the layer:

1. **Discovery** — instantiate every *enabled* detector from the registry
   (config toggles map 1:1 to ``DETECTOR_REGISTRY`` ids).
2. **Detection** — run detectors over the campus-scoped graph in stable id
   order; detectors return findings with explainable evidence.
3. **False-positive reduction** — the working core applies three layers:
   - *per-detector*: evidence must clear ``min_score`` (each detector);
   - *deduplication*: one finding per (rule, entity) — the strongest wins;
   - *noise floor*: a global minimum score that trims weak tails.
4. **Report** — counts by category/severity plus the sorted finding list,
   all deterministic for the same graph + config.

Nothing here ever mutates state or auto-acts: findings are review signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.intelligence.config import IntelligenceConfig
from app.intelligence.detectors import DETECTORS
from app.intelligence.detectors.base import Detector
from app.intelligence.graph import EntityGraph
from app.intelligence.scoring import Finding


@dataclass(frozen=True)
class PipelineReport:
    """Result of one pipeline run over one campus-scoped graph."""

    campus_id: int
    findings: tuple[Finding, ...] = ()
    counts_by_category: dict[str, int] = field(default_factory=dict)
    counts_by_severity: dict[str, int] = field(default_factory=dict)
    enabled_detectors: tuple[str, ...] = ()

    @property
    def total(self) -> int:
        return len(self.findings)


class DetectionPipeline:
    """Run all enabled detectors with evidence scoring + FPR reduction."""

    def __init__(
        self,
        config: IntelligenceConfig | None = None,
        noise_floor: float = 20.0,
    ) -> None:
        """
        Args:
            config: detector configuration (defaults if None).
            noise_floor: global score floor below which findings are trimmed.
                Sits *below* the per-detector ``min_score`` defaults so it
                only bites when a campus configures an aggressive detector
                (min_score under the floor) — the safety net.
        """
        self.config = config or IntelligenceConfig()
        self.noise_floor = noise_floor

    def run(self, graph: EntityGraph) -> PipelineReport:
        """Run the pipeline; deterministic for a fixed graph + config."""
        # Discovery + stable ordering (id sort keeps results reproducible).
        enabled = sorted(
            (
                detector_id
                for detector_id, cls in DETECTORS.items()
                if self.config.for_detector(detector_id).enabled
            )
        )
        instances: list[Detector] = [DETECTORS[detector_id]() for detector_id in enabled]

        # Detection + per-detector min-score gating (inside each detector).
        raw: list[Finding] = []
        for detector in instances:
            raw.extend(detector.run(graph, self.config))

        # FPR: dedupe one finding per (rule, entity, group); keep the
        # strongest. ``group_id`` keeps distinct events distinct (a cheating
        # cluster in exam 101 vs 102, a duplicate pair with partner A vs B).
        best: dict[tuple[str, int, str], Finding] = {}
        for finding in raw:
            key = (finding.rule_code, finding.entity_id, finding.group_id)
            previous = best.get(key)
            if previous is None or finding.score > previous.score:
                best[key] = finding

        # FPR: global noise floor trims weak tails.
        findings = sorted(
            (f for f in best.values() if f.score >= self.noise_floor),
            key=lambda f: (-f.score, f.rule_code, f.entity_id),
        )

        counts_by_category: dict[str, int] = {}
        counts_by_severity: dict[str, int] = {}
        for finding in findings:
            counts_by_category[finding.category] = counts_by_category.get(finding.category, 0) + 1
            counts_by_severity[finding.severity] = counts_by_severity.get(finding.severity, 0) + 1

        return PipelineReport(
            campus_id=graph.campus_id,
            findings=tuple(findings),
            counts_by_category=counts_by_category,
            counts_by_severity=counts_by_severity,
            enabled_detectors=tuple(enabled),
        )
