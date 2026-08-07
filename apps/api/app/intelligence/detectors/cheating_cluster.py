"""Cheating-cluster detection (DBSCAN over answer sheets).

Answer sheets are encoded as per-student answer-index vectors (one position
per question). DBSCAN with the *hamming* metric groups sheets whose answers
agree on nearly every position — including (crucially) the wrong answers,
which is the statistical signature of copying. A cluster only becomes a
finding when it has at least ``min_samples`` members and mean pairwise
agreement clears ``agreement_threshold``.

No accusation is ever made from this alone: the finding is a review signal
for the examination office (see OPTIMIZATION_ENGINE-style guardrails in
docs/RELATIONSHIP_INTELLIGENCE.md §8–9).
"""

from __future__ import annotations

from app.intelligence.clustering import dbscan_clusters
from app.intelligence.config import IntelligenceConfig
from app.intelligence.detectors.base import Detector
from app.intelligence.graph import EntityGraph
from app.intelligence.scoring import Evidence, EvidenceScorer, Finding


class CheatingClusterDetector(Detector):
    detector_id = "cheating_cluster"
    name = "Cheating cluster"
    category = "cluster"

    def run(self, graph: EntityGraph, config: IntelligenceConfig) -> list[Finding]:
        cfg = config.for_detector(self.detector_id)
        t = cfg.thresholds
        eps = float(t.get("eps", 0.2))
        min_samples = int(t.get("min_samples", 3))
        agreement_threshold = float(t.get("agreement_threshold", 0.85))

        responses = graph.records_with_label("exam_response")
        # Group by exam, then cluster the answer vectors per exam.
        by_exam: dict[int, list] = {}
        for response in responses:
            by_exam.setdefault(int(response.props["exam_id"]), []).append(response)

        scorer = EvidenceScorer(cfg.min_score)
        findings: list[Finding] = []
        for exam_id in sorted(by_exam):
            group = sorted(by_exam[exam_id], key=lambda r: r.entity_id)
            students = [int(r.props["student_id"]) for r in group]
            if len(students) < min_samples:
                continue
            questions = sorted({q for r in group for q in r.props["answers"]})
            if len(questions) < 3:
                continue
            codebook: dict[tuple[str, object], int] = {}
            vectors = []
            for r in group:
                answers = r.props["answers"]
                vector = [
                    codebook.setdefault((q, answers.get(q)), len(codebook)) for q in questions
                ]
                vectors.append(vector)

            for members in dbscan_clusters(
                vectors, eps=eps, min_samples=min_samples, metric="hamming"
            ).values():
                member_students = sorted(students[i] for i in members)
                if len(member_students) < min_samples:
                    continue
                agreement = _mean_pairwise_agreement(vectors, members)
                if agreement < agreement_threshold:
                    continue
                evidence = [
                    Evidence(
                        "answer_agreement",
                        round(agreement, 4),
                        0.7,
                        f"mean pairwise answer agreement {agreement:.0%}",
                    ),
                    Evidence(
                        "cluster_size",
                        min(len(member_students) / 10.0, 1.0),
                        0.2,
                        f"cluster of {len(member_students)} students",
                    ),
                    Evidence(
                        "wrong_answer_match",
                        round(agreement, 4),
                        0.1,
                        "identical wrong answers are the copying signature",
                    ),
                ]
                finding = scorer.finding(
                    rule_code=self.detector_id,
                    category=self.category,
                    entity_type="student",
                    entity_id=member_students[0],
                    evidence=evidence,
                    reason=(
                        f"Exam {exam_id}: students {member_students} share "
                        f"{agreement:.0%} identical answers"
                    ),
                    recommended_action=(
                        "Notify the examination office; re-invigilate future sittings."
                    ),
                    # Same leading student can appear in distinct events
                    # (a cluster in exam 101 vs 102) — keep them separate.
                    group_id=f"exam:{exam_id}",
                )
                if finding is not None:
                    findings.append(finding)
        return sorted(findings, key=lambda f: (-f.score, f.entity_id))


def _mean_pairwise_agreement(vectors: list[list[int]], members: list[int]) -> float:
    """Fraction of identical answer positions averaged over member pairs."""
    total, count = 0.0, 0
    for i in range(len(members)):
        for j in range(i + 1, len(members)):
            va, vb = vectors[members[i]], vectors[members[j]]
            total += sum(1 for x, y in zip(va, vb) if x == y) / len(va)
            count += 1
    return total / count if count else 0.0
