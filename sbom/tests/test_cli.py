"""CLI end-to-end tests (generate + validate + analyze)."""

from __future__ import annotations

import argparse
import json

from sbom import cli
from sbom.inventory import parse_uv_lock


def _ns(**kw):
    return argparse.Namespace(**kw)


def test_generate_end_to_end(tmp_path):
    uv = tmp_path / "uv.lock"
    uv.write_text(
        """[[package]]
name = "aiosqlite"
version = "0.22.1"
source = { registry = "https://pypi.org/simple" }
wheels = [{ url = "https://example.invalid/a.whl", hash = "sha256:abababababababababababababababababababababababababababababababab" }]
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
    for name in ("license_summary", "duplicate_dependencies", "dependency_metrics",
                 "dependency_risk_report", "warnings"):
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
        assert cli.cmd_generate(
            _ns(python_lock=str(uv), node_lock=[], venv=False,
                output_dir=str(out), created="0")
        ) == 0
    a = (out1 / "sbom.spdx.json").read_bytes()
    b = (out2 / "sbom.spdx.json").read_bytes()
    assert a == b


def test_validate_cli(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "sbom.spdx.json").write_text('{"spdxVersion": "SPDX-2.3"}', encoding="utf-8")
    rc = cli.cmd_validate(_ns(dir=str(out), file=[]))
    assert rc == 1  # invalid document must fail
