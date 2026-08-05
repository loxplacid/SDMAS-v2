"""Emitter tests: SPDX 2.3 and CycloneDX 1.5 structure + determinism."""

from __future__ import annotations

import json

import pytest

from sbom.emit_cyclonedx import build_cyclonedx
from sbom.emit_spdx import build_spdx, created_timestamp
from sbom.graph import resolve_graph
from sbom.inventory import Inventory, parse_package_lock, parse_uv_lock
from sbom.models import PYPI, Package
from sbom.validate import validate

UV = """\
[[package]]
name = "aiosqlite"
version = "0.22.1"
source = { registry = "https://pypi.org/simple" }
wheels = [{ url = "https://example.invalid/a.whl", hash = "sha256:abababababababababababababababababababababababababababababababab" }]

[[package]]
name = "alembic"
version = "1.18.5"
source = { registry = "https://pypi.org/simple" }
dependencies = [{ name = "aiosqlite" }]
"""


def _packages(tmp_path):
    p = tmp_path / "uv.lock"
    p.write_text(UV, encoding="utf-8")
    return parse_uv_lock(p).packages


def _docs(tmp_path, created="2024-01-01T00:00:00Z"):
    packages = _packages(tmp_path)
    graph = resolve_graph(packages)
    spdx = build_spdx(packages, "root", "1.0", graph, created)
    cdx = build_cyclonedx(packages, "root", "1.0", graph, created)
    return spdx, cdx, packages


def test_spdx_required_fields(tmp_path):
    spdx, _, _ = _docs(tmp_path)
    assert spdx["spdxVersion"] == "SPDX-2.3"
    assert spdx["dataLicense"] == "CC0-1.0"
    assert spdx["SPDXID"] == "SPDXRef-DOCUMENT"
    assert spdx["documentNamespace"].startswith("https://")
    assert spdx["creationInfo"]["created"] == "2024-01-01T00:00:00Z"
    assert all(p["SPDXID"].startswith("SPDXRef-Package-") for p in spdx["packages"])
    assert len(spdx["relationships"]) >= 2  # DESCRIBES x2 + DEPENDS_ON


def test_spdx_id_validation_and_uniqueness(tmp_path):
    spdx, _, _ = _docs(tmp_path)
    ids = [p["SPDXID"] for p in spdx["packages"]]
    assert len(ids) == len(set(ids))


def test_spdx_depends_on_edges(tmp_path):
    spdx, _, packages = _docs(tmp_path)
    alembic_id = next(
        p["SPDXID"] for p in spdx["packages"] if p["name"] == "alembic"
    )
    aio_id = next(p["SPDXID"] for p in spdx["packages"] if p["name"] == "aiosqlite")
    assert any(
        r["spdxElementId"] == alembic_id
        and r["relationshipType"] == "DEPENDS_ON"
        and r["relatedSpdxElement"] == aio_id
        for r in spdx["relationships"]
    )


def test_cyclonedx_required_fields(tmp_path):
    _, cdx, _ = _docs(tmp_path)
    assert cdx["bomFormat"] == "CycloneDX"
    assert cdx["specVersion"] == "1.5"
    assert cdx["serialNumber"].startswith("urn:uuid:")
    assert cdx["metadata"]["timestamp"] == "2024-01-01T00:00:00Z"
    assert cdx["metadata"]["component"]["type"] == "application"
    assert len(cdx["components"]) == 2
    refs = {c["bom-ref"] for c in cdx["components"]}
    assert len(refs) == 2
    # every dependency entry ref must be a known identifier: a component or
    # the root metadata component (wired into the graph since X3)
    known = refs | {cdx["metadata"]["component"]["bom-ref"]}
    assert all(d["ref"] in known for d in cdx["dependencies"])
    assert cdx["metadata"]["component"]["bom-ref"] in {
        d["ref"] for d in cdx["dependencies"]
    }


def test_deterministic_namespace_and_serial(tmp_path):
    spdx1, cdx1, _ = _docs(tmp_path)
    spdx2, cdx2, _ = _docs(tmp_path)
    assert spdx1["documentNamespace"] == spdx2["documentNamespace"]
    assert cdx1["serialNumber"] == cdx2["serialNumber"]
    assert spdx1 == spdx2 and cdx1 == cdx2


def test_determinism_changes_with_content(tmp_path):
    spdx1, _, _ = _docs(tmp_path)
    packages = _packages(tmp_path)
    packages = packages + [
        Package(name="extra", version="1.0", ecosystem=PYPI, source="x")
    ]
    graph = resolve_graph(packages)
    spdx2 = build_spdx(packages, "root", "1.0", graph, "2024-01-01T00:00:00Z")
    assert spdx1["documentNamespace"] != spdx2["documentNamespace"]


def test_created_timestamp_source_date_epoch():
    assert created_timestamp("0") == "1970-01-01T00:00:00Z"
    assert created_timestamp("1704067200") == "2024-01-01T00:00:00Z"
    with pytest.raises(ValueError):
        created_timestamp("not-a-number")
    with pytest.raises(ValueError):
        created_timestamp("99999999999999999999")


def test_license_handling():
    pkg = Package(
        name="x",
        version="1",
        ecosystem=PYPI,
        source="s",
        license_expression="MIT AND Apache-2.0",
    )
    graph = resolve_graph([pkg])
    spdx = build_spdx([pkg], "r", "1", graph, "2024-01-01T00:00:00Z")
    assert spdx["packages"][0]["licenseDeclared"] == "MIT AND Apache-2.0"
    cdx = build_cyclonedx([pkg], "r", "1", graph, "2024-01-01T00:00:00Z")
    assert cdx["components"][0]["licenses"] == [{"expression": "MIT AND Apache-2.0"}]


def test_generated_documents_pass_validation(tmp_path):
    spdx, cdx, _ = _docs(tmp_path)
    assert validate([("spdx", spdx), ("cyclonedx", cdx)]) == []
