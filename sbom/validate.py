"""SBOM validation — checks generated documents against the SPDX 2.3 and
CycloneDX 1.5 schemas (the subset we emit) and enforces the determinism and
data-quality rules described in docs/SBOM_VALIDATION.md.

``validate()`` returns a list of *errors*; ``validate_document`` is used by
``cli validate`` and exits non-zero when any error is found.
"""

from __future__ import annotations

import re
import uuid

from .licenses import COMMON_SPDX_IDS, SPECIAL, is_valid_expression

_SPDX_LICENSES = COMMON_SPDX_IDS | SPECIAL

_PURL_RE = re.compile(
    r"^pkg:(pypi|npm|generic|github|golang|maven|nuget|docker)/"
    r"[^\s]+(@[^\s]+)?(\?[^\s]+)?$"
)

_SPDXID_RE = re.compile(r"^[A-Za-z0-9.\-]+$")


def validate(documents: list[tuple[str, dict]]) -> list[str]:
    """Validate a list of (kind, document) pairs.

    kind is ``"spdx"`` or ``"cyclonedx"``.
    """
    errors: list[str] = []
    for kind, doc in documents:
        if kind == "spdx":
            errors.extend(_validate_spdx(doc))
        elif kind == "cyclonedx":
            errors.extend(_validate_cyclonedx(doc))
        else:
            errors.append(f"unknown document kind '{kind}'")
    return errors


# ---------------------------------------------------------------------------
# SPDX 2.3
# ---------------------------------------------------------------------------


def _validate_spdx(doc: dict) -> list[str]:
    """Validate the SPDX 2.3 document subset we emit; return error strings."""
    errors: list[str] = []

    if doc.get("spdxVersion") != "SPDX-2.3":
        errors.append(f"spdxVersion must be SPDX-2.3, got {doc.get('spdxVersion')!r}")
    if doc.get("dataLicense") != "CC0-1.0":
        errors.append(f"dataLicense must be CC0-1.0, got {doc.get('dataLicense')!r}")
    if doc.get("SPDXID") != "SPDXRef-DOCUMENT":
        errors.append("document SPDXID must be SPDXRef-DOCUMENT")

    ns = doc.get("documentNamespace")
    if not isinstance(ns, str) or "://" not in ns:
        errors.append(f"documentNamespace must be a URI, got {ns!r}")

    created = (doc.get("creationInfo") or {}).get("created")
    if not isinstance(created, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", created
    ):
        errors.append(f"creationInfo.created must be ISO-8601 UTC, got {created!r}")

    packages = doc.get("packages")
    if not isinstance(packages, list) or not packages:
        errors.append("document must contain at least one package")

    spdxids: set[str] = {"SPDXRef-DOCUMENT"}  # the document element itself
    for pkg in packages or []:
        sid = pkg.get("SPDXID")
        if not isinstance(sid, str) or not _SPDXID_RE.fullmatch(sid):
            errors.append(f"invalid SPDXID {sid!r}")
        elif sid in spdxids:
            errors.append(f"duplicate SPDXID {sid!r}")
        spdxids.add(sid)
        # SPDX 2.3 JSON schema requires SPDXID, name and downloadLocation;
        # versionInfo is OPTIONAL (a version-less package is legal).
        for field in ("name", "downloadLocation"):
            if not isinstance(pkg.get(field), str) or not pkg[field]:
                errors.append(f"package {sid!r} missing required field {field!r}")
        lic = pkg.get("licenseDeclared", "NOASSERTION")
        if lic != "NOASSERTION" and not is_valid_expression(lic):
            errors.append(f"package {sid!r}: invalid SPDX license expression {lic!r}")
        for ref in pkg.get("externalRefs", []) or []:
            if ref.get("referenceType") == "purl":
                loc = ref.get("referenceLocator")
                if not isinstance(loc, str) or not _PURL_RE.fullmatch(loc):
                    errors.append(f"package {sid!r}: malformed purl {loc!r}")

    rels = doc.get("relationships")
    if not isinstance(rels, list):
        errors.append("relationships must be a list")
    for rel in rels or []:
        if rel.get("spdxElementId") not in spdxids:
            errors.append(f"relationship references unknown element {rel.get('spdxElementId')!r}")
        if rel.get("relatedSpdxElement") not in spdxids:
            errors.append(
                f"relationship references unknown related element {rel.get('relatedSpdxElement')!r}"
            )
    return errors


# ---------------------------------------------------------------------------
# CycloneDX 1.5
# ---------------------------------------------------------------------------


def _validate_cyclonedx(doc: dict) -> list[str]:
    """Validate the CycloneDX 1.5 document subset we emit; return error strings."""
    errors: list[str] = []
    if doc.get("bomFormat") != "CycloneDX":
        errors.append(f"bomFormat must be CycloneDX, got {doc.get('bomFormat')!r}")
    if doc.get("specVersion") != "1.5":
        errors.append(f"specVersion must be 1.5, got {doc.get('specVersion')!r}")
    if not isinstance(doc.get("version"), int) or doc["version"] < 1:
        errors.append("document version must be a positive integer")

    serial = doc.get("serialNumber")
    if not isinstance(serial, str) or not serial.startswith("urn:uuid:"):
        errors.append(f"serialNumber must be urn:uuid:..., got {serial!r}")
    else:
        try:
            uuid.UUID(serial[len("urn:uuid:") :])
        except ValueError:
            errors.append(f"serialNumber is not a valid UUID: {serial!r}")

    ts = (doc.get("metadata") or {}).get("timestamp")
    if not isinstance(ts, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})", ts
    ):
        errors.append(f"metadata.timestamp must be RFC-3339, got {ts!r}")

    components = doc.get("components")
    if not isinstance(components, list) or not components:
        errors.append("document must contain at least one component")

    # known bom-refs = every component PLUS the root metadata component
    # (CycloneDX 1.5 places the root in metadata.component, not in the
    # components array — dependency entries may legitimately reference it)
    refs: set[str] = set()
    root_ref = ((doc.get("metadata") or {}).get("component") or {}).get("bom-ref")
    if isinstance(root_ref, str) and root_ref:
        refs.add(root_ref)
    for comp in components or []:
        ref = comp.get("bom-ref")
        if not isinstance(ref, str) or not ref:
            errors.append("component missing bom-ref")
        elif ref in refs:
            errors.append(f"duplicate bom-ref {ref!r}")
        refs.add(ref)
        for field in ("name", "version"):
            if not isinstance(comp.get(field), str) or not comp[field]:
                errors.append(f"component {ref!r} missing required field {field!r}")
        for lic in comp.get("licenses", []) or []:
            if "license" in lic and lic["license"].get("id", "") not in _SPDX_LICENSES:
                errors.append(
                    f"component {ref!r}: unknown SPDX license id {lic['license'].get('id')!r}"
                )
        if "purl" in comp:
            purl = comp["purl"]
            if not isinstance(purl, str) or not _PURL_RE.fullmatch(purl):
                errors.append(f"component {ref!r}: malformed purl {purl!r}")
        for h in comp.get("hashes", []) or []:
            if not re.fullmatch(r"[0-9a-fA-F]+", h.get("content", "")):
                errors.append(f"component {ref!r}: hash content must be hex")

    for dep in doc.get("dependencies", []) or []:
        if dep.get("ref") not in refs:
            errors.append(f"dependency entry references unknown bom-ref {dep.get('ref')!r}")
        for t in dep.get("dependsOn", []) or []:
            if t not in refs:
                errors.append(f"dependency entry dependsOn unknown bom-ref {t!r}")
    return errors
