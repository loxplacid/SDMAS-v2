"""Unit tests for the evidence test-manifest + checksum module."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

from evidence.manifest import (
    build_test_manifest,
    collect_tree,
    parse_junit,
    sha256_file,
    write_artifact_manifest,
    write_checksums,
)


def _write_junit(path: Path, *, tests: int, failures: int, skipped: int) -> Path:
    root = ET.Element(
        "testsuite",
        {
            "tests": str(tests),
            "failures": str(failures),
            "errors": "0",
            "skipped": str(skipped),
            "time": "1.5",
        },
    )
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=False)
    return path


def test_parse_junit_counts(tmp_path: Path) -> None:
    path = _write_junit(tmp_path / "suite.xml", tests=10, failures=2, skipped=1)
    summary = parse_junit(path)
    assert summary is not None
    assert summary["ran"] is True
    assert summary["tests"] == 10
    assert summary["passed"] == 7  # 10 - 2 failures - 1 skipped
    assert summary["failed"] == 2
    assert summary["skipped"] == 1
    assert summary["duration_seconds"] == 1.5


def test_parse_junit_pytest_nested_shape(tmp_path: Path) -> None:
    # pytest wraps totals on an inner <testsuite> under <testsuites>.
    inner = ET.Element(
        "testsuite",
        {
            "name": "pytest",
            "tests": "58",
            "failures": "0",
            "errors": "0",
            "skipped": "0",
            "time": "50.89",
        },
    )
    outer = ET.Element("testsuites", {"name": "pytest tests"})
    outer.append(inner)
    ET.ElementTree(outer).write(tmp_path / "nested.xml", encoding="utf-8", xml_declaration=False)
    summary = parse_junit(tmp_path / "nested.xml")
    assert summary is not None
    assert summary["tests"] == 58
    assert summary["passed"] == 58


def test_parse_junit_missing_file(tmp_path: Path) -> None:
    assert parse_junit(tmp_path / "nope.xml") is None


def test_build_test_manifest_totals(tmp_path: Path) -> None:
    s1 = _write_junit(tmp_path / "a.xml", tests=20, failures=1, skipped=0)
    s2 = _write_junit(tmp_path / "b.xml", tests=5, failures=0, skipped=2)
    manifest = build_test_manifest(tmp_path, {"api-unit": s1, "api-security": s2})
    totals = manifest["totals"]
    assert totals["tests"] == 25
    assert totals["passed"] == 22  # 19 + 3
    assert totals["failed"] == 1
    assert totals["skipped"] == 2
    assert manifest["suites"]["api-unit"]["passed"] == 19


def test_unrun_suite_is_recorded_not_fabricated(tmp_path: Path) -> None:
    manifest = build_test_manifest(tmp_path, {"api-integration": None})
    assert manifest["suites"]["api-integration"] == {"ran": False}
    # An unrun suite must not contribute fake counts to totals.
    assert manifest["totals"]["tests"] == 0


def test_sha256_file(tmp_path: Path) -> None:
    p = tmp_path / "data.bin"
    p.write_bytes(b"hello evidence")
    expected = hashlib.sha256(b"hello evidence").hexdigest()
    assert sha256_file(p) == expected


def test_write_checksums_and_manifest(tmp_path: Path) -> None:
    (tmp_path / "security").mkdir()
    f = tmp_path / "security" / "bandit.json"
    f.write_text("{}", encoding="utf-8")
    files = collect_tree(tmp_path)
    checksums = write_checksums(tmp_path / "SHA256SUMS", files)
    assert checksums["bandit.json"]
    manifest = write_artifact_manifest(
        tmp_path / "artifact-manifest.json",
        commit="abc123",
        generator="test",
        version="1",
        checksums=checksums,
    )
    assert manifest["commit_sha"] == "abc123"
    assert manifest["artifacts"]["bandit.json"]["sha256"] == checksums["bandit.json"]
    assert (
        (tmp_path / "SHA256SUMS").read_text(encoding="utf-8").startswith(checksums["bandit.json"])
    )
