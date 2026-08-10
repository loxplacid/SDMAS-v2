"""Test evidence manifest — parse JUnit XML + collect environment metadata.

The manifest is the machine-readable record of what was actually tested:
suite name, counts, pass/fail/skip, durations, and the environment that ran
them.  It is deliberately *report-only*: it never invents numbers.  A suite
that did not run is recorded with ``{"ran": false}`` rather than a fake
``passed`` count.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: Order suites are listed in the manifest (stable, human-readable).
SUITE_ORDER = [
    "api-unit",
    "api-security",
    "api-tenant-isolation",
    "api-rbac",
    "api-finance",
    "api-outbox",
    "api-jobs-async",
    "api-migration",
    "api-integration",
    "web",
    "mobile",
    "sbom",
]


def sha256_file(path: Path) -> str:
    """SHA-256 of a file's bytes, hex-encoded."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit_sha(root: Path) -> str:
    """The current HEAD commit, or an empty string when not a git repo."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def tool_version(name: str) -> str:
    """Version of a CLI tool, or '' when unavailable."""
    try:
        out = subprocess.run(
            [name, "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return (
            (out.stdout or out.stderr).strip().splitlines()[0:1][0]
            if (out.stdout or out.stderr)
            else ""
        )
    except (OSError, subprocess.SubprocessError):
        return ""


def environment(root: Path) -> dict[str, str]:
    """Reproducible metadata about the environment that produced the run."""
    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "python": platform.python_version(),
        "node": tool_version("node"),
        "pytest": tool_version("pytest"),
        "commit_sha": git_commit_sha(root),
        "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def parse_junit(path: Path) -> dict[str, Any] | None:
    """Parse a pytest ``--junitxml`` file into a suite summary.

    Returns ``None`` when the file is missing or unparsable (the caller
    records ``ran: False`` instead of guessing).
    """
    try:
        tree = ET.parse(path)
    except (OSError, ET.ParseError):
        return None
    root = tree.getroot()
    # pytest emits ``<testsuites><testsuite .../>``; vitest puts the totals
    # on the root ``testsuites`` element.  Walk both shapes so counts are
    # always read from the element that actually carries them.
    node = root
    if root.tag == "testsuites" and not root.attrib.get("tests"):
        # Explicit ``is None`` — Python 3.13 deprecates Element truthiness,
        # and a childless <testsuite> would otherwise be falsy.
        inner = root.find("testsuite")
        node = inner if inner is not None else root
    tests = int(node.attrib.get("tests", 0))
    failures = int(node.attrib.get("failures", 0))
    errors = int(node.attrib.get("errors", 0))
    skipped = int(node.attrib.get("skipped", 0))
    time = float(node.attrib.get("time", 0.0))
    passed = tests - failures - errors - skipped
    return {
        "ran": True,
        "tests": tests,
        "passed": max(passed, 0),
        "failed": failures + errors,
        "skipped": skipped,
        "duration_seconds": round(time, 3),
    }


def build_test_manifest(
    root: Path,
    suites: dict[str, Path | None],
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the full test manifest from JUnit XML files.

    ``suites`` maps a suite key to its junitxml path (or ``None`` when it was
    intentionally not run, e.g. integration tests without Docker).
    """
    result: dict[str, Any] = {"_schema": "sdmas-test-manifest/1", "environment": environment(root)}
    per_suite: dict[str, Any] = {}
    for key in SUITE_ORDER:
        if key in suites:
            path = suites[key]
            per_suite[key] = parse_junit(path) if path else {"ran": False}
    # Any suites not in the canonical order (keep them, sorted).
    for key in suites:
        if key not in per_suite:
            path = suites[key]
            per_suite[key] = parse_junit(path) if path else {"ran": False}
    result["suites"] = per_suite

    totals = {"tests": 0, "passed": 0, "failed": 0, "skipped": 0, "duration_seconds": 0.0}
    for s in per_suite.values():
        if not s.get("ran"):
            continue
        for k in ("tests", "passed", "failed", "skipped"):
            totals[k] += s.get(k, 0)
        totals["duration_seconds"] += s.get("duration_seconds", 0.0)
    result["totals"] = totals
    if extra:
        result.update(extra)
    return result


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_checksums(path: Path, files: list[Path]) -> dict[str, str]:
    """Write a ``SHA256SUMS`` file and return the mapping."""
    entries: dict[str, str] = {}
    for f in sorted(files, key=lambda p: p.name):
        if f.is_file():
            entries[f.name] = sha256_file(f)
    lines = [f"{digest}  {name}" for name, digest in sorted(entries.items())]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return entries


def write_artifact_manifest(
    path: Path,
    *,
    commit: str,
    generator: str,
    version: str,
    checksums: dict[str, str],
) -> dict[str, Any]:
    """Write the immutable artifact manifest (artifact → SHA-256)."""
    manifest = {
        "_schema": "sdmas-artifact-manifest/1",
        "generator": generator,
        "generator_version": version,
        "commit_sha": commit,
        "generation_date_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "artifacts": {name: {"sha256": digest} for name, digest in sorted(checksums.items())},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def collect_tree(root: Path) -> list[Path]:
    """Recursively list regular files under ``root`` (for checksumming)."""
    out: list[Path] = []
    for base, _dirs, files in os.walk(root):
        for name in files:
            p = Path(base) / name
            if p.is_file():
                out.append(p)
    return out
