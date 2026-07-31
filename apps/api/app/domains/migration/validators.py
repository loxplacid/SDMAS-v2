from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class ValidationRule:
    """A single validation rule applied to a field."""

    field: str
    name: str
    validator: Callable[[Any, dict[str, Any]], str | None]
    """Takes (field_value, full_record). Returns None if valid, or an error string."""


@dataclass
class ValidationResult:
    """Result of validating a single record."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Built-in validation rules
# ---------------------------------------------------------------------------


def required(field: str) -> ValidationRule:
    def _check(val: Any, _record: dict[str, Any]) -> str | None:
        if val is None or (isinstance(val, str) and not val.strip()):
            return f"'{field}' is required"
        return None
    return ValidationRule(field=field, name="required", validator=_check)


def max_length(field: str, max_len: int) -> ValidationRule:
    def _check(val: Any, _record: dict[str, Any]) -> str | None:
        if val is not None and isinstance(val, str) and len(val) > max_len:
            return f"'{field}' exceeds max length {max_len} (got {len(val)})"
        return None
    return ValidationRule(field=field, name="max_length", validator=_check)


def valid_email(field: str) -> ValidationRule:
    def _check(val: Any, _record: dict[str, Any]) -> str | None:
        if val is not None and isinstance(val, str) and "@" not in val:
            return f"'{field}' is not a valid email"
        return None
    return ValidationRule(field=field, name="valid_email", validator=_check)


def one_of(field: str, allowed: set[str]) -> ValidationRule:
    def _check(val: Any, _record: dict[str, Any]) -> str | None:
        if val is not None and val not in allowed:
            return f"'{field}' must be one of {sorted(allowed)}, got '{val}'"
        return None
    return ValidationRule(field=field, name="one_of", validator=_check)


def positive_number(field: str) -> ValidationRule:
    def _check(val: Any, _record: dict[str, Any]) -> str | None:
        if val is not None:
            try:
                if float(val) < 0:
                    return f"'{field}' must be non-negative, got {val}"
            except (ValueError, TypeError):
                return f"'{field}' must be a number, got '{val}'"
        return None
    return ValidationRule(field=field, name="positive_number", validator=_check)


def unique_in_set(field: str) -> ValidationRule:
    """Cross-record uniqueness check — applied by ValidationEngine,
    not as a per-record rule."""

    def _check(val: Any, _record: dict[str, Any]) -> str | None:
        return None
    return ValidationRule(field=field, name="unique_in_set", validator=_check)


# ---------------------------------------------------------------------------
# ValidationEngine
# ---------------------------------------------------------------------------


class ValidationEngine:
    """Runs a set of validation rules against a batch of records.

    Tracks both per-record errors and cross-record uniqueness violations.
    """

    def __init__(self) -> None:
        self._rules: dict[str, list[ValidationRule]] = {}

    def add_rules(self, entity_type: str, rules: list[ValidationRule]) -> None:
        self._rules.setdefault(entity_type, []).extend(rules)

    def validate(
        self,
        entity_type: str,
        records: list[dict[str, Any]],
    ) -> list[tuple[dict[str, Any], ValidationResult]]:
        rules = self._rules.get(entity_type, [])
        uniq_fields: dict[str, set[Any]] = {}
        uniq_rules = [r for r in rules if r.name == "unique_in_set"]
        for r in uniq_rules:
            uniq_fields[r.field] = set()

        results: list[tuple[dict[str, Any], ValidationResult]] = []

        for record in records:
            result = ValidationResult(is_valid=True)

            for rule in rules:
                if rule.name == "unique_in_set":
                    continue
                val = record.get(rule.field)
                error = rule.validator(val, record)
                if error:
                    result.errors.append(error)
                    result.is_valid = False

            results.append((record, result))

        for rule in uniq_rules:
            field = rule.field
            seen: set[Any] = set()
            for record, result in results:
                val = record.get(field)
                if val is not None:
                    if val in seen:
                        result.errors.append(
                            f"Duplicate '{field}': '{val}' appears in multiple records"
                        )
                        result.is_valid = False
                    seen.add(val)

        return results
