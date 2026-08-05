"""CycloneDX 1.5 (JSON) emission.

Implements the CycloneDX 1.5 JSON schema for package-level components.
Determinism notes:

* ``serialNumber`` is ``urn:uuid:<uuid5>`` derived from document content.
* ``metadata.timestamp`` honours ``SOURCE_DATE_EPOCH``; without it the
  current UTC time is used (spec requires a timestamp).
"""

from __future__ import annotations

import uuid

from . import __version__
from .graph import ResolvedGraph
from .licenses import is_valid_expression
from .models import Package

_CDX_NS = uuid.UUID("1f36d2a7-5a1c-4f80-8b3a-9c1d2e3f4a5b")


def build_cyclonedx(
    packages: list[Package],
    root_name: str,
    root_version: str,
    graph: ResolvedGraph,
    timestamp: str,
    tool: dict | None = None,
) -> dict:
    """Build the CycloneDX 1.5 JSON document (as a dict)."""
    if tool is None:
        tool = {
            "vendor": "SDMAS",
            "name": "sdmas-sbom",
            "version": __version__,
        }

    bom_refs: dict[str, str] = {}
    components: list[dict] = []
    for pkg in packages:
        ref = _bom_ref(pkg)
        bom_refs[pkg.identity] = ref
        comp: dict = {
            "type": "library",
            "bom-ref": ref,
            "name": pkg.name,
            "version": pkg.version,
        }
        if pkg.purl:
            comp["purl"] = pkg.purl
        licenses = _license_entry(pkg.license_expression)
        if licenses:
            comp["licenses"] = licenses
        elif pkg.license_expression:
            # unresolvable licence: omit from schema-valid field, keep verbatim
            comp["properties"] = [
                {"name": "sdmas:license:original", "value": pkg.license_expression}
            ]
        if pkg.checksums:
            comp["hashes"] = [
                {"alg": _cdx_alg(alg), "content": digest}
                for alg, digest in pkg.checksums
            ]
        if pkg.download_url:
            comp["externalReferences"] = [
                {"type": "distribution", "url": pkg.download_url}
            ]
        components.append(comp)

    dependencies: list[dict] = []
    for pkg in packages:
        src = bom_refs[pkg.identity]
        depends_on: list[str] = []
        seen: set[str] = set()
        for target in graph.edges.get(pkg.identity, []):
            tid = bom_refs.get(target.identity)
            if tid and tid not in seen:
                seen.add(tid)
                depends_on.append(tid)
        dependencies.append({"ref": src, "dependsOn": sorted(depends_on)})

    # Wire the root metadata component into the dependency graph so
    # root-traversing consumers (Dependency-Track, Grype --from-graph)
    # see the tree instead of a disconnected root.  The root depends on
    # every direct install; without this entry the root ref appears in
    # metadata.component but nowhere in dependencies.
    root_direct = [
        bom_refs[pkg.identity] for pkg in packages if pkg.is_direct
    ]
    dependencies.append(
        {"ref": _root_ref(root_name, root_version), "dependsOn": sorted(root_direct)}
    )

    canonical = _canonical_key(packages, root_name, root_version)
    serial = f"urn:uuid:{uuid.uuid5(_CDX_NS, canonical)}"

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": serial,
        "version": 1,
        "metadata": {
            "timestamp": timestamp,
            "tools": [tool],
            "component": {
                "type": "application",
                "bom-ref": _root_ref(root_name, root_version),
                "name": root_name,
                "version": root_version,
            },
        },
        "components": components,
        "dependencies": dependencies,
    }


def _bom_ref(pkg: Package) -> str:
    # identity alone is NOT unique: the same (ecosystem, name, version) can
    # legitimately appear once per lock file (e.g. one package version
    # installed in both apps/web and apps/mobile).  CycloneDX requires every
    # component bom-ref to be unique, so the ref must include the source.
    # ``identity|source`` is unique per merged Package by construction.
    return str(uuid.uuid5(_CDX_NS, f"{pkg.identity}|{pkg.source}"))


def _root_ref(root_name: str, root_version: str) -> str:
    return str(uuid.uuid5(_CDX_NS, f"root:{root_name}:{root_version}"))


def _license_entry(expr: str | None) -> list[dict] | None:
    """CycloneDX licenses list: a bare SPDX id becomes ``license.id``, an
    expression with operators becomes ``license.expression``.  Returns None
    for unrecognised values (caller preserves them as a property)."""
    if not expr or not is_valid_expression(expr):
        return None
    if any(op in expr for op in (" AND ", " OR ", " WITH ")):
        return [{"expression": expr}]
    return [{"license": {"id": expr}}]


def _cdx_alg(algorithm: str) -> str:
    return {"SHA1": "SHA-1", "SHA256": "SHA-256", "SHA384": "SHA-384", "SHA512": "SHA-512"}.get(
        algorithm.upper(), algorithm.upper()
    )


def _canonical_key(packages: list[Package], root_name: str, root_version: str) -> str:
    lines = [f"{root_name}@{root_version}"]
    for pkg in packages:
        lines.append(
            "|".join(
                [
                    pkg.ecosystem,
                    pkg.name,
                    pkg.version,
                    pkg.purl or "",
                    pkg.license_expression or "",
                    pkg.download_url or "",
                ]
            )
        )
        lines.extend(f"~{d.name}{d.specifier}" for d in pkg.dependencies)
    return "\n".join(lines)
