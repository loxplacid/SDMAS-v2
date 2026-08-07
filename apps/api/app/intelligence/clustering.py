"""Clustering and graph-algorithm wrappers.

All wrappers are deterministic: DBSCAN has no randomness; networkx's greedy
label-propagation and PageRank are deterministic given the node/edge order,
which the pipeline keeps stable by construction (sorted inputs).
"""

from __future__ import annotations

import networkx as nx
from sklearn.cluster import DBSCAN

from app.intelligence.graph import EntityGraph


def dbscan_clusters(
    features: list[list[float]],
    eps: float = 0.5,
    min_samples: int = 3,
    metric: str = "euclidean",
) -> dict[int, list[int]]:
    """Cluster feature rows; return {cluster_label: [row indices]}.

    Noise points (label -1) are dropped. ``metric="hamming"`` is the natural
    choice for answer-sheet vectors: distance is the fraction of differing
    positions.
    """
    if len(features) < min_samples:
        return {}
    labels = DBSCAN(eps=eps, min_samples=min_samples, metric=metric).fit_predict(features)
    clusters: dict[int, list[int]] = {}
    for row_idx, label in enumerate(labels):
        if label >= 0:
            clusters.setdefault(int(label), []).append(row_idx)
    return clusters


def label_propagation_communities(graph: nx.Graph) -> list[set[object]]:
    """Deterministic greedy label propagation (networkx).

    NOTE: use ``label_propagation_communities`` (deterministic), not
    ``asyn_lpa_communities`` (random tie-breaking).
    """
    from networkx.algorithms.community import label_propagation_communities as lpa

    return [set(community) for community in lpa(graph)]


def pagerank_rankings(graph: nx.Graph) -> dict[object, float]:
    """PageRank over a weighted graph (deterministic)."""
    return nx.pagerank(graph, weight="weight")


def student_community_graph(graph: EntityGraph, edge_type: str = "co_attendance") -> nx.Graph:
    """Student-only undirected graph from one typed edge family."""
    g: nx.Graph = nx.Graph()
    for edge in graph.edge_records(edge_type):
        src = (edge.src_label, edge.src_id)
        dst = (edge.dst_label, edge.dst_id)
        if src[0] != "student" or dst[0] != "student" or src == dst:
            continue
        if g.has_edge(src, dst):
            g[src][dst]["weight"] += edge.weight
        else:
            g.add_edge(src, dst, weight=edge.weight)
    return g
