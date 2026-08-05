"""SPDX 2.3 (JSON) emission.

Implements the SPDX 2.3 JSON schema for the package-level document we
produce.  Determinism notes:

* ``documentNamespace`` is a UUIDv5 derived from the *content* of the SBOM
  (canonical sorted package list + root component), so identical inputs
  produce an identical namespace on every run.
* ``creationInfo.created`` honours ``SOURCE_DATE_EPOCH`` (Unix seconds) for
  reproducible builds; without it the current UTC time is used, which is
  spec-compliant but not byte-reproducible.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import re
import uuid
from typing import Iterable

from . import __version__
from .graph import ResolvedGraph
from .licenses import is_valid_expression
from .models import Package

#: Namespace used to derive deterministic UUIDs.  Fixed constant (not random).
_DOC_NS = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")

#: SPDX license list version we validate expressions against.
LICENSE_LIST_VERSION = "3.23"


def created_timestamp(source_date_epoch: str | None = None) -> str:
    """Return an ISO-8601 UTC timestamp for ``creationInfo.created``.

    Uses ``SOURCE_DATE_EPOCH`` when provided (reproducible-builds
    convention); raises ``ValueError`` on a malformed value rather than
    silently producing a wrong date.
    """
    if source_date_epoch is not None:
        try:
            stamp = int(source_date_epoch)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"SOURCE_DATE_EPOCH must be an integer Unix timestamp, got {source_date_epoch!r}"
            ) from exc
        try:
            return _dt.datetime.fromtimestamp(stamp, tz=_dt.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        except (OverflowError, OSError, ValueError) as exc:
            raise ValueError(
                f"SOURCE_DATE_EPOCH={source_date_epoch} is out of range"
            ) from exc
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def spdx_id(pkg: Package, used: set[str]) -> str:
    """Deterministic, collision-free SPDXID for a package.

    ``SPDXRef-Package-<ecosystem>-<name>-<version>`` with every character
    outside the SPDXID alphabet replaced; collisions are disambiguated with
    a content-derived hex suffix.
    """
    base = _slug(f"SPDXRef-Package-{pkg.ecosystem}-{pkg.name}-{pkg.version}")
    candidate = base
    n = 0
    while candidate in used:
        n += 1
        suffix = hashlib.sha256(pkg.identity.encode("utf-8")).hexdigest()[:8]
        candidate = f"{base}-{suffix}-{n}"
    used.add(candidate)
    return candidate


def _slug(text: str) -> str:
    out = re.sub(r"[^A-Za-z0-9.\-]", "-", text)
    # SPDXID cannot start with a digit per the spec grammar
    if out and out[0].isdigit():
        out = "P-" + out
    return out or "SPDXRef-Package"


def build_spdx(
    packages: list[Package],
    root_name: str,
    root_version: str,
    graph: ResolvedGraph,
    created: str,
    tool_creator: str = f"SDMAS-SBOM-{__version__}",
) -> dict:
    """Build the SPDX 2.3 JSON document (as a dict)."""
    used_ids: set[str] = set()
    spdxid_of: dict[str, str] = {}

    doc_packages: list[dict] = []
    for pkg in packages:
        sid = spdx_id(pkg, used_ids)
        spdxid_of[pkg.identity] = sid
        declared = _spdx_license(pkg.license_expression)
        entry: dict = {
            "name": pkg.name,
            "SPDXID": sid,
            "versionInfo": pkg.version,
            "filesAnalyzed": False,
            "downloadLocation": pkg.download_url or "NOASSERTION",
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": declared,
            "copyrightText": "NOASSERTION",
            "supplier": "NOASSERTION",
            "externalRefs": [],
        }
        if pkg.purl:
            entry["externalRefs"].append(
                {
                    "referenceCategory": "PACKAGE-MANAGER",
                    "referenceType": "purl",
                    "referenceLocator": pkg.purl,
                }
            )
        if pkg.checksums:
            entry["checksums"] = [
                {"algorithm": alg, "checksumValue": digest}
                for alg, digest in pkg.checksums
            ]
        comments: list[str] = []
        if pkg.origin and pkg.origin not in {"registry", "unknown", "venv", "venv-incomplete"}:
            comments.append(f"origin: {pkg.origin}")
        if (
            pkg.license_expression
            and declared == "NOASSERTION"
            and pkg.license_expression not in ("NOASSERTION", "NONE")
        ):
            # unresolvable licence metadata: keep it, but schema-valid
            comments.append(f"original license metadata: {pkg.license_expression}")
        if comments:
            entry["comment"] = "; ".join(comments)
        doc_packages.append(entry)

    relationships: list[dict] = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": spdxid_of[pkg.identity],
        }
        for pkg in packages
    ]
    for pkg in packages:
        src = spdxid_of[pkg.identity]
        seen: set[str] = set()
        for target in graph.edges.get(pkg.identity, []):
            tid = spdxid_of.get(target.identity)
            if tid and tid not in seen:
                seen.add(tid)
                relationships.append(
                    {
                        "spdxElementId": src,
                        "relationshipType": "DEPENDS_ON",
                        "relatedSpdxElement": tid,
                    }
                )

    canonical = _canonical_key(packages, root_name, root_version)
    namespace = f"https://sdmas.local/sbom/spdx/{uuid.uuid5(_DOC_NS, canonical)}"

    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"{root_name}-{root_version}",
        "documentNamespace": namespace,
        "creationInfo": {
            "created": created,
            "creators": [f"Tool: {tool_creator}"],
            "licenseListVersion": LICENSE_LIST_VERSION,
        },
        "packages": doc_packages,
        "relationships": relationships,
    }


def _spdx_license(expr: str | None) -> str:
    """Emit a declared license: recognised SPDX expressions verbatim, else
    NOASSERTION (the raw value is preserved in the package comment)."""
    if not expr:
        return "NOASSERTION"
    if is_valid_expression(expr):
        return expr
    return "NOASSERTION"


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
