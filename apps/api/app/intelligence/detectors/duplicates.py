"""Duplicate-student detection (entity resolution).

Pipeline: **block** on strong identity signals (normalised phone, normalised
email, last name token), then **score** every pair inside a shared block with
the weighted field similarity. A pair only becomes a finding if the weighted
similarity clears the configured threshold — the block keeps the pair count
O(n·block) instead of O(n²), and the threshold keeps precision high.
"""

from __future__ import annotations

from app.intelligence.config import IntelligenceConfig
from app.intelligence.detectors.base import Detector
from app.intelligence.graph import EntityGraph
from app.intelligence.scoring import Evidence, EvidenceScorer, Finding
from app.intelligence.similarity import (
    normalize_email,
    normalize_phone,
    normalize_text,
    record_similarity,
)


class DuplicateStudentsDetector(Detector):
    detector_id = "duplicate_students"
    name = "Duplicate students"
    category = "duplicate"

    def run(self, graph: EntityGraph, config: IntelligenceConfig) -> list[Finding]:
        cfg = config.for_detector(self.detector_id)
        threshold = float(cfg.thresholds.get("similarity_threshold", 0.85))
        students = graph.records_with_label("student")
        by_id = {s.entity_id: s for s in students}

        # --- Blocking -------------------------------------------------------
        blocks: dict[str, list[int]] = {}
        for student in students:
            props = student.props
            keys: list[str] = []
            phone = normalize_phone(props.get("phone", ""))
            email = normalize_email(props.get("email", ""))
            name_tokens = normalize_text(props.get("name", "")).split()
            if phone:
                keys.append(f"phone:{phone}")
            if email:
                keys.append(f"email:{email}")
            if name_tokens:
                keys.append(f"name:{name_tokens[-1]}")
            for key in keys:
                blocks.setdefault(key, []).append(student.entity_id)

        # --- Pair scoring ----------------------------------------------------
        scorer = EvidenceScorer(cfg.min_score)
        findings: list[Finding] = []
        seen: set[tuple[int, int]] = set()
        for block in blocks.values():
            ids = sorted(set(block))
            if len(ids) < 2:
                continue
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    a, b = ids[i], ids[j]
                    pair = (min(a, b), max(a, b))
                    if pair in seen:
                        continue
                    seen.add(pair)
                    pa, pb = by_id[a].props, by_id[b].props
                    similarity = record_similarity(pa, pb)
                    if similarity < threshold:
                        continue
                    evidence = [
                        Evidence(
                            "record_similarity",
                            similarity,
                            0.6,
                            f"weighted field similarity {similarity:.2f}",
                        ),
                        Evidence(
                            "phone_match",
                            1.0 if _same_phone(pa, pb) else 0.0,
                            0.2,
                            "same normalised phone" if _same_phone(pa, pb) else "phone differs",
                        ),
                        Evidence(
                            "email_match",
                            1.0 if _same_email(pa, pb) else 0.0,
                            0.2,
                            "same normalised email" if _same_email(pa, pb) else "email differs",
                        ),
                    ]
                    finding = scorer.finding(
                        rule_code=self.detector_id,
                        category=self.category,
                        entity_type="student",
                        entity_id=a,
                        evidence=evidence,
                        reason=(
                            f"Student {a} and student {b} look like the same person "
                            f"(similarity {similarity:.2f})"
                        ),
                        recommended_action="Review the pair and merge the records.",
                        # Student a may be flagged against several partners;
                        # each pair is a distinct review event.
                        group_id=f"pair:{a}:{b}",
                    )
                    if finding is not None:
                        findings.append(finding)
        return sorted(findings, key=lambda f: (-f.score, f.entity_id))


def _same_phone(a: dict, b: dict) -> bool:
    pa, pb = normalize_phone(a.get("phone", "")), normalize_phone(b.get("phone", ""))
    return bool(pa) and pa == pb


def _same_email(a: dict, b: dict) -> bool:
    ea, eb = normalize_email(a.get("email", "")), normalize_email(b.get("email", ""))
    return bool(ea) and ea == eb
