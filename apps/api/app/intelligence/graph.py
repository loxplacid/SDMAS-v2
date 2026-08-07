"""In-memory entity graph for relationship intelligence.

A campus-scoped projection of school entities and the relationships between
them, backed by ``networkx`` (the graph layer's sanctioned engine, see
``docs/GRAPH_LAYER.md``). Detectors read only this graph; the pipeline caller
builds it from persisted records (later phases ingest from the graph layer's
outbox projection and the adjacency tables).

Structural tenancy mirrors ``multi_tenant``: a graph is bound to one
``campus_id`` and the working core never crosses it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx


@dataclass(frozen=True)
class EntityRecord:
    """One entity node: (label, entity_id) + free-form props."""

    label: str  # "student" | "teacher" | "parent" | "grade" | "exam_response" ...
    entity_id: int
    props: dict = field(default_factory=dict)


@dataclass(frozen=True)
class EdgeRecord:
    """One typed, weighted relationship between two entities."""

    edge_type: str  # "co_attendance" | "parent_of" | "teaches" ...
    src_label: str
    src_id: int
    dst_label: str
    dst_id: int
    weight: float = 1.0
    props: dict = field(default_factory=dict)


class EntityGraph:
    """Campus-scoped graph; nodes keyed by (label, id), typed edges."""

    def __init__(
        self,
        campus_id: int,
        nodes: tuple[EntityRecord, ...] = (),
        edges: tuple[EdgeRecord, ...] = (),
    ) -> None:
        self.campus_id = campus_id
        self._g: nx.MultiDiGraph = nx.MultiDiGraph()
        for node in nodes:
            self.add_node(node)
        for edge in edges:
            self.add_edge(edge)

    def add_node(self, record: EntityRecord) -> None:
        self._g.add_node((record.label, record.entity_id), **record.props)

    def add_edge(self, edge: EdgeRecord) -> None:
        self._g.add_edge(
            (edge.src_label, edge.src_id),
            (edge.dst_label, edge.dst_id),
            type=edge.edge_type,
            weight=edge.weight,
            **edge.props,
        )

    @property
    def graph(self) -> nx.MultiDiGraph:
        """The underlying networkx graph (read-only by convention)."""
        return self._g

    def nodes_with_label(self, label: str) -> list[tuple[str, int]]:
        return [node for node in self._g.nodes if node[0] == label]

    def records_with_label(self, label: str) -> list[EntityRecord]:
        return [
            EntityRecord(label, node_id, dict(self._g.nodes[(label, node_id)]))
            for label, node_id in self.nodes_with_label(label)
        ]

    def edge_records(self, edge_type: str) -> list[EdgeRecord]:
        out: list[EdgeRecord] = []
        for src, dst, data in self._g.edges(data=True):
            if data.get("type") != edge_type:
                continue
            out.append(
                EdgeRecord(
                    edge_type=edge_type,
                    src_label=src[0],
                    src_id=src[1],
                    dst_label=dst[0],
                    dst_id=dst[1],
                    weight=float(data.get("weight", 1.0)),
                    props={k: v for k, v in data.items() if k not in ("type", "weight")},
                )
            )
        return out
