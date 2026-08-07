"""Dependency graph resolution.

Lock-file edges reference packages by *name* only (version constraints are
usually not a single resolved version).  We resolve each edge to every
candidate package of the same ecosystem — an over-approximation that is
conservative for cycle detection and reachability analysis.  Ambiguities
are surfaced as warnings so downstream consumers know the graph is a
superset of the true install graph.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from .models import PYPI, Package, norm_npm_name, norm_pypi_name


@dataclass
class ResolvedGraph:
    """Name-keyed graph plus per-edge resolution metadata."""

    #: (ecosystem, normalized name) -> candidate packages
    index: dict[tuple[str, str], list[Package]] = field(default_factory=dict)
    #: resolved edges: source identity -> list of target Package
    edges: dict[str, list[Package]] = field(default_factory=dict)
    #: edges that matched no candidate (dangling references)
    dangling: list[tuple[Package, str]] = field(default_factory=list)
    #: edges that matched more than one candidate version
    ambiguous: list[tuple[Package, str, int]] = field(default_factory=list)

    def node_key(self, pkg: Package) -> tuple[str, str]:
        """Normalised (ecosystem, name) key used for name-level graph ops."""
        norm = norm_pypi_name if pkg.ecosystem == PYPI else norm_npm_name
        return (pkg.ecosystem, norm(pkg.name))


def resolve_graph(packages: Iterable[Package]) -> ResolvedGraph:
    """Resolve name-level dependency edges against the package index.

    Returns the name-keyed graph plus dangling/ambiguous edge metadata.
    """
    graph = ResolvedGraph()
    pkgs = list(packages)
    for pkg in pkgs:
        graph.index.setdefault(graph.node_key(pkg), []).append(pkg)

    for pkg in pkgs:
        targets: list[Package] = []
        for dep in pkg.dependencies:
            key = (pkg.ecosystem, _norm(dep.name, pkg.ecosystem))
            candidates = graph.index.get(key, [])
            if not candidates:
                graph.dangling.append((pkg, dep.name))
                continue
            targets.extend(candidates)
            if len(candidates) > 1:
                graph.ambiguous.append((pkg, dep.name, len(candidates)))
        # stable, deterministic ordering (index insertion order is already
        # sorted because merge_inventories sorts packages)
        graph.edges[pkg.identity] = sorted(targets, key=lambda t: (t.ecosystem, t.name, t.version))
    return graph


def _norm(name: str, ecosystem: str) -> str:
    """Normalise a dependency name for the ecosystem's dedupe rule."""
    return norm_pypi_name(name) if ecosystem == PYPI else norm_npm_name(name)
