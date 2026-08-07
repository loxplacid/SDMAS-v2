"""Analysis tests: duplicates, cycles, orphans, metrics, risk report."""

from __future__ import annotations

from sbom.analyze import (
    cross_ecosystem_collisions,
    dependency_metrics,
    dependency_risk_report,
    duplicate_dependencies,
    license_summary,
)
from sbom.graph import resolve_graph
from sbom.models import NPM, PYPI, Dependency, Package


def _pkg(name, version, ecosystem=PYPI, deps=(), direct=True, origin=None, license_expr=None):
    return Package(
        name=name,
        version=version,
        ecosystem=ecosystem,
        source="s",
        dependencies=tuple(Dependency(d, "") for d in deps),
        is_direct=direct,
        origin=origin,
        license_expression=license_expr,
    )


def test_license_summary_counts():
    pkgs = [
        _pkg("a", "1", license_expr="MIT"),
        _pkg("b", "1", license_expr="MIT"),
        _pkg("c", "1"),
    ]
    s = license_summary(pkgs)
    assert s["total_packages"] == 3
    assert s["packages_without_license"] == 1
    assert s["by_license"] == {"MIT": 2}


def test_duplicate_versions_detected():
    pkgs = [_pkg("a", "1.0"), _pkg("a", "2.0")]
    dups = duplicate_dependencies(pkgs)
    assert len(dups) == 1
    assert dups[0]["kind"] == "multiple_versions"
    assert dups[0]["versions"] == ["1.0", "2.0"]


def test_cross_ecosystem_collision():
    pkgs = [_pkg("progress", "1.0", PYPI), _pkg("progress", "2.0", NPM)]
    assert cross_ecosystem_collisions(pkgs) == [{"name": "progress", "ecosystems": ["npm", "pypi"]}]


def test_cycle_detection():
    pkgs = [
        _pkg("a", "1", deps=["b"], direct=True),
        _pkg("b", "1", deps=["c"]),
        _pkg("c", "1", deps=["a"]),
    ]
    graph = resolve_graph(pkgs)
    m = dependency_metrics(pkgs, graph)
    assert len(m["cycles"]) == 1
    assert set(m["cycles"][0]) == {"a", "b", "c"}


def test_orphaned_and_depth():
    pkgs = [
        _pkg("root", "1", deps=["mid"], direct=True),
        _pkg("mid", "1", deps=["leaf"], direct=False),
        _pkg("leaf", "1", direct=False),
        _pkg("lone", "1", direct=False),
    ]
    graph = resolve_graph(pkgs)
    m = dependency_metrics(pkgs, graph)
    assert m["direct_packages"] == 1
    assert m["transitive_packages"] == 3
    assert ("pypi", "lone") in m["orphaned_names"]
    assert m["max_depth"] == 2  # root -> mid -> leaf


def test_risk_report_high_severity():
    pkgs = [
        _pkg("gitpkg", "1", origin="git"),
        _pkg("nover", "", direct=False),
        _pkg("ok", "1", license_expr="MIT"),
    ]
    graph = resolve_graph(pkgs)
    report = dependency_risk_report(pkgs, graph, [])
    high = [f for f in report["findings"] if f["severity"] == "high"]
    assert len(high) == 2
    assert report["by_severity"]["high"] == 2


def test_dangling_edge_reported():
    pkgs = [_pkg("a", "1", deps=["ghost"], direct=True)]
    graph = resolve_graph(pkgs)
    assert len(graph.dangling) == 1
    report = dependency_risk_report(pkgs, graph, [])
    assert any(f["category"] == "dangling_dependency" for f in report["findings"])
