"""Core data model for SBOM generation."""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Ecosystem identifiers used throughout the tool.
PYPI = "pypi"
NPM = "npm"


def norm_pypi_name(name: str) -> str:
    """PEP 503 normalisation: lower-case and collapse runs of -_. to a dash.

    Used for deduplication keys only; the emitted SBOM keeps the canonical
    name exactly as the lock file wrote it.
    """
    return re.sub(r"[-_.]+", "-", name).lower()


def norm_npm_name(name: str) -> str:
    """npm package names are case-sensitive on disk but the registry treats
    them case-insensitively for resolution; we lowercase for dedupe keys."""
    return name.lower()


@dataclass(frozen=True)
class Dependency:
    """A dependency edge declared by a package in a lock file."""

    name: str
    #: Version constraint as written in the lock file (may be empty when the
    #: lock file does not record one, e.g. npm hoisted edges).
    specifier: str = ""


@dataclass(frozen=True)
class Package:
    """A resolved package component of the SBOM.

    Frozen and hashable so inventories can be deduplicated and sorted
    deterministically.
    """

    name: str
    version: str
    ecosystem: str
    #: Human-readable provenance, e.g. ``apps/api/uv.lock``.
    source: str
    #: SPDX license expression as declared by the ecosystem metadata, or
    #: ``None`` when the source carries no license information.
    license_expression: str | None = None
    purl: str | None = None
    download_url: str | None = None
    #: ``(algorithm, hexdigest)`` tuples, e.g. ``("SHA256", "abc…")``.
    checksums: tuple[tuple[str, str], ...] = ()
    dependencies: tuple[Dependency, ...] = ()
    is_direct: bool = True
    #: Origin class: registry / git / editable / path / workspace / npm-scope.
    origin: str | None = None

    @property
    def dedupe_key(self) -> tuple[str, str]:
        """Key used for cross-source deduplication.

        ``(ecosystem, normalized name)`` — deliberately ignores version so
        that duplicate *versions* of one package are detectable as data
        quality issues rather than silently merged.
        """
        norm = norm_pypi_name if self.ecosystem == PYPI else norm_npm_name
        return (self.ecosystem, norm(self.name))

    @property
    def identity(self) -> str:
        """A stable, unique identifier used for SPDXID / bom-ref / graph maps.

        MUST include the source: the same (ecosystem, name, version) can
        legitimately appear once per lock file (e.g. one package version
        installed in both apps/web and apps/mobile).  Keying maps on the
        source-less tuple silently overwrote the graph/relationship maps of
        the first instance, losing its dependency edges and DESCRIBES.
        """
        return f"{self.ecosystem}:{self.name}:{self.version}:{self.source}"
