from __future__ import annotations

import datetime
import logging
import re
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Deterministic, reusable transformations (D2.5)
#
# Each transform is a pure ``(value) -> value`` function registered under a
# stable ``op`` name.  The registry drives the UI (available ops per mapped
# field) and the pipeline applier.  No free-form code execution — transforms
# are chosen from this fixed set only (D2.5 / D2.15).
# ---------------------------------------------------------------------------

TransformFn = Callable[[Any, dict[str, Any]], Any]


def _to_str(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value)
    return s if s.strip() else None


def _trim(value: Any, _params: dict[str, Any]) -> Any:
    s = _to_str(value)
    return s.strip() if s is not None else None


def _lowercase(value: Any, _params: dict[str, Any]) -> Any:
    s = _to_str(value)
    return s.lower() if s is not None else None


def _uppercase(value: Any, _params: dict[str, Any]) -> Any:
    s = _to_str(value)
    return s.upper() if s is not None else None


def _normalize_email(value: Any, _params: dict[str, Any]) -> Any:
    s = _to_str(value)
    if s is None:
        return None
    s = s.strip().lower()
    return s if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", s) else s


def _normalize_phone(value: Any, _params: dict[str, Any]) -> Any:
    """Normalise phone to E.164-ish ``+<digits>`` (no formatting fidelity
    claims — just strips separators and keeps a leading ``+``)."""
    s = _to_str(value)
    if s is None:
        return None
    digits = re.sub(r"[^\d+]", "", s)
    if not digits:
        return None
    return digits if digits.startswith("+") else digits


def _parse_date(value: Any, _params: dict[str, Any]) -> Any:
    """Parse common date formats into ISO ``YYYY-MM-DD`` (or ISO datetime)."""
    s = _to_str(value)
    if s is None:
        return None
    s = s.strip()
    formats = (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d-%m-%y",
        "%d/%m/%y",
        "%b %d %Y",
        "%B %d %Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    )
    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(s, fmt)
            return dt.date().isoformat()
        except ValueError:
            continue
    # Fall back to dateutil-free ISO parse.
    try:
        return datetime.date.fromisoformat(s).isoformat()
    except ValueError:
        logger.debug("Unparseable date value %r", s)
        return None


def _map_values(value: Any, params: dict[str, Any]) -> Any:
    """Map categorical values (e.g. 'M'/'Male'/'MALE' → 'male')."""
    s = _to_str(value)
    if s is None:
        return None
    mapping = params.get("values") or {}
    return mapping.get(s.strip().lower(), s)


def _split_name(value: Any, params: dict[str, Any]) -> Any:
    """Split a full name.  ``part=0`` → first name, ``part=1`` → last name.
    Used when a source ``full_name`` column maps to first/last."""
    s = _to_str(value)
    if s is None:
        return None
    parts = [p for p in re.split(r"\s+", s.strip()) if p]
    part = int(params.get("part", 0))
    if not parts:
        return None
    if part == 0:
        return parts[0]
    return " ".join(parts[1:]) if len(parts) > 1 else parts[0]


def _merge_fields(value: Any, params: dict[str, Any]) -> Any:
    """Merge the current value with sibling values (``other_fields``)."""
    s = _to_str(value) or ""
    others = [str(params["record"].get(f, "") or "") for f in params.get("other_fields", [])]
    return " ".join([s, *others]).strip() or None


def _default(value: Any, params: dict[str, Any]) -> Any:
    if value is None or (isinstance(value, str) and not value.strip()):
        return params.get("default")
    return value


def _replace(value: Any, params: dict[str, Any]) -> Any:
    s = _to_str(value)
    if s is None:
        return None
    return s.replace(str(params.get("old", "")), str(params.get("new", "")))


def _strip_prefix(value: Any, params: dict[str, Any]) -> Any:
    s = _to_str(value)
    if s is None:
        return None
    prefix = str(params.get("prefix", ""))
    return s[len(prefix) :] if prefix and s.startswith(prefix) else s


#: Registry: op name → (apply function, description).
TRANSFORM_REGISTRY: dict[str, tuple[TransformFn, str]] = {
    "trim": (_trim, "Trim surrounding whitespace"),
    "lowercase": (_lowercase, "Convert to lowercase"),
    "uppercase": (_uppercase, "Convert to uppercase"),
    "normalize_email": (_normalize_email, "Normalise email (trim + lowercase)"),
    "normalize_phone": (_normalize_phone, "Normalise phone (strip separators)"),
    "parse_date": (_parse_date, "Parse common date formats to ISO"),
    "map_values": (_map_values, "Map categorical values"),
    "split_name": (_split_name, "Split full name (part 0 = first, 1 = last)"),
    "merge_fields": (_merge_fields, "Merge with sibling fields"),
    "default": (_default, "Fill missing values with a default"),
    "replace": (_replace, "Replace a substring"),
    "strip_prefix": (_strip_prefix, "Strip a leading prefix"),
}


def available_transforms() -> list[str]:
    return list(TRANSFORM_REGISTRY.keys())


def apply_transforms(value: Any, transforms: list[dict[str, Any]], record: dict[str, Any]) -> Any:
    """Apply a list of transform descriptors ``[{op, ...params}]`` to a value."""
    result = value
    for spec in transforms or []:
        op = spec.get("op") if isinstance(spec, dict) else spec
        if op not in TRANSFORM_REGISTRY:
            logger.warning("Unknown transform op %r — skipped", op)
            continue
        fn = TRANSFORM_REGISTRY[op][0]
        params = dict(spec or {})
        params.pop("op", None)
        params["record"] = record
        result = fn(result, params)
    return result


def apply_mapping(records: list[dict[str, Any]], mapping: dict[str, Any]) -> list[dict[str, Any]]:
    """Apply the operator's mapping to every source record.

    ``mapping`` is ``{source_field: {target, transforms: [...]}}``.  A
    ``full_name`` mapping fans out into first/last (split transform).  The
    result keeps all unmapped source fields untouched (operators may want
    them for reference) and overlays the mapped target fields.
    """
    transformed: list[dict[str, Any]] = []
    for record in records:
        out = dict(record)
        for source_field, spec in mapping.items():
            if not isinstance(spec, dict):
                continue
            target = spec.get("target")
            if not target:
                continue
            transforms = spec.get("transforms") or []
            value = record.get(source_field)
            if target == "full_name":
                # Fan-out: first/last come from the same source column.
                out["first_name"] = apply_transforms(
                    value, [*transforms, {"op": "split_name", "part": 0}], record
                )
                out["last_name"] = apply_transforms(
                    value, [*transforms, {"op": "split_name", "part": 1}], record
                )
            else:
                out[target] = apply_transforms(value, transforms, record)
        # Idempotency key: the migrator records mappings by ``legacy_id``.
        # When the source has no explicit ID column, derive it from the
        # mapped student number so every record is traceable and re-runs
        # never duplicate (unique constraint on entity_type+legacy_id).
        if not out.get("legacy_id") and out.get("student_number"):
            out["legacy_id"] = out["student_number"]
        transformed.append(out)
    return transformed
