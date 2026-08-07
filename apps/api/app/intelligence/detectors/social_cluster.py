"""Social-cluster detection (community detection on the co-attendance graph).

Co-attendance edges (two students present in the same section on the same
day) accumulate weight; the deterministic greedy label-propagation algorithm
finds communities. A community becomes an informational ``social_cluster``
finding when it is large and dense enough, with PageRank identifying the
most central members (e.g. for peer-group analytics and pastoral care).

This detector also powers the graph-based-recommendation surface in the
roadmap: co-attendance affinity is the same signal, only the output differs.
"""

from __future__ import annotations

import networkx as nx

from app.intelligence.clustering import (
    label_propagation_communities,
    pagerank_rankings,
    student_community_graph,
)
from app.intelligence.config import IntelligenceConfig
from app.intelligence.detectors.base import Detector
from app.intelligence.graph import EntityGraph
from app.intelligence.scoring import Evidence, EvidenceScorer, Finding


class SocialClusterDetector(Detector):
    detector_id = "social_cluster"
    name = "Social cluster"
    category = "social"

    def run(self, graph: EntityGraph, config: IntelligenceConfig) -> list[Finding]:
        cfg = config.for_detector(self.detector_id)
        t = cfg.thresholds
        min_cluster_size = int(t.get("min_cluster_size", 5))
        min_density = float(t.get("min_density", 0.5))

        co = student_community_graph(graph)
        scorer = EvidenceScorer(cfg.min_score)
        findings: list[Finding] = []
        for community in sorted(
            label_propagation_communities(co),
            key=lambda c: (-len(c), sorted(node[1] for node in c)[0] if c else 0),
        ):
            if len(community) < min_cluster_size:
                continue
            subgraph = co.subgraph(community)
            density = nx.density(subgraph)
            if density < min_density:
                continue
            rankings = pagerank_rankings(subgraph)
            member_ids = sorted(node[1] for node in community)
            central = sorted(
                (node[1] for node in community),
                key=lambda sid: -rankings.get(("student", sid), 0.0),
            )[:3]
            evidence = [
                Evidence(
                    "cluster_size",
                    min(len(member_ids) / 15.0, 1.0),
                    0.4,
                    f"community of {len(member_ids)} students",
                ),
                Evidence(
                    "density",
                    round(density, 4),
                    0.4,
                    f"co-attendance density {density:.2f}",
                ),
                Evidence(
                    "centrality",
                    round(rankings.get(("student", central[0]), 0.0) * 10, 4),
                    0.2,
                    f"top PageRank members {central}",
                ),
            ]
            finding = scorer.finding(
                rule_code=self.detector_id,
                category=self.category,
                entity_type="student",
                entity_id=member_ids[0],
                evidence=evidence,
                reason=(
                    f"Co-attendance community of {len(member_ids)} students "
                    f"(density {density:.2f}); most central: {central}"
                ),
                recommended_action=(
                    "Informational: peer-group analytics, tutoring, pastoral care."
                ),
            )
            if finding is not None:
                findings.append(finding)
        return sorted(findings, key=lambda f: (-f.score, f.entity_id))
