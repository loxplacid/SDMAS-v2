"""Policy-as-code — deterministic condition evaluator (pure functions).

Rules are data, not code.  A condition is a JSON expression tree:

.. code-block:: json

    {
      "op": "and",
      "conditions": [
        {"op": "lt", "field": "attendance.rate", "value": 0.85},
        {"op": "exists", "field": "student.id"}
      ]
    }

Operators (all deterministic, same input → same result):

- comparisons: ``eq`` ``neq`` ``lt`` ``lte`` ``gt`` ``gte`` (numeric-aware)
- membership: ``in`` ``not_in``
- string/list: ``contains``
- presence: ``exists`` ``not_exists``
- boolean: ``is_true`` ``is_false``
- combinators: ``and`` ``or`` ``not``

Fields are dotted paths resolved against the input data (``attendance.rate``
→ ``data["attendance"]["rate"]``).  No code evaluation (no ``eval``, no
Python expressions) — the operator set is closed, which keeps the engine
safe to run on untrusted policy data.
"""

from __future__ import annotations

import datetime
from typing import Any

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

_MISSING = object()


def get_path(data: Any, path: str, default: Any = None) -> Any:
    """Resolve a dotted field path against ``data``.

    ``attendance.rate`` → ``data["attendance"]["rate"]``.  Returns
    ``default`` when any segment is missing.
    """
    if not path:
        return default
    current = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return default
    return current


def _coerce_number(value: Any) -> float | None:
    """Coerce a value to a float for numeric comparison, else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().replace(",", "").rstrip("%"))
        except ValueError:
            return None
    return None


def _as_string(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


# ---------------------------------------------------------------------------
# Condition evaluation
# ---------------------------------------------------------------------------


def evaluate_condition(condition: dict[str, Any], data: Any) -> bool:
    """Evaluate a condition expression tree against ``data``.

    Returns ``False`` for unknown operators or malformed nodes — the
    engine fails closed (a broken rule can never accidentally allow).
    """
    if not isinstance(condition, dict):
        return False

    op = condition.get("op")
    if op == "and":
        sub = condition.get("conditions")
        if not isinstance(sub, list):
            return False
        return all(evaluate_condition(c, data) for c in sub)

    if op == "or":
        sub = condition.get("conditions")
        if not isinstance(sub, list):
            return False
        return any(evaluate_condition(c, data) for c in sub)

    if op == "not":
        inner = condition.get("condition")
        if not isinstance(inner, dict):
            return False
        return not evaluate_condition(inner, data)

    field = condition.get("field")
    actual = get_path(data, field, _MISSING) if field else _MISSING
    expected = condition.get("value")

    if op in ("eq", "neq"):
        matched = _values_equal(actual, expected, _MISSING)
        return matched if op == "eq" else not matched

    if op in ("lt", "lte", "gt", "gte"):
        actual_num = _coerce_number(actual)
        expected_num = _coerce_number(expected)
        if actual_num is None or expected_num is None:
            return False
        if op == "lt":
            return actual_num < expected_num
        if op == "lte":
            return actual_num <= expected_num
        if op == "gt":
            return actual_num > expected_num
        return actual_num >= expected_num

    if op in ("in", "not_in"):
        if not isinstance(expected, list):
            return False
        matched = any(_values_equal(actual, item, _MISSING) for item in expected)
        return matched if op == "in" else not matched

    if op == "contains":
        if actual is _MISSING or actual is None:
            return False
        if isinstance(actual, list):
            return any(_values_equal(item, expected, _MISSING) for item in actual)
        return _as_string(expected) in _as_string(actual)

    if op == "exists":
        return actual is not _MISSING and actual is not None

    if op == "not_exists":
        return actual is _MISSING or actual is None

    if op == "is_true":
        return actual is True

    if op == "is_false":
        return actual is False

    # Unknown operator → fail closed.
    return False


def _values_equal(actual: Any, expected: Any, missing: Any) -> bool:
    """Type-tolerant equality: numeric strings compare with numbers, dates
    compare with ISO strings, everything else compares exactly."""
    if actual is missing or actual is None:
        return expected is None or expected is missing
    if expected is None:
        return actual is None or actual is missing

    # Numeric comparison (string "45000" == int 45000).
    actual_num = _coerce_number(actual)
    expected_num = _coerce_number(expected)
    if actual_num is not None and expected_num is not None:
        return actual_num == expected_num

    # Datetime vs ISO string.
    if isinstance(actual, datetime.datetime) and isinstance(expected, str):
        try:
            parsed = datetime.datetime.fromisoformat(expected.replace("Z", "+00:00"))
            return actual == parsed
        except ValueError:
            return False

    return actual == expected
