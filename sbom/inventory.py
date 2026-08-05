"""Dependency inventory extraction from lock files and installed dist-info.

Inputs supported:

* ``uv.lock`` (TOML) — primary Python source of truth.
* ``requirements.txt`` — fallback for legacy installs.
* ``package-lock.json`` (npm lockfile v2 and v3) — Node.js.
* optional ``*.dist-info`` (``METADATA`` / ``RECORD``) augmentation from an
  installed virtualenv — adds license metadata and checksums that lock files
  do not carry.

Every parser is defensive by design: malformed or corrupt entries are skipped
with a warning rather than aborting the inventory, and the warnings are
surfaced in the report so consumers can judge data quality.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .models import Dependency, NPM, PYPI, Package, norm_npm_name, norm_pypi_name

# ---------------------------------------------------------------------------
# Inventory container
# ---------------------------------------------------------------------------


@dataclass
class Inventory:
    """A parsed dependency inventory plus any parse warnings."""

    packages: list[Package] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def dedupe(self) -> None:
        """Merge identical (ecosystem, name, version, source) entries and
        keep a stable, sorted order."""
        seen: set[tuple[str, str, str, str]] = set()
        unique: list[Package] = []
        for pkg in sorted(
            self.packages, key=lambda p: (p.ecosystem, p.name, p.version, p.source)
        ):
            k = (pkg.ecosystem, pkg.name, pkg.version, pkg.source)
            if k in seen:
                continue
            seen.add(k)
            unique.append(pkg)
        self.packages = unique


# ---------------------------------------------------------------------------
# Python: uv.lock
# ---------------------------------------------------------------------------


#: Upper bound on a single input file we will load into memory.  A lock file
#: larger than this is treated as hostile/corrupt (resource-exhaustion guard)
#: and skipped with a warning instead of exhausting the process.
MAX_INPUT_BYTES = 200 * 1024 * 1024


def _read_bounded(path: Path, label: str, inv: Inventory) -> str | None:
    """Read a text input file, refusing files above MAX_INPUT_BYTES."""
    try:
        size = path.stat().st_size
    except OSError as exc:
        inv.warnings.append(f"{label} '{path}' unreadable: {exc}")
        return None
    if size > MAX_INPUT_BYTES:
        inv.warnings.append(
            f"{label} '{path}' is {size} bytes — exceeds {MAX_INPUT_BYTES} "
            "limit; skipped (possible resource-exhaustion attack)"
        )
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        # UnicodeDecodeError: a lock file with invalid UTF-8 is corrupt — warn
        # and skip (defensive-parsing contract: never crash on bad input)
        inv.warnings.append(f"{label} '{path}' unreadable: {exc}")
        return None


def parse_uv_lock(path: str | Path) -> Inventory:
    """Parse a uv.lock (TOML) into a package inventory.

    ``source`` origins are classified as registry / git / editable / path /
    workspace.  Distribution hashes (sdist + wheels) become package
    checksums.  uv.lock does not record license metadata, so
    ``license_expression`` stays ``None`` here (augmented later from
    dist-info when available).
    """
    inv = Inventory()
    p = Path(path)
    text = _read_bounded(p, "uv.lock", inv)
    if text is None:
        return inv
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        inv.warnings.append(f"uv.lock '{p}' unreadable: {exc}")
        return inv
    if not isinstance(data, dict) or "package" not in data:
        inv.warnings.append(f"uv.lock '{p}' has no [[package]] table")
        return inv

    for entry in data.get("package", []):
        if not isinstance(entry, dict):
            inv.warnings.append(f"uv.lock '{p}': non-table [[package]] entry skipped")
            continue
        name = entry.get("name")
        version = entry.get("version")
        if not isinstance(name, str) or not isinstance(version, str) or not version:
            inv.warnings.append(
                f"uv.lock '{p}': package entry missing name/version: {str(entry)[:120]!r}"
            )
            continue

        origin = None
        src = entry.get("source")
        if isinstance(src, dict):
            if src.get("git"):
                origin = "git"
            elif src.get("editable"):
                origin = "editable"
            elif src.get("path"):
                origin = "path"
            elif src.get("workspace"):
                origin = "workspace"
            elif src.get("registry"):
                origin = "registry"

        deps: list[Dependency] = []
        for d in entry.get("dependencies", []) or []:
            if isinstance(d, dict) and isinstance(d.get("name"), str):
                spec = d.get("version")
                deps.append(
                    Dependency(name=d["name"], specifier=spec if isinstance(spec, str) else "")
                )

        checksums: list[tuple[str, str]] = []
        sdist = entry.get("sdist")
        if isinstance(sdist, dict):
            _add_hash(checksums, sdist.get("hash"), p, name)
        wheels = entry.get("wheels", []) or []
        for wheel in wheels:
            if isinstance(wheel, dict):
                _add_hash(checksums, wheel.get("hash"), p, name)

        # prefer the actual artifact URL the lock file resolved (SPDX
        # downloadLocation should point at the download, not a project page)
        download_url = None
        if isinstance(sdist, dict) and isinstance(sdist.get("url"), str):
            download_url = sdist["url"]
        elif wheels and isinstance(wheels[0], dict) and isinstance(wheels[0].get("url"), str):
            download_url = wheels[0]["url"]
        if download_url is None:
            download_url = _pypi_download_url(name, version)

        inv.packages.append(
            Package(
                name=name,
                version=version,
                ecosystem=PYPI,
                source=str(p),
                purl=f"pkg:pypi/{name.lower()}@{version}",
                download_url=download_url,
                checksums=tuple(checksums),
                dependencies=tuple(deps),
                is_direct=False,  # corrected below from requirements.txt
                origin=origin,
            )
        )
    return inv


def _add_hash(
    checksums: list[tuple[str, str]], raw: object, lock: Path, name: str
) -> None:
    """Parse a uv hash string ('sha256:<hex>') into (algorithm, hexdigest)."""
    if not isinstance(raw, str) or ":" not in raw:
        return
    algo, _, digest = raw.partition(":")
    if algo.lower() in {"sha256", "sha384", "sha512", "sha1", "md5"} and re.fullmatch(
        r"[0-9a-fA-F]+", digest
    ):
        checksums.append((algo.upper(), digest.lower()))
    # unrecognised hash forms are dropped silently — never fatal


def _pypi_download_url(name: str, version: str) -> str:
    return f"https://pypi.org/project/{name}/{version}/"


# ---------------------------------------------------------------------------
# Python: requirements.txt (fallback)
# ---------------------------------------------------------------------------


def _strip_comment(line: str) -> str:
    """Remove a trailing comment, honouring URL/egg fragments.

    A ``#`` only starts a comment when it begins the line or is preceded by
    whitespace.  A bare ``#`` immediately after a token is *not* a comment
    (e.g. ``-e .#egg=name`` or ``git+https://...#egg=name``), so the legacy
    ``#egg=`` editable syntax survives.
    """
    for i, ch in enumerate(line):
        if ch == "#" and (i == 0 or line[i - 1].isspace()):
            return line[:i]
    return line


def parse_requirements(path: str | Path) -> Inventory:
    """Best-effort requirements.txt parser.

    Handles comments, inline ``#`` comments, extras, environment markers
    (``; python_version < ...``) and simple version specifiers.  ``-r`` /
    ``-c`` includes are *not* followed — a warning is recorded instead.
    """
    inv = Inventory()
    p = Path(path)
    text = _read_bounded(p, "requirements.txt", inv)
    if text is None:
        return inv
    lines = text.splitlines()

    for lineno, raw in enumerate(lines, start=1):
        line = _strip_comment(raw).strip()
        if not line:
            continue
        if line.startswith(("-r", "-c", "--requirement", "--constraint")):
            parts = line.split()
            if len(parts) < 2:
                inv.warnings.append(
                    f"requirements.txt '{p}':{lineno} '{line}' is missing a "
                    "filename (recursive includes are not resolved)"
                )
                continue
            inv.warnings.append(
                f"requirements.txt '{p}':{lineno} includes '{parts[1]}' "
                "(recursive includes are not resolved)"
            )
            continue
        if line.startswith(("-e ", "--editable")):
            spec = line.split(" ", 1)[1] if " " in line else line
            egg = spec.split("#egg=")[-1]
            egg_name = Path(egg).name if egg else ""
            if not egg_name or egg_name in {".", ".."}:
                # no usable #egg= fragment (e.g. plain '-e .'): cannot name it
                inv.warnings.append(
                    f"requirements.txt '{p}':{lineno} editable '{spec}' has no "
                    "#egg= name — recorded as 'editable'"
                )
                egg_name = "editable"
            inv.packages.append(
                Package(
                    name=egg_name,
                    version="",
                    ecosystem=PYPI,
                    source=str(p),
                    origin="editable",
                )
            )
            continue
        if line.startswith("-"):
            continue  # other options (--index-url etc.)

        req = line.split(";")[0].strip()  # drop environment markers
        req = req.split("[")[0].strip()  # drop extras
        # PEP 508 direct references: 'name @ https://…/wheel' (no '==').
        # The name is known; the version cannot be resolved from the URL
        # alone, so the package is recorded version-less with a warning.
        if " @ " in req:
            pep_name, _, pep_url = req.partition(" @ ")
            pep_name = pep_name.strip()
            if pep_name and pep_url.startswith(("http://", "https://", "git+", "file:")):
                inv.warnings.append(
                    f"requirements.txt '{p}':{lineno} direct reference "
                    f"'{req}' — version not resolved from URL"
                )
                inv.packages.append(
                    Package(
                        name=pep_name,
                        version="",
                        ecosystem=PYPI,
                        source=str(p),
                        origin="direct-url",
                    )
                )
                continue
        name, _, spec = req.partition("==")
        if not name or name.startswith(("http://", "https://", "git+")):
            if name.startswith(("http", "git+")):
                inv.warnings.append(
                    f"requirements.txt '{p}':{lineno} direct-URL requirement "
                    f"'{req}' is not resolved to a name/version"
                )
            else:
                inv.warnings.append(
                    f"requirements.txt '{p}':{lineno} unparsable line '{req}'"
                )
            continue
        spec = spec.strip()
        # drop pip inline-hash options: 'name==1.0 --hash=sha256:…'
        if " --" in spec:
            spec = spec.split(" --")[0].strip()
        inv.packages.append(
            Package(
                name=name.strip(),
                version=spec or "",
                ecosystem=PYPI,
                source=str(p),
                purl=(
                    f"pkg:pypi/{norm_pypi_name(name)}@{spec}"
                    if spec
                    else f"pkg:pypi/{norm_pypi_name(name)}"
                ),
                download_url=_pypi_download_url(name.strip(), spec or "unknown"),
            )
        )
    return inv


# ---------------------------------------------------------------------------
# Node: package-lock.json (npm v2 and v3)
# ---------------------------------------------------------------------------


def parse_package_lock(path: str | Path) -> Inventory:
    """Parse an npm package-lock.json (lockfileVersion 1/2/3).

    v3 entries are keyed by install path (``node_modules/…``); v1/v2 use the
    nested ``dependencies`` tree.  Dependency edges are taken from each
    entry's ``dependencies`` map when present; npm hoisting means most v3
    edges are only recoverable from the root entry, so many transitive
    packages appear edge-less (reported as ``is_direct=False`` orphans by
    the analyser).
    """
    inv = Inventory()
    p = Path(path)
    text = _read_bounded(p, "package-lock.json", inv)
    if text is None:
        return inv
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        inv.warnings.append(f"package-lock.json '{p}' unreadable: {exc}")
        return inv
    if not isinstance(data, dict):
        inv.warnings.append(f"package-lock.json '{p}' is not a JSON object")
        return inv

    lockfile_version = data.get("lockfileVersion")
    if isinstance(lockfile_version, int) and lockfile_version >= 3 and isinstance(
        data.get("packages"), dict
    ):
        _parse_v3(inv, p, data["packages"])
    elif isinstance(data.get("dependencies"), dict):
        _parse_v2(inv, p, data["dependencies"], direct=True, depth=0)
    else:
        inv.warnings.append(
            f"package-lock.json '{p}': neither 'packages' (v3) nor "
            "'dependencies' (v2) present"
        )
    return inv


def _parse_v3(inv: Inventory, lock: Path, packages: dict) -> None:
    root = packages.get("") if isinstance(packages.get(""), dict) else {}
    root_deps = root.get("dependencies") if isinstance(root.get("dependencies"), dict) else {}
    # direct packages are the *names* declared by the root entry, not the
    # node_modules/ install paths
    direct_names = {str(k) for k in root_deps}
    for pkg_path, meta in packages.items():
        if pkg_path == "" or not isinstance(meta, dict):
            continue
        name = _name_from_lock_path(pkg_path) or meta.get("name")
        version = meta.get("version")
        if not isinstance(name, str) or not name:
            inv.warnings.append(
                f"package-lock.json '{lock}': entry '{pkg_path}' has no resolvable name"
            )
            continue
        if not isinstance(version, str) or not version:
            inv.warnings.append(
                f"package-lock.json '{lock}': entry '{pkg_path}' has no version"
            )
            version = ""

        # NOTE: npm v3 locks do not record per-package dependency edges for
        # hoisted packages; edges below come only from explicit nested
        # ``dependencies`` maps.  The root entry's direct-dependency map is
        # intentionally NOT turned into edges (see docs/SBOM_VALIDATION.md).
        deps: list[Dependency] = []
        dep_map = meta.get("dependencies")
        if dep_map is not None and not isinstance(dep_map, dict):
            inv.warnings.append(
                f"package-lock.json '{lock}': entry '{pkg_path}' has a "
                f"non-object 'dependencies' value ({type(dep_map).__name__})"
            )
        elif isinstance(dep_map, dict):
            for dep_name, dep_spec in dep_map.items():
                if isinstance(dep_spec, str):
                    deps.append(Dependency(name=dep_name, specifier=dep_spec))
                elif dep_spec is None:
                    deps.append(Dependency(name=dep_name))

        license_expr = meta.get("license")
        if isinstance(license_expr, dict):  # npm legacy {type, url}
            license_expr = license_expr.get("type")
        if not isinstance(license_expr, str) or not license_expr:
            license_expr = None

        resolved = meta.get("resolved")
        checksums: list[tuple[str, str]] = []
        integrity = meta.get("integrity")
        _add_integrity(checksums, integrity, lock, name)

        inv.packages.append(
            Package(
                name=name,
                version=version,
                ecosystem=NPM,
                source=str(lock),
                license_expression=license_expr,
                purl=_npm_purl(name, version),
                download_url=resolved if isinstance(resolved, str) else None,
                checksums=tuple(checksums),
                dependencies=tuple(deps),
                is_direct=name in direct_names,
                origin="registry" if isinstance(resolved, str) else "unknown",
            )
        )


def _parse_v2(
    inv: Inventory,
    lock: Path,
    deps: dict,
    direct: bool,
    depth: int,
) -> None:
    if depth > 50:  # belt-and-braces guard against corrupt cyclic trees
        inv.warnings.append(f"package-lock.json '{lock}': dependency tree too deep")
        return
    for name, meta in deps.items():
        if not isinstance(meta, dict):
            inv.warnings.append(
                f"package-lock.json '{lock}': malformed dependency '{name}'"
            )
            continue
        version = meta.get("version")
        license_expr = meta.get("license")
        if isinstance(license_expr, dict):
            license_expr = license_expr.get("type")
        if not isinstance(license_expr, str) or not license_expr:
            license_expr = None
        resolved = meta.get("resolved")
        checksums: list[tuple[str, str]] = []
        _add_integrity(checksums, meta.get("integrity"), lock, name)

        nested: list[Dependency] = []
        if isinstance(meta.get("dependencies"), dict):
            nested = [
                Dependency(name=child, specifier="")
                for child in meta["dependencies"]
            ]

        inv.packages.append(
            Package(
                name=name,
                version=version if isinstance(version, str) else "",
                ecosystem=NPM,
                source=str(lock),
                license_expression=license_expr,
                purl=_npm_purl(name, version if isinstance(version, str) else ""),
                download_url=resolved if isinstance(resolved, str) else None,
                checksums=tuple(checksums),
                dependencies=tuple(nested),
                is_direct=direct,
                origin="registry" if isinstance(resolved, str) else "unknown",
            )
        )
        if isinstance(meta.get("dependencies"), dict):
            _parse_v2(inv, lock, meta["dependencies"], direct=False, depth=depth + 1)


def _name_from_lock_path(pkg_path: str) -> str | None:
    """Derive a package name from a v3 lock path.

    ``node_modules/foo`` -> ``foo``; ``node_modules/@scope/bar`` ->
    ``@scope/bar``; nested ``node_modules/a/node_modules/b`` -> ``b``.
    """
    idx = pkg_path.rfind("node_modules/")
    if idx < 0:
        return None
    seg = pkg_path[idx + len("node_modules/") :]
    if not seg:
        return None
    if seg.startswith("@"):
        parts = seg.split("/")
        return "/".join(parts[:2]) if len(parts) >= 2 else seg
    return seg.split("/")[0]


def _npm_purl(name: str, version: str) -> str:
    # scoped names are percent-encoded per the purl spec (canonical form)
    if name.startswith("@"):
        scope, _, rest = name.partition("/")
        enc = _purl_quote(scope) + "/" + _purl_quote(rest)
    else:
        enc = _purl_quote(name)
    return f"pkg:npm/{enc}@{version}" if version else f"pkg:npm/{enc}"


def _purl_quote(seg: str) -> str:
    return re.sub(r"[^A-Za-z0-9.\-_]", lambda m: f"%{ord(m.group(0)):02X}", seg)


def _add_integrity(
    checksums: list[tuple[str, str]], integrity: object, lock: Path, name: str
) -> None:
    """Parse npm SRI strings ('sha512-<base64>') into (algorithm, hexdigest)."""
    if not isinstance(integrity, str) or "-" not in integrity:
        return
    algo, _, b64 = integrity.partition("-")
    if algo not in {"sha1", "sha256", "sha384", "sha512"}:
        return
    try:
        digest = base64.b64decode(b64, validate=False).hex()
    except (ValueError, TypeError):
        return
    if digest:
        checksums.append((algo.upper(), digest))


# ---------------------------------------------------------------------------
# Augmentation: installed virtualenv dist-info (METADATA + RECORD)
# ---------------------------------------------------------------------------


def parse_venv_dist_info(site_packages: str | Path) -> Inventory:
    """Read installed ``*.dist-info`` directories for license metadata and
    checksums (absent from lock files).

    For each distribution we parse ``METADATA`` (Name, Version,
    License-Expression, License, License :: classifiers) and compute a
    SHA-256 of the ``METADATA`` bytes as the package checksum.  A missing or
    corrupt ``RECORD`` file is reported as a warning but does not fail the
    inventory (the environment may be partially installed).
    """
    inv = Inventory()
    root = Path(site_packages)
    if not root.is_dir():
        inv.warnings.append(f"venv site-packages '{root}' not found")
        return inv

    for dist in sorted(root.glob("*.dist-info")):
        metadata_path = dist / "METADATA"
        record_path = dist / "RECORD"
        try:
            metadata_bytes = metadata_path.read_bytes()
        except OSError:
            inv.warnings.append(f"dist-info '{dist.name}': METADATA unreadable")
            continue
        meta = _parse_metadata(metadata_bytes.decode("utf-8", errors="replace"))
        if not meta.get("Name") or not meta.get("Version"):
            inv.warnings.append(f"dist-info '{dist.name}': METADATA lacks Name/Version")
            continue

        if not record_path.is_file():
            inv.warnings.append(
                f"dist-info '{dist.name}': RECORD missing (partial install?)"
            )
            record_ok = False
        else:
            record_ok = _validate_record(record_path, dist, inv)

        checksums = (("SHA256", hashlib.sha256(metadata_bytes).hexdigest()),)
        inv.packages.append(
            Package(
                name=meta["Name"],
                version=meta["Version"],
                ecosystem=PYPI,
                source=str(dist),
                license_expression=meta.get("LicenseExpression") or meta.get("License"),
                purl=f"pkg:pypi/{norm_pypi_name(meta['Name'])}@{meta['Version']}",
                checksums=checksums,
                is_direct=False,
                origin="venv" if record_ok else "venv-incomplete",
            )
        )
    return inv


def _parse_metadata(text: str) -> dict[str, str | None]:
    """Minimal RFC 822-style METADATA reader (Name, Version, licenses)."""
    out: dict[str, str | None] = {"Name": None, "Version": None,
                                  "License": None, "LicenseExpression": None}
    license_classifiers: list[str] = []
    for raw in text.splitlines():
        if not raw or raw.startswith((" ", "\t")):
            continue  # continuation lines (long descriptions) ignored
        key, _, value = raw.partition(":")
        key = key.strip()
        value = value.strip()
        if key in out and value:
            out[key] = value
        elif key == "Classifier" and value.startswith("License :: "):
            license_classifiers.append(value)
    if not out["License"] and license_classifiers:
        # extract the leaf of the first classifier, e.g. "MIT License"
        leaf = license_classifiers[0].rsplit(":: ", 1)[-1].strip()
        out["License"] = leaf
    return out


def _validate_record(record_path: Path, dist: Path, inv: Inventory) -> bool:
    """Checksum the RECORD's own entries are well-formed CSV.

    Returns True when the RECORD parses; corrupt RECORD files are flagged as
    warnings (the METADATA checksum above remains the package checksum).
    """
    try:
        text = record_path.read_text(encoding="utf-8")
        rows = csv.reader(io.StringIO(text))
        n = 0
        for row in rows:
            if not row:
                continue
            if len(row) < 2:
                raise ValueError(f"row with {len(row)} fields")
            n += 1
        if n == 0:
            raise ValueError("empty RECORD")
        return True
    except (OSError, ValueError, csv.Error) as exc:
        inv.warnings.append(f"dist-info '{dist.name}': RECORD corrupt ({exc})")
        return False


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------


def merge_inventories(*inventories: Inventory) -> tuple[list[Package], list[str]]:
    """Merge several inventories into one sorted, deduplicated package list.

    Deduplication key is ``(ecosystem, normalized name, version, source)``:
    the *same package version from two lock files* (e.g. web + mobile) is
    kept once per source so downstream analysis can flag cross-project
    version skew; the *exact same tuple* is merged.
    """
    merged: dict[tuple[str, str, str, str], Package] = {}
    warnings: list[str] = []
    for inv in inventories:
        for pkg in inv.packages:
            key = (pkg.ecosystem, pkg.name, pkg.version, pkg.source)
            merged[key] = pkg
        warnings.extend(inv.warnings)
    packages = sorted(
        merged.values(), key=lambda p: (p.ecosystem, p.name, p.version, p.source)
    )
    return packages, warnings
