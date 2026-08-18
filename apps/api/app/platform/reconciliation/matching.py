"""Universal reconciliation — deterministic matching primitives.

Pure, deterministic functions (no AI, no randomness, no network):

- normalization of field values (exact / lower / digits / iso_date /
  numeric)
- match-key extraction from a record using a configured key spec
- one-pass matching of source records against target records
- per-field comparison with tolerance rules (exact / absolute / percent /
  days)

The same input always produces the same output, so reconciliation is
reproducible and auditable.
"""

from __future__ import annotations

import datetime
import re
import unicodedata
from typing import Any, Optional

from app.platform.reconciliation.models import (
    MATCH_STATUS_EXCEPTION,
    MATCH_STATUS_MATCHED,
    MATCH_STATUS_SOURCE_ONLY,
    MATCH_STATUS_TARGET_ONLY,
    NORMALIZERS,
    TOLERANCE_TYPES,
)

_WS_RE = re.compile(r"\s+")
_DIGITS_RE = re.compile(r"\D+")

#: Exception codes produced by the engine.
CODE_UNMATCHED_SOURCE = "UNMATCHED_SOURCE"
CODE_UNMATCHED_TARGET = "UNMATCHED_TARGET"
CODE_TOLERANCE_EXCEEDED = "TOLERANCE_EXCEEDED"


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if not unicodedata.combining(c))
    return _WS_RE.sub(" ", value).strip().lower()


def normalize_value(value: Any, normalizer: str) -> Any:
    """Normalize a single value per the named normalizer.

    Unknown normalizers raise ``ValueError`` so a misconfigured rule fails
    loudly at match time rather than silently producing a wrong key.
    """
    if normalizer not in NORMALIZERS:
        raise ValueError(f"unknown normalizer {normalizer!r}")
    if value is None:
        return None
    if normalizer == "exact":
        return value
    if normalizer == "lower":
        return _fold(str(value))
    if normalizer == "digits":
        return _DIGITS_RE.sub("", str(value))
    if normalizer == "iso_date":
        if isinstance(value, datetime.datetime):
            return value.date().isoformat()
        if isinstance(value, datetime.date):
            return value.isoformat()
        return str(value).strip()[:10]
    if normalizer == "numeric":
        try:
            return float(str(value).replace(",", "").replace(" ", ""))
        except (TypeError, ValueError):
            return None
    return value  # pragma: no cover — guarded above


def _side_field(spec: dict[str, Any], side: str) -> str | None:
    """The field name to extract for one side of a match key spec."""
    direct = spec.get("field")
    if direct:
        return direct
    return spec.get(f"{side}_field")


def build_match_key(
    record: dict[str, Any],
    match_keys: list[dict[str, Any]],
    side: str = "source",
) -> tuple[Any, ...]:
    """Extract the normalized match key tuple from a record on one side.

    ``match_keys`` is a list of dicts with ``source_field`` / ``target_field``
    (and optional ``normalizer``); ``side`` selects which field name to
    read, so a single key spec works for both the source and target side
    of a comparison.
    """
    values: list[Any] = []
    for spec in match_keys:
        field = _side_field(spec, side)
        normalizer = spec.get("normalizer") or "exact"
        values.append(normalize_value(record.get(field or ""), normalizer))
    return tuple(values)


def match_records(
    source_records: list[dict[str, Any]],
    target_records: list[dict[str, Any]],
    match_keys: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Deterministically match source records to target records.

    Returns one result dict per **source** record:

    - ``matched``      — target found by key (``target_ref`` set)
    - ``source_only``  — no target with this key

    Target records that no source matched are reported separately (callers
    use :func:`unmatched_targets`).  Matching is one-to-one: a target key is
    consumed by the first source (in input order) that claims it, so no
    target is matched twice.  Keys with no normalizer default to ``exact``.
    """
    # Build the target index: normalized key -> (target_ref, target_record).
    target_index: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for target in target_records:
        key = build_match_key(target, match_keys, side="target")
        if key is None or any(v is None for v in key):
            continue
        target_index.setdefault(key, []).append(target)

    consumed: set[int] = set()
    results: list[dict[str, Any]] = []
    for source in source_records:
        key = build_match_key(source, match_keys, side="source")
        if key is None or any(v is None for v in key):
            results.append(
                {
                    "source": source,
                    "target": None,
                    "status": MATCH_STATUS_SOURCE_ONLY,
                    "reason": "source match key incomplete",
                }
            )
            continue
        candidates = target_index.get(key, [])
        matched = next((t for t in candidates if id(t) not in consumed), None)
        if matched is None:
            results.append(
                {
                    "source": source,
                    "target": None,
                    "status": MATCH_STATUS_SOURCE_ONLY,
                    "reason": "no target with this key",
                }
            )
            continue
        consumed.add(id(matched))
        results.append({"source": source, "target": matched, "status": MATCH_STATUS_MATCHED})
    return results


def unmatched_targets(
    source_records: list[dict[str, Any]],
    target_records: list[dict[str, Any]],
    match_keys: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Target records no source matched (their key never appeared on the
    source side)."""
    source_keys = {build_match_key(s, match_keys, side="source") for s in source_records}
    return [
        t
        for t in target_records
        if build_match_key(t, match_keys, side="target") not in source_keys
    ]


def compare_records(
    source: dict[str, Any],
    target: dict[str, Any],
    comparison_fields: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare source vs target per configured comparison fields.

    ``comparison_fields`` is a list of ``{"source_field", "target_field",
    "tolerance", "value"}`` dicts.  Returns::

        {
          "differences": {field: {"source": ..., "target": ..., "diff": ...}},
          "within_tolerance": bool,
          "exceeded": [field, ...],
        }

    Tolerance kinds:
    - ``exact``    — values must be equal (diff is bool)
    - ``absolute`` — |s - t| <= value (numeric)
    - ``percent``  — |s - t| / max(|s|, |t|, 1) <= value (0..1)
    - ``days``     — |s - t| <= value days (dates)
    """
    differences: dict[str, Any] = {}
    exceeded: list[str] = []
    within = True

    for spec in comparison_fields or []:
        src_field = spec.get("source_field") or ""
        tgt_field = spec.get("target_field") or src_field
        tolerance = spec.get("tolerance") or "exact"
        if tolerance not in TOLERANCE_TYPES:
            raise ValueError(f"unknown tolerance {tolerance!r}")
        s = source.get(src_field)
        t = target.get(tgt_field)

        diff: Any
        ok: bool
        if tolerance == "exact":
            diff = s != t
            ok = s == t
        elif tolerance == "absolute":
            sv, tv = _to_float(s), _to_float(t)
            diff = None if (sv is None or tv is None) else abs(sv - tv)
            ok = diff is not None and diff <= float(spec.get("value", 0))
        elif tolerance == "percent":
            sv, tv = _to_float(s), _to_float(t)
            if sv is None or tv is None:
                diff, ok = None, False
            else:
                diff = abs(sv - tv) / max(abs(sv), abs(tv), 1.0)
                ok = diff <= float(spec.get("value", 0))
        else:  # days
            sd, td = _to_date(s), _to_date(t)
            if sd is None or td is None:
                diff, ok = None, False
            else:
                diff = abs((sd - td).days)
                ok = diff <= int(spec.get("value", 0))

        label = src_field or tgt_field
        differences[label] = {
            "source": s,
            "target": t,
            "diff": diff,
        }
        if not ok:
            within = False
            exceeded.append(label)

    return {
        "differences": differences,
        "within_tolerance": within,
        "exceeded": exceeded,
    }


def classify(
    match: dict[str, Any],
    comparison_fields: list[dict[str, Any]],
) -> tuple[str, Optional[str], Optional[str]]:
    """Classify a ``match_records`` result into ``(status, exception_code,
    reason)``.

    - ``matched`` + within tolerance → matched
    - ``matched`` + tolerance exceeded → exception ``TOLERANCE_EXCEEDED``
    - no target → source_only
    """
    status = match["status"]
    if status == MATCH_STATUS_MATCHED:
        comparison = compare_records(match["source"], match["target"], comparison_fields)
        if comparison["within_tolerance"]:
            return MATCH_STATUS_MATCHED, None, None
        return (
            MATCH_STATUS_EXCEPTION,
            CODE_TOLERANCE_EXCEEDED,
            "tolerance exceeded on fields: " + ", ".join(comparison["exceeded"]),
        )
    if status == MATCH_STATUS_SOURCE_ONLY:
        return MATCH_STATUS_SOURCE_ONLY, CODE_UNMATCHED_SOURCE, match.get("reason")
    return MATCH_STATUS_TARGET_ONLY, CODE_UNMATCHED_TARGET, match.get("reason")


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_date(value: Any) -> Optional[datetime.date]:
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
