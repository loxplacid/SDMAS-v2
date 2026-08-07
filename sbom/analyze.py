"""Data-quality analysis of the merged inventory.

Produces the companion artefacts of the SBOM:

* ``license_summary.json`` — license distribution + unknown-license count.
* ``duplicate_dependencies.json`` — the same package at multiple versions
  (or across multiple projects/ecosystems).
* ``dependency_metrics.json`` — graph statistics (sizes, orphaned nodes,
  cycles, depth).
* ``dependency_risk_report.json`` — supply-chain risk findings with
  severities.

All outputs are deterministic (sorted, stable keys).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable

from .graph import ResolvedGraph
from .licenses import COMMON_SPDX_IDS
from .models import Package

# ---------------------------------------------------------------------------
# license summary
# ---------------------------------------------------------------------------


def license_summary(packages: Iterable[Package]) -> dict:
    """Distribution of declared licenses plus the unknown-license count."""
    packages = list(packages)
    counts: Counter[str] = Counter()
    unknown = 0
    for pkg in packages:
        if pkg.license_expression:
            counts[pkg.license_expression] += 1
        else:
            unknown += 1
    return {
        "total_packages": len(packages),
        "packages_with_license": len(packages) - unknown,
        "packages_without_license": unknown,
        "by_license": dict(sorted(counts.items())),
    }


# ---------------------------------------------------------------------------
# duplicates
# ---------------------------------------------------------------------------


def duplicate_dependencies(packages: Iterable[Package]) -> list[dict]:
    """Flag the same logical package (ecosystem + normalized name) present at
    more than one version, or from more than one source."""
    groups: dict[tuple[str, str], list[Package]] = defaultdict(list)
    for pkg in packages:
        groups[pkg.dedupe_key].append(pkg)

    findings: list[dict] = []
    for key, members in sorted(groups.items()):
        versions = {m.version for m in members}
        sources = {m.source for m in members}
        if len(versions) > 1:
            findings.append(
                {
                    "ecosystem": key[0],
                    "name": members[0].name,
                    "severity": "medium",
                    "kind": "multiple_versions",
                    "versions": sorted(versions),
                    "sources": sorted(sources),
                }
            )
        elif len(sources) > 1 and len(versions) == 1:
            findings.append(
                {
                    "ecosystem": key[0],
                    "name": members[0].name,
                    "severity": "info",
                    "kind": "multiple_sources_same_version",
                    "versions": sorted(versions),
                    "sources": sorted(sources),
                }
            )
    return findings


def cross_ecosystem_collisions(packages: Iterable[Package]) -> list[dict]:
    """Names that exist in both the pypi and npm inventories."""
    by_name: dict[str, set[str]] = defaultdict(set)
    for pkg in packages:
        by_name[pkg.name.lower()].add(pkg.ecosystem)
    return [
        {"name": name, "ecosystems": sorted(ecos)}
        for name, ecos in sorted(by_name.items())
        if len(ecos) > 1
    ]


# ---------------------------------------------------------------------------
# graph metrics
# ---------------------------------------------------------------------------


def dependency_metrics(packages: list[Package], graph: ResolvedGraph) -> dict:
    """Graph statistics: sizes, edges, orphans, cycles and bounded depth."""
    direct = [p for p in packages if p.is_direct]
    direct_keys = {graph.node_key(p) for p in direct}

    # reachability from direct packages (node-key level, version-agnostic)
    adj: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for pkg in packages:
        for target in graph.edges.get(pkg.identity, []):
            adj[graph.node_key(pkg)].add(graph.node_key(target))

    reachable: set[tuple[str, str]] = set()
    stack = list(direct_keys)
    while stack:
        node = stack.pop()
        if node in reachable:
            continue
        reachable.add(node)
        stack.extend(adj[node] - reachable)

    node_keys = {graph.node_key(p) for p in packages}
    orphaned = sorted(node_keys - reachable - direct_keys)

    # cycle detection (iterative DFS, name-level graph)
    cycles = _find_cycles(adj)

    # max depth from direct roots (BFS layered)
    depth = _max_depth(direct_keys, adj, node_keys)

    return {
        "total_packages": len(packages),
        "direct_packages": len(direct),
        "transitive_packages": len(packages) - len(direct),
        "by_ecosystem": dict(sorted(Counter(p.ecosystem for p in packages).items())),
        "dependency_edges": sum(len(v) for v in graph.edges.values()),
        "dangling_edges": len(graph.dangling),
        "ambiguous_edges": len(graph.ambiguous),
        "orphaned_packages": len(orphaned),
        "orphaned_names": orphaned,
        "cycles": cycles,
        "max_depth": depth,
        "empty_version_packages": [
            {"ecosystem": p.ecosystem, "name": p.name} for p in packages if not p.version
        ],
    }


def _find_cycles(adj: dict[tuple[str, str], set[tuple[str, str]]]) -> list[list[str]]:
    """Return one representative cycle per strongly-connected component
    (name-level).  Deterministic: nodes visited in sorted order."""
    WHITE, GREY, BLACK = 0, 1, 2
    color: dict[tuple[str, str], int] = {}
    cycles: list[list[str]] = []

    for start in sorted(adj):
        if color.get(start, WHITE) != WHITE:
            continue
        stack: list[tuple[tuple[str, str], int]] = [(start, 0)]
        color[start] = GREY
        path: list[tuple[str, str]] = [start]
        while stack:
            node, idx = stack[-1]
            neighbors = sorted(adj.get(node, ()))
            advanced = False
            while idx < len(neighbors):
                nxt = neighbors[idx]
                stack[-1] = (node, idx + 1)
                if color.get(nxt, WHITE) == GREY:
                    # found a cycle: slice path from nxt to node
                    try:
                        start_i = path.index(nxt)
                    except ValueError:
                        start_i = 0
                    cyc = [n[1] for n in path[start_i:]] + [nxt[1]]
                    if cyc not in cycles:
                        cycles.append(cyc)
                    advanced = True
                    break
                if color.get(nxt, WHITE) == WHITE:
                    color[nxt] = GREY
                    path.append(nxt)
                    stack.append((nxt, 0))
                    advanced = True
                    break
                idx += 1
            if not advanced and idx >= len(neighbors):
                color[node] = BLACK
                path.pop()
                stack.pop()
    return cycles


def _max_depth(
    roots: set[tuple[str, str]],
    adj: dict[tuple[str, str], set[tuple[str, str]]],
    nodes: set[tuple[str, str]],
) -> int:
    """Layered longest-path bound from any direct root.

    The resolved graph is an over-approximation and may contain cycles, so
    the true longest path is unbounded.  We report a *bounded* layered
    measure instead: each node is advanced at most once per round (deduped)
    and the value is capped at ``len(nodes)`` — deterministic, sane, and
    equal to the true longest path when the graph is acyclic.  The presence
    of cycles is reported separately in ``cycles``.
    """
    dist: dict[tuple[str, str], int] = {}
    frontier = sorted(roots)
    for node in frontier:
        dist[node] = 0
    depth = 0
    cap = len(nodes)
    guard = 0
    while frontier and guard <= cap + 1:
        nxt: set[tuple[str, str]] = set()
        for node in frontier:
            nd = dist[node] + 1
            for neighbor in sorted(adj.get(node, ())):
                if nd > dist.get(neighbor, -1) and dist.get(neighbor, -1) < cap:
                    dist[neighbor] = nd
                    nxt.add(neighbor)
        depth = max([depth] + [dist[n] for n in nxt]) if nxt else depth
        frontier = sorted(nxt)
        guard += 1
    return min(depth, cap)


# ---------------------------------------------------------------------------
# risk report
# ---------------------------------------------------------------------------


def dependency_risk_report(
    packages: list[Package],
    graph: ResolvedGraph,
    warnings: list[str],
) -> dict:
    """Severity-tagged supply-chain findings for the inventory and graph."""
    findings: list[dict] = []
    for pkg in packages:
        if pkg.origin in {"git", "editable", "path", "workspace"}:
            findings.append(
                {
                    "severity": "high",
                    "category": "non_registry_origin",
                    "package": f"{pkg.ecosystem}/{pkg.name}@{pkg.version}",
                    "message": f"resolved from {pkg.origin} instead of a registry",
                }
            )
        if not pkg.version:
            findings.append(
                {
                    "severity": "high",
                    "category": "missing_version",
                    "package": f"{pkg.ecosystem}/{pkg.name}",
                    "message": "no version resolved from lock file",
                }
            )
        if not pkg.license_expression:
            findings.append(
                {
                    "severity": "medium",
                    "category": "missing_license",
                    "package": f"{pkg.ecosystem}/{pkg.name}@{pkg.version}",
                    "message": "no license metadata available",
                }
            )
        elif pkg.license_expression not in COMMON_SPDX_IDS:
            findings.append(
                {
                    "severity": "low",
                    "category": "custom_license",
                    "package": f"{pkg.ecosystem}/{pkg.name}@{pkg.version}",
                    "message": f"license '{pkg.license_expression}' is not a standard SPDX id",
                }
            )
    for src, dep_name in graph.dangling:
        findings.append(
            {
                "severity": "medium",
                "category": "dangling_dependency",
                "package": f"{src.ecosystem}/{src.name}@{src.version}",
                "message": f"depends on '{dep_name}' which is not in the inventory",
            }
        )
    for pkg, dep_name, n in graph.ambiguous:
        findings.append(
            {
                "severity": "low",
                "category": "ambiguous_dependency",
                "package": f"{pkg.ecosystem}/{pkg.name}@{pkg.version}",
                "message": f"'{dep_name}' resolves to {n} candidate versions",
            }
        )
    findings.extend(
        {"severity": "info", "category": "inventory_warning", "package": None, "message": w}
        for w in warnings
    )
    findings.sort(key=lambda f: (f["severity"], f["category"], str(f["package"])))
    return {
        "total_findings": len(findings),
        "by_severity": dict(sorted(Counter(f["severity"] for f in findings).items())),
        "findings": findings,
    }
