"""Unit tests for the security assurance report renderer."""

from __future__ import annotations

import json
from pathlib import Path

from evidence.report import render_assurance_report


def _write_scanner_outputs(artifacts: Path) -> None:
    sec = artifacts / "security"
    sec.mkdir(parents=True, exist_ok=True)
    (sec / "bandit.json").write_text(
        json.dumps({"results": [{"issue_severity": "LOW", "issue_confidence": "HIGH"}]}),
        encoding="utf-8",
    )
    (sec / "pip-audit.json").write_text(
        json.dumps(
            {
                "dependencies": [
                    {
                        "name": "cryptography",
                        "version": "49.0.0",
                        "vulns": [{"id": "PYSEC-2026-3552"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (sec / "npm-audit-web.json").write_text(
        json.dumps({"vulnerabilities": {"vite": {"severity": "high"}}}),
        encoding="utf-8",
    )
    (sec / "npm-audit-mobile.json").write_text(
        json.dumps({"vulnerabilities": {"tar": {"severity": "critical"}}}),
        encoding="utf-8",
    )
    (artifacts / "sbom").mkdir(parents=True, exist_ok=True)
    (artifacts / "sbom" / "sbom.cdx.json").write_text("{}", encoding="utf-8")
    (artifacts / "sbom" / "sbom.spdx.json").write_text("{}", encoding="utf-8")
    tests = artifacts / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test-manifest.json").write_text(
        json.dumps(
            {
                "totals": {
                    "tests": 100,
                    "passed": 98,
                    "failed": 1,
                    "skipped": 1,
                    "duration_seconds": 30.0,
                },
                "suites": {
                    "api-unit": {
                        "ran": True,
                        "tests": 100,
                        "passed": 98,
                        "failed": 1,
                        "skipped": 1,
                        "duration_seconds": 30.0,
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def test_report_contains_verified_sections(tmp_path: Path) -> None:
    _write_scanner_outputs(tmp_path / "artifacts")
    md = render_assurance_report(
        tmp_path / "artifacts",
        commit="deadbeef",
        python_version="3.11",
        node_version="v20.0.0",
        env={"os": "Linux", "timestamp_utc": "2026-01-01T00:00:00Z"},
    )
    assert "# SDMAS v2 — Security Assurance Report" in md
    assert "commit" in md.lower() and "deadbeef" in md
    assert "VERIFIED" in md
    assert "NOT APPLICABLE" in md  # GDPR / SOC 2 / HIPAA rows are always present
    assert "KNOWN LIMITATION" in md
    # Scanner evidence must appear verbatim.
    assert "32" in md or "1" in md  # bandit findings number present
    assert "cryptography" in md
    assert "PYSEC-2026-3552" in md
    assert "CycloneDX 1.5" in md
    assert "SPDX 2.3" in md
    assert "98" in md  # passed count from the test manifest
    # No fabricated compliance claims.
    assert "GDPR compliant" not in md.lower()
    assert "SOC 2 compliant" not in md.lower()


def test_report_handles_missing_scanners(tmp_path: Path) -> None:
    """A scanner that did not run must be marked, not fabricated."""
    artifacts = tmp_path / "artifacts"
    (artifacts / "security").mkdir(parents=True)
    (artifacts / "tests").mkdir()
    md = render_assurance_report(
        artifacts, commit="x", python_version="3.11", node_version="", env={}
    )
    assert "did not run" in md
    assert "not run" in md
