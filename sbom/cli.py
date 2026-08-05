"""SBOM command-line interface.

Usage::

    python -m sbom.cli generate            # full pipeline (defaults to repo paths)
    python -m sbom.cli python-inventory -o <file>.json
    python -m sbom.cli node-inventory -o <file>.json
    python -m sbom.cli analyze --output-dir <dir>
    python -m sbom.cli validate --dir <dir>

All output files are written with sorted keys and 2-space indentation.
The ``created`` timestamp honours ``SOURCE_DATE_EPOCH`` for reproducible
builds (see docs/SBOM_VALIDATION.md).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__
from .analyze import (
    cross_ecosystem_collisions,
    dependency_metrics,
    dependency_risk_report,
    duplicate_dependencies,
    license_summary,
)
from .emit_cyclonedx import build_cyclonedx
from .emit_spdx import build_spdx, created_timestamp
from .graph import resolve_graph
from .inventory import (
    Inventory,
    merge_inventories,
    parse_package_lock,
    parse_requirements,
    parse_uv_lock,
    parse_venv_dist_info,
)
from .models import PYPI, Package
from .validate import validate

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# discovery helpers
# ---------------------------------------------------------------------------


def _find_python_lock() -> Path | None:
    uv = REPO_ROOT / "apps" / "api" / "uv.lock"
    if uv.is_file():
        return uv
    req = REPO_ROOT / "apps" / "api" / "requirements.txt"
    return req if req.is_file() else None


def _find_node_locks() -> list[Path]:
    return sorted((REPO_ROOT / "apps").glob("*/package-lock.json"))


def _find_site_packages() -> Path | None:
    venv = REPO_ROOT / "apps" / "api" / ".venv"
    win = venv / "Lib" / "site-packages"
    if win.is_dir():
        return win
    unix = sorted(venv.glob("lib/python*/site-packages"))
    return unix[0] if unix else None


def _root_component() -> tuple[str, str]:
    """Root component name/version, derived from the API pyproject.toml
    when present (falls back to a constant)."""
    pyproject = REPO_ROOT / "apps" / "api" / "pyproject.toml"
    if pyproject.is_file():
        try:
            import tomllib

            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            project = data.get("project", {}) if isinstance(data, dict) else {}
            name = project.get("name")
            version = project.get("version")
            if isinstance(name, str) and isinstance(version, str) and name and version:
                return name, version
        except Exception:
            pass
    return "SDMAS-v2", "2.0.0"


def _relative_source(source: str) -> str:
    """Normalise a source path for stable, portable output.

    Sources are rewritten to be relative to the repo root (forward slashes)
    so SBOM identifiers that embed the source — CycloneDX bom-refs, the
    inventory ``source`` field — are identical across machines, path case
    and Windows/Linux separators.  Paths outside the repo are kept absolute
    (normalised separators only).
    """
    try:
        # resolve() (realpath) canonicalises the on-disk casing on Windows
        # and symlinks — abspath would preserve the *typed* case, so
        # ``APPS/API/uv.lock`` and ``apps/api/uv.lock`` (the same file on a
        # case-insensitive FS) must produce the same relative source.
        abs_src = str(Path(source).resolve())
        rel = os.path.relpath(abs_src, REPO_ROOT)
    except (ValueError, OSError):
        return source.replace("\\", "/")
    if not rel.startswith(("..", "/", "\\")):
        return rel.replace("\\", "/")
    return abs_src.replace("\\", "/")


def _relativize(packages: list[Package]) -> list[Package]:
    out: list[Package] = []
    for p in packages:
        src = _relative_source(p.source)
        if src == p.source:
            out.append(p)
            continue
        out.append(
            Package(
                name=p.name,
                version=p.version,
                ecosystem=p.ecosystem,
                source=src,
                license_expression=p.license_expression,
                purl=p.purl,
                download_url=p.download_url,
                checksums=p.checksums,
                dependencies=p.dependencies,
                is_direct=p.is_direct,
                origin=p.origin,
            )
        )
    return out


def _exclude_root_project(packages: list[Package]) -> list[Package]:
    """Drop the root project's own lock entry.

    uv.lock records the project itself as a package with an editable/workspace
    source; it is the *subject* of the SBOM, not a dependency component, and
    must not be reported as a supply-chain risk.
    """
    root_name, _ = _root_component()
    root_norm = root_name.lower().replace("_", "-").replace(".", "-")
    return [
        p
        for p in packages
        if not (
            p.ecosystem == PYPI
            and p.name.lower().replace("_", "-").replace(".", "-") == root_norm
            and p.origin in {"editable", "path", "workspace"}
        )
    ]


def _direct_pypi_names(pyproject: Path | None) -> set[str]:
    """Direct dependencies from pyproject.toml [project] tables."""
    if not pyproject or not pyproject.is_file():
        return set()
    try:
        import tomllib

        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except Exception:
        return set()
    names: set[str] = set()
    project = data.get("project", {}) if isinstance(data, dict) else {}
    for table in ("dependencies", "optional-dependencies"):
        deps = project.get(table, {})
        if isinstance(deps, dict):
            for group in deps.values():
                if isinstance(group, list):
                    names.update(_req_names(group))
        elif isinstance(deps, list):
            names.update(_req_names(deps))
    return names


def _req_names(requirements: list) -> set[str]:
    out: set[str] = set()
    for req in requirements:
        if isinstance(req, str):
            name = req.split("[", 1)[0].split(";", 1)[0].strip()
            name = name.replace("==", " ").replace(">=", " ").replace("<=", " ").replace(
                "~=", " "
            ).replace("!=", " ").split()[0] if name else ""
            if name:
                out.add(name.lower().replace("_", "-").replace(".", "-"))
    return out


def _set_direct(packages: list[Package], direct_names: set[str]) -> list[Package]:
    out: list[Package] = []
    for pkg in packages:
        key = pkg.name.lower().replace("_", "-").replace(".", "-")
        if pkg.ecosystem == PYPI and key in direct_names:
            pkg = Package(
                name=pkg.name,
                version=pkg.version,
                ecosystem=pkg.ecosystem,
                source=pkg.source,
                license_expression=pkg.license_expression,
                purl=pkg.purl,
                download_url=pkg.download_url,
                checksums=pkg.checksums,
                dependencies=pkg.dependencies,
                is_direct=True,
                origin=pkg.origin,
            )
        out.append(pkg)
    return out


def _augment_from_venv(packages: list[Package], venv_inv: Inventory) -> tuple[list[Package], list[str]]:
    """Merge license + checksum metadata from installed dist-info into the
    lock-derived packages where name AND version match.  venv-only packages
    (including version-mismatched ones — environment drift) are appended
    with a warning rather than merged across versions."""
    if not venv_inv.packages:
        return packages, venv_inv.warnings
    # key on (ecosystem, normalized name, version): attaching metadata from
    # a *different* installed version to a lock component would forge
    # checksums/licenses for an artifact we never installed
    by_key: dict[tuple[str, str, str], Package] = {}
    for pkg in packages:
        by_key.setdefault((pkg.ecosystem, pkg.name.lower(), pkg.version), pkg)

    merged: list[Package] = []
    appended: list[Package] = []
    matched: set[tuple[str, str, str]] = set()
    for venv_pkg in venv_inv.packages:
        target = by_key.get((PYPI, venv_pkg.name.lower(), venv_pkg.version))
        if target is None:
            appended.append(venv_pkg)
            continue
        matched.add((PYPI, venv_pkg.name.lower(), venv_pkg.version))
        if target.license_expression is None or not target.checksums:
            merged.append(
                Package(
                    name=target.name,
                    version=target.version,
                    ecosystem=target.ecosystem,
                    source=f"{target.source} (+{venv_pkg.source})",
                    license_expression=target.license_expression
                    or venv_pkg.license_expression,
                    purl=target.purl,
                    download_url=target.download_url,
                    checksums=target.checksums or venv_pkg.checksums,
                    dependencies=target.dependencies,
                    is_direct=target.is_direct,
                    origin=target.origin,
                )
            )
        else:
            merged.append(target)
    # retain lock-derived packages that are NOT installed in the venv — the
    # venv is a partial snapshot and must never silently drop lock packages
    retained = [pkg for key, pkg in by_key.items() if key not in matched]
    warnings = list(venv_inv.warnings)
    if appended:
        warnings.append(
            f"venv contains {len(appended)} package(s) absent from uv.lock "
            "(partial environment?)"
        )
    return sorted(
        retained + merged + appended, key=lambda p: (p.ecosystem, p.name, p.version)
    ), warnings


# ---------------------------------------------------------------------------
# subcommands
# ---------------------------------------------------------------------------


def cmd_python_inventory(args: argparse.Namespace) -> int:
    lock = Path(args.lock) if args.lock else _find_python_lock()
    if not lock:
        print("error: no Python lock file found", file=sys.stderr)
        return 1
    inv = parse_uv_lock(lock) if lock.name == "uv.lock" else parse_requirements(lock)
    direct = _direct_pypi_names(REPO_ROOT / "apps" / "api" / "pyproject.toml")
    inv.packages = _set_direct(inv.packages, direct)
    inv.packages = _exclude_root_project(inv.packages)
    inv.packages = _relativize(inv.packages)
    if args.venv:
        site = _find_site_packages()
        if site:
            venv_inv = parse_venv_dist_info(site)
            inv.packages, venv_warnings = _augment_from_venv(inv.packages, venv_inv)
            inv.warnings.extend(venv_warnings)
    inv.dedupe()
    _write_json(_inventory_to_dict(inv), Path(args.output))
    print(f"wrote {args.output} ({len(inv.packages)} packages, {len(inv.warnings)} warnings)")
    return 0


def cmd_node_inventory(args: argparse.Namespace) -> int:
    locks = [Path(l) for l in args.lock] or _find_node_locks()
    if not locks:
        print("error: no package-lock.json files found", file=sys.stderr)
        return 1
    invs = [parse_package_lock(l) for l in locks]
    packages, warnings = merge_inventories(*invs)
    inv = Inventory(packages=_relativize(packages), warnings=warnings)
    _write_json(_inventory_to_dict(inv), Path(args.output))
    print(f"wrote {args.output} ({len(packages)} packages, {len(warnings)} warnings)")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    python_lock = Path(args.python_lock) if args.python_lock else _find_python_lock()
    if python_lock is None:
        print("error: no Python lock file found (use --python-lock)", file=sys.stderr)
        return 1
    python_inv = (
        parse_uv_lock(python_lock)
        if python_lock.name == "uv.lock"
        else parse_requirements(python_lock)
    )
    direct = _direct_pypi_names(REPO_ROOT / "apps" / "api" / "pyproject.toml")
    python_inv.packages = _set_direct(python_inv.packages, direct)
    python_inv.packages = _exclude_root_project(python_inv.packages)
    python_inv.packages = _relativize(python_inv.packages)
    if args.venv:
        site = _find_site_packages()
        if site:
            venv_inv = parse_venv_dist_info(site)
            python_inv.packages, venv_warnings = _augment_from_venv(
                python_inv.packages, venv_inv
            )
            python_inv.warnings.extend(venv_warnings)
    python_inv.dedupe()

    node_locks = [Path(l) for l in args.node_lock] if args.node_lock else _find_node_locks()
    node_invs = [parse_package_lock(l) for l in node_locks]

    packages, warnings = merge_inventories(python_inv, *node_invs)
    # single normalization point: source paths must be repo-relative in the
    # merged list (bom-refs embed them) regardless of how each sub-inventory
    # was produced
    packages = _relativize(packages)
    graph = resolve_graph(packages)

    _write_json(
        _inventory_to_dict(python_inv), output_dir / "python_dependency_inventory.json"
    )
    node_merged = Inventory(
        packages=[p for p in packages if p.ecosystem != PYPI], warnings=[]
    )
    _write_json(
        _inventory_to_dict(node_merged), output_dir / "node_dependency_inventory.json"
    )

    # analysis artefacts
    _write_json(license_summary(packages), output_dir / "license_summary.json")
    _write_json(
        {
            "duplicates": duplicate_dependencies(packages),
            "cross_ecosystem_collisions": cross_ecosystem_collisions(packages),
        },
        output_dir / "duplicate_dependencies.json",
    )
    _write_json(dependency_metrics(packages, graph), output_dir / "dependency_metrics.json")
    _write_json(
        dependency_risk_report(packages, graph, warnings),
        output_dir / "dependency_risk_report.json",
    )
    _write_json({"warnings": warnings}, output_dir / "warnings.json")

    # SBOM documents
    created = created_timestamp(args.created)
    root_name, root_version = _root_component()
    spdx_doc = build_spdx(packages, root_name, root_version, graph, created)
    cdx_doc = build_cyclonedx(packages, root_name, root_version, graph, created)
    _write_json(spdx_doc, output_dir / "sbom.spdx.json")
    _write_json(cdx_doc, output_dir / "sbom.cdx.json")

    errors = validate([("spdx", spdx_doc), ("cyclonedx", cdx_doc)])
    print(
        f"wrote {len(packages)} packages to {output_dir} "
        f"({len(warnings)} warnings, {len(errors)} validation errors)"
    )
    for e in errors:
        print(f"  VALIDATION ERROR: {e}", file=sys.stderr)
    return 1 if errors else 0


def cmd_analyze(args: argparse.Namespace) -> int:
    """Re-run analysis from previously written inventories (CI use)."""
    output_dir = Path(args.output_dir)
    inv = _read_inventory(output_dir / "python_dependency_inventory.json")
    inv.packages += _read_inventory(output_dir / "node_dependency_inventory.json").packages
    packages = sorted(inv.packages, key=lambda p: (p.ecosystem, p.name, p.version))
    graph = resolve_graph(packages)
    _write_json(license_summary(packages), output_dir / "license_summary.json")
    _write_json(
        {
            "duplicates": duplicate_dependencies(packages),
            "cross_ecosystem_collisions": cross_ecosystem_collisions(packages),
        },
        output_dir / "duplicate_dependencies.json",
    )
    _write_json(dependency_metrics(packages, graph), output_dir / "dependency_metrics.json")
    _write_json(
        dependency_risk_report(packages, graph, inv.warnings),
        output_dir / "dependency_risk_report.json",
    )
    print(f"analyzed {len(packages)} packages -> {output_dir}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    files: list[Path] = []
    if args.dir:
        files = sorted(Path(args.dir).glob("sbom.*.json"))
    files += [Path(f) for f in args.file]
    if not files:
        print("error: no documents to validate", file=sys.stderr)
        return 1

    documents: list[tuple[str, dict]] = []
    for f in files:
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  ERROR {f}: unreadable ({exc})", file=sys.stderr)
            return 1
        kind = "spdx" if f.name.startswith("sbom.spdx") else (
            "cyclonedx" if f.name.startswith("sbom.cdx") else None
        )
        if kind is None:
            continue
        documents.append((kind, doc))

    errors = validate(documents)
    for e in errors:
        print(f"  ERROR: {e}", file=sys.stderr)
    print(f"validated {len(documents)} document(s): {len(errors)} error(s)")
    return 1 if errors else 0


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _inventory_to_dict(inv: Inventory) -> dict:
    return {
        "generator": f"sdmas-sbom-{__version__}",
        "packages": [_pkg_to_dict(p) for p in inv.packages],
        "warnings": inv.warnings,
    }


def _pkg_to_dict(pkg: Package) -> dict:
    return {
        "name": pkg.name,
        "version": pkg.version,
        "ecosystem": pkg.ecosystem,
        "source": pkg.source,
        "license_expression": pkg.license_expression,
        "purl": pkg.purl,
        "download_url": pkg.download_url,
        "checksums": [[a, h] for a, h in pkg.checksums],
        "dependencies": [{"name": d.name, "specifier": d.specifier} for d in pkg.dependencies],
        "is_direct": pkg.is_direct,
        "origin": pkg.origin,
    }


def _pkg_from_dict(d: dict) -> Package:
    return Package(
        name=d["name"],
        version=d["version"],
        ecosystem=d["ecosystem"],
        source=d["source"],
        license_expression=d.get("license_expression"),
        purl=d.get("purl"),
        download_url=d.get("download_url"),
        checksums=tuple((a, h) for a, h in d.get("checksums") or []),
        dependencies=tuple(
            {"name": x["name"], "specifier": x.get("specifier", "")}
            for x in d.get("dependencies") or []
        ),
        is_direct=d.get("is_direct", True),
        origin=d.get("origin"),
    )


def _read_inventory(path: Path) -> Inventory:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Inventory()
    return Inventory(
        packages=[_pkg_from_dict(d) for d in data.get("packages", [])],
        warnings=data.get("warnings", []),
    )


def _write_json(obj: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sbom", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_py = sub.add_parser("python-inventory", help="extract the Python dependency inventory")
    p_py.add_argument("--lock", help="path to uv.lock or requirements.txt")
    p_py.add_argument("--venv", action="store_true", help="augment from the installed venv")
    p_py.add_argument("-o", "--output", default="python_dependency_inventory.json")
    p_py.set_defaults(func=cmd_python_inventory)

    p_node = sub.add_parser("node-inventory", help="extract the Node dependency inventory")
    p_node.add_argument("--lock", action="append", help="path to package-lock.json (repeatable)")
    p_node.add_argument("-o", "--output", default="node_dependency_inventory.json")
    p_node.set_defaults(func=cmd_node_inventory)

    p_gen = sub.add_parser("generate", help="run the full SBOM pipeline")
    p_gen.add_argument("--python-lock", help="uv.lock / requirements.txt (default: repo default)")
    p_gen.add_argument("--node-lock", action="append", help="package-lock.json (repeatable)")
    p_gen.add_argument("--venv", action="store_true", help="augment Python inventory from venv")
    p_gen.add_argument("--output-dir", default=str(REPO_ROOT / "sbom" / "output"))
    p_gen.add_argument(
        "--created",
        default=os.environ.get("SOURCE_DATE_EPOCH"),
        help="creation timestamp: Unix epoch seconds (SOURCE_DATE_EPOCH)",
    )
    p_gen.set_defaults(func=cmd_generate)

    p_an = sub.add_parser("analyze", help="re-run analysis from stored inventories")
    p_an.add_argument("--output-dir", default=str(REPO_ROOT / "sbom" / "output"))
    p_an.set_defaults(func=cmd_analyze)

    p_val = sub.add_parser("validate", help="validate generated SBOM documents")
    p_val.add_argument("--dir", help="directory containing sbom.*.json files")
    p_val.add_argument("--file", action="append", default=[], help="explicit document (repeatable)")
    p_val.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
