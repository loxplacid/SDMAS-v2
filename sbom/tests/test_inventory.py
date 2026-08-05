"""Parser tests: uv.lock, requirements.txt, package-lock v2/v3, dist-info."""

from __future__ import annotations

import json
import tomllib

import pytest

from sbom.inventory import (
    Inventory,
    merge_inventories,
    parse_package_lock,
    parse_requirements,
    parse_uv_lock,
    parse_venv_dist_info,
)
from sbom.models import NPM, PYPI


UV_LOCK = """\
version = 1
requires-python = ">=3.11"

[[package]]
name = "aiosqlite"
version = "0.22.1"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://example.invalid/aiosqlite-0.22.1.tar.gz", hash = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }
wheels = [
    { url = "https://example.invalid/aiosqlite-0.22.1-py3-none-any.whl", hash = "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" },
]

[[package]]
name = "alembic"
version = "1.18.5"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "mako" },
    { name = "sqlalchemy", version = ">=1.4" },
]

[[package]]
name = "my-local-tool"
version = "0.1.0"
source = { editable = "." }
dependencies = [
    { name = "aiosqlite" },
]
"""


def _write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


def test_parse_uv_lock_basic(tmp_path):
    p = _write(tmp_path / "uv.lock", UV_LOCK)
    inv = parse_uv_lock(p)
    assert len(inv.packages) == 3
    names = {x.name for x in inv.packages}
    assert names == {"aiosqlite", "alembic", "my-local-tool"}
    aio = next(x for x in inv.packages if x.name == "aiosqlite")
    assert aio.checksums  # sdist + wheel hashes
    assert aio.purl == "pkg:pypi/aiosqlite@0.22.1"
    alembic = next(x for x in inv.packages if x.name == "alembic")
    assert {d.name for d in alembic.dependencies} == {"mako", "sqlalchemy"}
    assert alembic.dependencies[1].specifier == ">=1.4"
    tool = next(x for x in inv.packages if x.name == "my-local-tool")
    assert tool.origin == "editable"
    assert not inv.warnings


def test_parse_uv_lock_corrupt(tmp_path):
    p = _write(tmp_path / "uv.lock", "not toml [[[")
    inv = parse_uv_lock(p)
    assert inv.packages == []
    assert len(inv.warnings) == 1


def test_parse_uv_lock_malformed_entry(tmp_path):
    p = _write(tmp_path / "uv.lock", UV_LOCK.replace('version = "0.22.1"', 'version = 42'))
    inv = parse_uv_lock(p)
    assert len(inv.packages) == 2
    assert any("missing name/version" in w for w in inv.warnings)


def test_parse_requirements_basic(tmp_path):
    p = _write(
        tmp_path / "requirements.txt",
        "# comment\nfastapi==0.115.0\nsqlalchemy[asyncio]>=2.0,<3 ; python_version >= '3.11'\n"
        "-r other.txt\n-e .#egg=editable-thing\n--index-url https://example.invalid\n",
    )
    inv = parse_requirements(p)
    pkgs = {x.name: x for x in inv.packages}
    assert pkgs["fastapi"].version == "0.115.0"
    assert "sqlalchemy" in pkgs  # extras + marker stripped
    assert pkgs["editable-thing"].origin == "editable"
    assert any("recursive includes" in w for w in inv.warnings)


NPM_V3 = {
    "lockfileVersion": 3,
    "packages": {
        "": {"name": "app", "version": "1.0.0", "dependencies": {"left-pad": "^1.3.0"}},
        "node_modules/left-pad": {
            "version": "1.3.0",
            "resolved": "https://registry.npmjs.org/left-pad/-/left-pad-1.3.0.tgz",
            "integrity": "sha512-c3RhY2tvdmVyZmxvdy5jb20=",
            "license": "WTFPL",
        },
        "node_modules/@scope/thing": {
            "version": "2.0.0",
            "resolved": "https://registry.npmjs.org/@scope/thing/-/thing-2.0.0.tgz",
            "integrity": "sha512-9aBc2o1gZ2b0cGgZgXJkGjY2qW9FJgGK8lG8z3D/TzF3H2WW5xKfxbE0wKk3k8VvJjE5GJFl1tO3SHNfD9tC3g==",
        },
    },
}


def test_parse_package_lock_v3(tmp_path):
    p = _write(tmp_path / "package-lock.json", json.dumps(NPM_V3))
    inv = parse_package_lock(p)
    assert len(inv.packages) == 2
    lp = next(x for x in inv.packages if x.name == "left-pad")
    assert lp.version == "1.3.0"
    assert lp.is_direct is True
    assert lp.checksums and lp.checksums[0][0] == "SHA512"
    assert lp.purl == "pkg:npm/left-pad@1.3.0"
    scoped = next(x for x in inv.packages if x.name == "@scope/thing")
    # purl canonical form: %40 for '@', literal '/' between namespace and name
    assert scoped.purl == "pkg:npm/%40scope/thing@2.0.0"
    assert scoped.is_direct is False


NPM_V2 = {
    "lockfileVersion": 1,
    "dependencies": {
        "a": {
            "version": "1.0.0",
            "license": "MIT",
            "dependencies": {
                "b": {"version": "2.0.0", "license": "ISC"},
            },
        },
        "c": {"version": "3.0.0", "integrity": "sha1-AAAA"},
    },
}


def test_parse_package_lock_v2(tmp_path):
    p = _write(tmp_path / "package-lock.json", json.dumps(NPM_V2))
    inv = parse_package_lock(p)
    assert {x.name for x in inv.packages} == {"a", "b", "c"}
    a = next(x for x in inv.packages if x.name == "a")
    assert a.is_direct is True
    assert {d.name for d in a.dependencies} == {"b"}
    b = next(x for x in inv.packages if x.name == "b")
    assert b.is_direct is False


def test_parse_package_lock_corrupt(tmp_path):
    p = _write(tmp_path / "package-lock.json", "{not json")
    inv = parse_package_lock(p)
    assert inv.packages == []
    assert len(inv.warnings) == 1


def test_parse_venv_dist_info(tmp_path):
    site = tmp_path / "site-packages"
    dist = site / "requests-2.32.0.dist-info"
    dist.mkdir(parents=True)
    meta = "Metadata-Version: 2.1\nName: requests\nVersion: 2.32.0\n"
    meta += "License: Apache-2.0\nClassifier: License :: OSI Approved :: Apache Software License\n"
    (dist / "METADATA").write_text(meta, encoding="utf-8")
    (dist / "RECORD").write_text("requests/__init__.py,sha256=abcd,123\n", encoding="utf-8")
    inv = parse_venv_dist_info(site)
    assert len(inv.packages) == 1
    pkg = inv.packages[0]
    assert pkg.name == "requests" and pkg.version == "2.32.0"
    assert pkg.license_expression == "Apache-2.0"
    assert pkg.checksums and pkg.checksums[0][0] == "SHA256"
    assert not inv.warnings


def test_parse_venv_dist_info_corrupt_record(tmp_path):
    site = tmp_path / "site-packages"
    dist = site / "foo-1.0.dist-info"
    dist.mkdir(parents=True)
    (dist / "METADATA").write_text("Name: foo\nVersion: 1.0\n", encoding="utf-8")
    (dist / "RECORD").write_text("garbage-with-one-field\n", encoding="utf-8")
    inv = parse_venv_dist_info(site)
    assert len(inv.packages) == 1
    assert any("RECORD corrupt" in w for w in inv.warnings)


def test_oversized_input_skipped(tmp_path, monkeypatch):
    from sbom import inventory as inv_mod

    monkeypatch.setattr(inv_mod, "MAX_INPUT_BYTES", 100)
    p = tmp_path / "uv.lock"
    p.write_text("version = 1\n" * 50, encoding="utf-8")
    inv = parse_uv_lock(p)
    assert inv.packages == []
    assert any("exceeds" in w for w in inv.warnings)


def test_merge_inventories_dedupe(tmp_path):
    uv = _write(tmp_path / "uv.lock", UV_LOCK)
    a = parse_uv_lock(uv)
    a.dedupe()
    inv = Inventory(packages=list(a.packages))
    merged, warnings = merge_inventories(a, inv)
    assert len(merged) == len(a.packages)
    assert warnings == []
