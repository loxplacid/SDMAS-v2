"""Validator tests: good documents pass, tampered documents fail."""

from __future__ import annotations

import copy

from sbom.emit_cyclonedx import build_cyclonedx
from sbom.emit_spdx import build_spdx
from sbom.graph import resolve_graph
from sbom.models import PYPI, Package
from sbom.validate import validate


def _pkg(name="a", version="1.0", **kw):
    return Package(
        name=name,
        version=version,
        ecosystem=PYPI,
        source="s",
        purl=f"pkg:pypi/{name}@{version}",
        license_expression="MIT",
        **kw,
    )


def _docs():
    pkgs = [_pkg(), _pkg("b", "2.0", dependencies=())]
    graph = resolve_graph(pkgs)
    created = "2024-01-01T00:00:00Z"
    spdx = build_spdx(pkgs, "root", "1", graph, created)
    cdx = build_cyclonedx(pkgs, "root", "1", graph, created)
    return spdx, cdx


def test_valid_documents_pass():
    spdx, cdx = _docs()
    assert validate([("spdx", spdx), ("cyclonedx", cdx)]) == []


def test_spdx_rejects_duplicate_spdxid():
    spdx, _ = _docs()
    spdx["packages"][1]["SPDXID"] = spdx["packages"][0]["SPDXID"]
    assert any("duplicate SPDXID" in e for e in validate([("spdx", spdx)]))


def test_spdx_rejects_bad_license():
    spdx, _ = _docs()
    spdx["packages"][0]["licenseDeclared"] = "Not A Real License!!!"
    assert any("invalid SPDX license expression" in e for e in validate([("spdx", spdx)]))


def test_spdx_rejects_bad_purl():
    spdx, _ = _docs()
    spdx["packages"][0]["externalRefs"][0]["referenceLocator"] = "pkg:/nope"
    assert any("malformed purl" in e for e in validate([("spdx", spdx)]))


def test_spdx_rejects_dangling_relationship():
    spdx, _ = _docs()
    spdx["relationships"][0]["relatedSpdxElement"] = "SPDXRef-Package-does-not-exist"
    assert any("unknown related element" in e for e in validate([("spdx", spdx)]))


def test_cdx_rejects_duplicate_bom_ref():
    _, cdx = _docs()
    cdx["components"][1]["bom-ref"] = cdx["components"][0]["bom-ref"]
    assert any("duplicate bom-ref" in e for e in validate([("cyclonedx", cdx)]))


def test_cdx_rejects_bad_serial():
    _, cdx = _docs()
    cdx["serialNumber"] = "urn:uuid:not-a-uuid"
    assert any("not a valid UUID" in e for e in validate([("cyclonedx", cdx)]))


def test_cdx_rejects_bad_license_id():
    _, cdx = _docs()
    cdx["components"][0]["licenses"] = [{"license": {"id": "Nope"}}]
    assert any("unknown SPDX license id" in e for e in validate([("cyclonedx", cdx)]))
