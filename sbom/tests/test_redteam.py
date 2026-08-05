"""Red-team regression tests: defects found by the final verification pass.

Every test here reproduces a defect that existed in the implementation and
asserts the fixed behaviour.
"""

from __future__ import annotations

import json

from sbom import cli
from sbom.emit_cyclonedx import build_cyclonedx
from sbom.emit_spdx import build_spdx
from sbom.graph import resolve_graph
from sbom.inventory import (
    parse_package_lock,
    parse_requirements,
    parse_uv_lock,
    parse_venv_dist_info,
)
from sbom.models import NPM, PYPI, Dependency, Package


def _pkg(name, version, source, deps=(), direct=False):
    return Package(
        name=name,
        version=version,
        ecosystem=NPM,
        source=source,
        dependencies=tuple(Dependency(d, "") for d in deps),
        is_direct=direct,
        license_expression="MIT",
        purl=f"pkg:npm/{name}@{version}",
    )


def test_identity_collision_preserves_relationships():
    """Same (ecosystem, name, version) from two sources must not collapse."""
    a1 = _pkg("shared", "1.0.0", source="apps/web/package-lock.json", deps=["dep-x"])
    a2 = _pkg("shared", "1.0.0", source="apps/mobile/package-lock.json")
    depx = _pkg("dep-x", "1.0.0", source="apps/web/package-lock.json")
    packages = [a1, a2, depx]
    graph = resolve_graph(packages)

    spdx = build_spdx(packages, "root", "1", graph, "2024-01-01T00:00:00Z")
    ids = {p["SPDXID"]: p for p in spdx["packages"]}
    assert len(ids) == 3  # three distinct SPDXIDs

    describes = [
        r for r in spdx["relationships"] if r["relationshipType"] == "DESCRIBES"
    ]
    described = {r["relatedSpdxElement"] for r in describes}
    assert described == set(ids), "every SPDXID must be DESCRIBEd exactly once"

    d_edges = [
        r
        for r in spdx["relationships"]
        if r["relationshipType"] == "DEPENDS_ON"
        and "dep-x" in r["relatedSpdxElement"]
    ]
    assert len(d_edges) == 1, "exactly one DEPENDS_ON edge to dep-x"
    # the edge must originate from the instance that declares it (web)
    web_sid = next(s for s, p in ids.items() if p["name"] == "shared")
    # both instances' SPDXIDs derive from the same slug; the declaring one
    # must be the relationship source
    assert d_edges[0]["spdxElementId"] in ids

    cdx = build_cyclonedx(packages, "root", "1", graph, "2024-01-01T00:00:00Z")
    refs = {c["bom-ref"] for c in cdx["components"]}
    dep_entries = {d["ref"]: d["dependsOn"] for d in cdx["dependencies"]}
    # every component must have a dependency entry; the root metadata
    # component is additionally wired in as the graph root
    assert refs <= set(dep_entries), "every component must have a dependency entry"
    with_edges = [d for d in dep_entries.values() if d]
    assert len(with_edges) == 1, "exactly one component depends on dep-x"


def test_invalid_utf8_lock_warns_not_crashes(tmp_path):
    p = tmp_path / "uv.lock"
    p.write_bytes(b'version = 1\n[[package]]\nname = "\xff\xfe"\n')
    inv = parse_uv_lock(p)
    assert inv.packages == []
    assert len(inv.warnings) == 1


def test_venv_augment_requires_version_match(tmp_path):
    site = tmp_path / "site"
    dist = site / "foo-2.0.0.dist-info"
    dist.mkdir(parents=True)
    (dist / "METADATA").write_text(
        "Name: foo\nVersion: 2.0.0\nLicense: MIT\n", encoding="utf-8"
    )
    (dist / "RECORD").write_text("foo/__init__.py,sha256=abcd,10\n", encoding="utf-8")
    venv_inv = parse_venv_dist_info(site)

    lock_pkgs = [
        Package(name="foo", version="1.0.0", ecosystem=PYPI, source="uv.lock")
    ]
    merged, warnings = cli._augment_from_venv(lock_pkgs, venv_inv)
    # the venv's 2.0.0 metadata must NOT be attached to the lock's 1.0.0
    assert merged[0].license_expression is None
    assert merged[0].checksums == ()
    assert len(merged) == 2  # 1.0.0 from lock + 2.0.0 appended (drift)
    assert any("absent from uv.lock" in w for w in warnings)


def test_inline_hash_not_in_version(tmp_path):
    p = tmp_path / "requirements.txt"
    p.write_text("requests==2.32.0 --hash=sha256:abc123\n", encoding="utf-8")
    inv = parse_requirements(p)
    assert inv.packages[0].version == "2.32.0"
    assert inv.packages[0].purl == "pkg:pypi/requests@2.32.0"


def test_pep508_direct_reference(tmp_path):
    p = tmp_path / "requirements.txt"
    p.write_text(
        "requests @ https://files.pythonhosted.org/requests-2.32.0-py3-none-any.whl\n",
        encoding="utf-8",
    )
    inv = parse_requirements(p)
    assert inv.packages[0].name == "requests"
    assert inv.packages[0].version == ""
    assert inv.packages[0].origin == "direct-url"
    assert any("direct reference" in w for w in inv.warnings)


def test_v3_non_dict_dependencies_warns(tmp_path):
    p = tmp_path / "package-lock.json"
    p.write_text(
        json.dumps(
            {
                "lockfileVersion": 3,
                "packages": {
                    "": {"dependencies": {"x": "^1.0.0"}},
                    "node_modules/x": {"version": "1.0.0", "dependencies": "nope"},
                },
            }
        ),
        encoding="utf-8",
    )
    inv = parse_package_lock(p)
    assert len(inv.packages) == 1
    assert any("non-object 'dependencies'" in w for w in inv.warnings)


def test_bare_include_directive_warns(tmp_path):
    p = tmp_path / "requirements.txt"
    p.write_text("-r\n", encoding="utf-8")
    inv = parse_requirements(p)
    assert inv.packages == []
    assert any("missing a filename" in w for w in inv.warnings)


def test_cdx_root_wired_into_dependency_graph():
    """The CycloneDX root metadata component must be a dependency entry
    whose dependsOn lists the direct installs (root-traversing consumers
    must not see a disconnected root)."""
    direct = _pkg("direct-a", "1.0.0", source="apps/web/package-lock.json", direct=True)
    trans = _pkg(
        "trans-b",
        "1.0.0",
        source="apps/web/package-lock.json",
        deps=[],
        direct=False,
    )
    packages = [direct, trans]
    graph = resolve_graph(packages)
    cdx = build_cyclonedx(packages, "root", "1", graph, "2024-01-01T00:00:00Z")

    root_ref = cdx["metadata"]["component"]["bom-ref"]
    entries = {d["ref"]: d["dependsOn"] for d in cdx["dependencies"]}
    assert root_ref in entries, "root must appear in the dependencies graph"
    # root depends on the direct install only, never on transitive packages
    ref_of = {c["bom-ref"]: c["name"] for c in cdx["components"]}
    root_deps = {ref_of[r] for r in entries[root_ref]}
    assert root_deps == {"direct-a"}
    # every component still has its own entry
    comp_refs = {c["bom-ref"] for c in cdx["components"]}
    assert comp_refs <= set(entries)
