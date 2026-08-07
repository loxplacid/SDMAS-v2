"""CLI end-to-end tests (generate + validate + analyze)."""

from __future__ import annotations

import argparse
import json

from sbom import cli


def _ns(**kw):
    """Build an argparse.Namespace with the given attributes."""
    return argparse.Namespace(**kw)


def test_generate_end_to_end(tmp_path):
    uv = tmp_path / "uv.lock"
    uv.write_text(
        """[[package]]
name = "aiosqlite"
version = "0.22.1"
source = { registry = "https://pypi.org/simple" }
wheels = [
    { url = "https://example.invalid/a.whl", hash = "sha256:abababababababababababababababab" },
]
""",
        encoding="utf-8",
    )
    pl = tmp_path / "package-lock.json"
    pl.write_text(
        json.dumps(
            {
                "lockfileVersion": 3,
                "packages": {
                    "": {"dependencies": {"left-pad": "^1.3.0"}},
                    "node_modules/left-pad": {
                        "version": "1.3.0",
                        "integrity": "sha512-AAAAAAAA",
                        "license": "WTFPL",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "out"
    rc = cli.cmd_generate(
        _ns(
            python_lock=str(uv),
            node_lock=[str(pl)],
            venv=False,
            output_dir=str(out),
            created="0",
        )
    )
    assert rc == 0
    assert (out / "sbom.spdx.json").is_file()
    assert (out / "sbom.cdx.json").is_file()
    assert (out / "python_dependency_inventory.json").is_file()
    assert (out / "node_dependency_inventory.json").is_file()
    for name in (
        "license_summary",
        "duplicate_dependencies",
        "dependency_metrics",
        "dependency_risk_report",
        "warnings",
    ):
        assert (out / f"{name}.json").is_file()

    spdx = json.loads((out / "sbom.spdx.json").read_text(encoding="utf-8"))
    names = {p["name"] for p in spdx["packages"]}
    assert names == {"aiosqlite", "left-pad"}


def test_generate_deterministic_twice(tmp_path):
    uv = tmp_path / "uv.lock"
    uv.write_text(
        """[[package]]
name = "aiosqlite"
version = "0.22.1"
source = { registry = "https://pypi.org/simple" }
""",
        encoding="utf-8",
    )
    out1, out2 = tmp_path / "o1", tmp_path / "o2"
    for out in (out1, out2):
        assert (
            cli.cmd_generate(
                _ns(python_lock=str(uv), node_lock=[], venv=False, output_dir=str(out), created="0")
            )
            == 0
        )
    a = (out1 / "sbom.spdx.json").read_bytes()
    b = (out2 / "sbom.spdx.json").read_bytes()
    assert a == b


def test_node_inventory_discovers_locks_when_flag_omitted(tmp_path, monkeypatch):
    """``node-inventory`` with no --lock must fall back to repo discovery
    instead of crashing on a None arg (argparse action=append has no default)."""
    monkeypatch.setattr(cli, "_find_node_locks", lambda: [tmp_path / "package-lock.json"])
    p = tmp_path / "package-lock.json"
    p.write_text(
        json.dumps({"lockfileVersion": 3, "packages": {"node_modules/x": {"version": "1.0.0"}}}),
        encoding="utf-8",
    )
    out = tmp_path / "out.json"
    rc = cli.cmd_node_inventory(_ns(lock=None, output=str(out)))
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert {p["name"] for p in data["packages"]} == {"x"}


def test_validate_cli(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "sbom.spdx.json").write_text('{"spdxVersion": "SPDX-2.3"}', encoding="utf-8")
    rc = cli.cmd_validate(_ns(dir=str(out), file=[]))
    assert rc == 1  # invalid document must fail


def test_analyze_roundtrip_with_dependencies(tmp_path):
    """analyze must survive packages whose dependencies round-trip through
    the persisted JSON (dependencies rehydrate as Dependency objects, not
    bare dicts — regression for the AttributeError crash)."""
    out = tmp_path / "out"
    out.mkdir()
    (out / "python_dependency_inventory.json").write_text(
        json.dumps(
            {
                "generator": "test",
                "packages": [
                    {
                        "name": "alembic",
                        "version": "1.18.5",
                        "ecosystem": "pypi",
                        "source": "apps/api/uv.lock",
                        "license_expression": None,
                        "purl": "pkg:pypi/alembic@1.18.5",
                        "download_url": None,
                        "checksums": [],
                        "dependencies": [{"name": "aiosqlite", "specifier": ""}],
                        "is_direct": True,
                        "origin": "registry",
                    },
                    {
                        "name": "aiosqlite",
                        "version": "0.22.1",
                        "ecosystem": "pypi",
                        "source": "apps/api/uv.lock",
                        "license_expression": None,
                        "purl": "pkg:pypi/aiosqlite@0.22.1",
                        "download_url": None,
                        "checksums": [],
                        "dependencies": [],
                        "is_direct": False,
                        "origin": "registry",
                    },
                ],
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )
    (out / "node_dependency_inventory.json").write_text(
        json.dumps({"generator": "test", "packages": [], "warnings": []}),
        encoding="utf-8",
    )
    rc = cli.cmd_analyze(_ns(output_dir=str(out)))
    assert rc == 0
    metrics = json.loads((out / "dependency_metrics.json").read_text(encoding="utf-8"))
    assert metrics["dependency_edges"] == 1
