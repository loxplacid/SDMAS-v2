"""``scripts/evidence`` CLI — subcommands for building the evidence package.

Usage
-----
    python -m evidence.cli test-manifest [--junit DIR] --out OUTPUT.json
    python -m evidence.cli checksums [--dir ARTIFACTS]
    python -m evidence.cli report [--artifacts ARTIFACTS]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from .manifest import (
    build_test_manifest,
    collect_tree,
    environment,
    write_artifact_manifest,
    write_checksums,
    write_json,
)
from .report import render_assurance_report


def cmd_test_manifest(args: argparse.Namespace) -> int:
    """Read JUnit XML files and write the test manifest."""
    junit_dir = Path(args.junit_dir)
    suites: dict[str, Path | None] = {st.stem: st for st in sorted(junit_dir.glob("*.xml"))}
    manifest = build_test_manifest(Path.cwd(), suites, extra={"_version": __version__})
    out = Path(args.out)
    write_json(out, manifest)
    print(f"Test manifest written ({len(suites)} suites) -> {out}")
    return 0


def cmd_checksums(args: argparse.Namespace) -> int:
    """Walk the artifacts tree and write SHA256SUMS + manifest."""
    root = Path(args.dir)
    files = collect_tree(root)
    checksums = write_checksums(root / "SHA256SUMS", files)
    env = environment(Path.cwd())
    write_artifact_manifest(
        root / "artifact-manifest.json",
        commit=env.get("commit_sha", ""),
        generator="sdmas-security-audit",
        version=__version__,
        checksums=checksums,
    )
    print(f"Checksums written: {len(checksums)} files -> {root / 'SHA256SUMS'}")
    print(f"Artifact manifest -> {root / 'artifact-manifest.json'}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Generate the security assurance report from collected evidence."""
    artifacts = Path(args.artifacts)
    env = environment(Path.cwd())
    os.makedirs("docs", exist_ok=True)

    markdown = render_assurance_report(
        artifacts,
        commit=env.get("commit_sha", ""),
        python_version=env.get("python", ""),
        node_version=env.get("node", ""),
        env=env,
    )
    report_path = Path("docs/security-assurance-report.md")
    report_path.write_text(markdown, encoding="utf-8")
    print(f"Security assurance report written -> {report_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="evidence")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")

    p_tm = sub.add_parser("test-manifest", help="build test manifest from JUnit XML")
    p_tm.add_argument(
        "--junit-dir", default="artifacts/tests", help="directory with *.xml JUnit files"
    )
    p_tm.add_argument("--out", default="artifacts/tests/test-manifest.json", help="output path")

    p_cs = sub.add_parser("checksums", help="walk artifacts and write SHA256SUMS + manifest")
    p_cs.add_argument("--dir", default="artifacts", help="root of the artifact tree")

    p_rp = sub.add_parser("report", help="generate security assurance report")
    p_rp.add_argument("--artifacts", default="artifacts", help="artifacts directory")

    args = parser.parse_args()
    if args.command == "test-manifest":
        return cmd_test_manifest(args)
    elif args.command == "checksums":
        return cmd_checksums(args)
    elif args.command == "report":
        return cmd_report(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
