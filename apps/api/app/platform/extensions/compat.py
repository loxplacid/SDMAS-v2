"""Extension compatibility — pure semantic-version helpers (stdlib only).

The extension contract declares the core version range it requires (e.g.
``>=0.1.0,<1.0.0``); publishing/enabling an extension fails closed when the
running core does not satisfy the range.  Implemented here with a small
deterministic parser instead of pulling ``packaging`` into the platform
layer (it is only a transitive dev dependency).

Supported forms
---------------
Versions:      ``MAJOR.MINOR.PATCH`` with an optional ``-prerelease``
               suffix (``1.2.3``, ``0.1.0-rc1``).  ``MAJOR``/``MINOR``
               without ``PATCH`` are normalized (``1.2`` -> ``1.2.0``).
Ranges:        comma-separated clauses over the operators ``>=``, ``<=``,
               ``>``, ``<``, ``==``, ``!=``, or a bare exact version, plus
               the wildcard ``*`` (any version).  Examples:
               ``>=0.1.0``, ``>=0.1.0,<1.0.0``, ``==0.2.3``, ``*``.

Pre-release ordering follows semver: ``1.0.0-rc1 < 1.0.0``.  An empty or
malformed range fails closed (``satisfies`` returns ``False``) — a broken
declaration can never silently permit an incompatible extension.
"""

from __future__ import annotations

import re

#: The core platform version this package is built against.  Mirrors
#: ``pyproject.toml`` ``project.version`` (and ``app.main``'s log version).
CORE_VERSION = "0.1.0"

_VERSION_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)"
    r"(?:\.(?P<minor>0|[1-9]\d*))?"
    r"(?:\.(?P<patch>0|[1-9]\d*))?"
    r"(?:-(?P<pre>[0-9A-Za-z.-]+))?$"
)

_CLAUSE_RE = re.compile(r"^\s*(>=|<=|>|<|==|!=)?\s*(\*|[0-9A-Za-z.\-]+)\s*$")


class Version:
    """A parsed semantic version (comparable tuple + prerelease tag)."""

    __slots__ = ("major", "minor", "patch", "pre", "_key")

    def __init__(self, major: int, minor: int, patch: int, pre: str | None = None) -> None:
        self.major = major
        self.minor = minor
        self.patch = patch
        self.pre = pre
        #: Sort key: release tuple, then a release-vs-prerelease marker so
        #: ``1.0.0-rc1 < 1.0.0`` holds (any pre-release sorts below the
        #: corresponding release).  Both branches are tuples — never mixing
        #: a tuple with a non-tuple sentinel, which would raise on compare.
        if pre is None:
            self._key: tuple = (major, minor, patch, (1,))
        else:
            self._key = (major, minor, patch, (0,) + tuple(_pre_parts(pre)))

    def __repr__(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        return f"{base}-{self.pre}" if self.pre else base

    def __str__(self) -> str:
        return repr(self)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Version) and self._key == other._key

    def __lt__(self, other: "Version") -> bool:
        return self._key < other._key

    def __le__(self, other: "Version") -> bool:
        return self._key <= other._key

    def __gt__(self, other: "Version") -> bool:
        return self._key > other._key

    def __ge__(self, other: "Version") -> bool:
        return self._key >= other._key

    def __hash__(self) -> int:
        return hash(self._key)


def _pre_parts(pre: str) -> list[tuple]:
    """Semver pre-release identifier keys.

    Numeric identifiers sort before alphanumeric ones (per semver), then
    numerically / ASCII respectively.
    """
    parts: list[tuple] = []
    for part in pre.split("."):
        if part.isdigit():
            parts.append((0, int(part), ""))
        else:
            parts.append((1, 0, part))
    return parts


def parse_version(value: str) -> Version | None:
    """Parse ``value`` into a :class:`Version`, or ``None`` if malformed."""
    if not isinstance(value, str):
        return None
    match = _VERSION_RE.match(value.strip())
    if match is None:
        return None
    major = int(match.group("major"))
    minor = int(match.group("minor") or "0")
    patch = int(match.group("patch") or "0")
    return Version(major, minor, patch, match.group("pre"))


def satisfies(version: str | Version | None, range_spec: str | None) -> bool:
    """Whether ``version`` satisfies a comma-separated version range.

    Fails closed: ``None``/malformed versions, an empty or malformed range
    (other than ``*``), or any unsatisfied clause yields ``False``.
    """
    parsed: Version | None
    if isinstance(version, Version):
        parsed = version
    else:
        parsed = parse_version(version) if version else None
    if parsed is None:
        return False
    if range_spec is None:
        return False
    spec = range_spec.strip()
    if not spec:
        return False
    for clause in spec.split(","):
        match = _CLAUSE_RE.match(clause)
        if match is None:
            return False
        op, raw = match.group(1), match.group(2)
        if raw == "*":
            continue
        target = parse_version(raw)
        if target is None:
            return False
        if op in (None, "=="):
            if parsed != target:
                return False
        elif op == "!=":
            if parsed == target:
                return False
        elif op == ">=":
            if not parsed >= target:
                return False
        elif op == "<=":
            if not parsed <= target:
                return False
        elif op == ">":
            if not parsed > target:
                return False
        elif op == "<":
            if not parsed < target:
                return False
        else:  # pragma: no cover — regex limits op values
            return False
    return True


def core_satisfies(range_spec: str | None) -> bool:
    """Whether the running core version satisfies ``range_spec``."""
    return satisfies(CORE_VERSION, range_spec)


__all__ = ["CORE_VERSION", "Version", "parse_version", "satisfies", "core_satisfies"]
