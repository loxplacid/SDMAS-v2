"""Deterministic Step-2 validation checks for the migration workspace.

These checks run *on top of* the migrator rule sets (which stay the single
source of truth for what each importer accepts) and catch the cross-cutting
issues a legacy export typically carries:

* duplicate identifiers (same ``student_number`` twice in the file)
* malformed dates (garbage that the ``parse_date`` transform could not parse)
* negative / non-numeric amounts
* malformed emails
* impossible enum values (attendance status, gender)
* orphan references (attendance/fee rows pointing at students or classes
  that no student row in the file defines)
* conflicting references (a student's attendance row uses a different
  class/section than the student's own row)

Everything here is pure and deterministic — no AI, no randomness, no DB
reads.  The same functions are used by the validation endpoint (to gate
READY) and by the preview endpoint (to classify each row's action).
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from typing import Any

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

ATTENDANCE_STATUSES = frozenset({"present", "absent", "late", "excused", "holiday"})
GENDERS = frozenset({"male", "female"})

#: Mapped target fields that must hold an ISO date after transformation.
DATE_TARGET_FIELDS = frozenset({"date_of_birth", "attendance_date", "payment_date"})
#: Mapped target fields that must hold a non-negative number.
AMOUNT_TARGET_FIELDS = frozenset({"amount_paid"})

BLOCKING = "BLOCKING"
WARNING = "WARNING"


@dataclass
class Finding:
    """A single deterministic finding against one source row."""

    row: int
    category: str
    severity: str
    message: str
    field: str | None = None
    value: str | None = None


@dataclass
class WorkspaceValidation:
    """Aggregated result of :func:`validate_records`."""

    blocking: list[Finding] = field(default_factory=list)
    warnings: list[Finding] = field(default_factory=list)

    @property
    def categories(self) -> dict[str, int]:
        """Count findings per category (blocking + warnings)."""
        counts: dict[str, int] = {}
        for finding in (*self.blocking, *self.warnings):
            counts[finding.category] = counts.get(finding.category, 0) + 1
        return counts

    @property
    def blocking_by_row(self) -> dict[int, list[str]]:
        by_row: dict[int, list[str]] = {}
        for finding in self.blocking:
            by_row.setdefault(finding.row, []).append(finding.message)
        return by_row


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _is_person_row(record: dict[str, Any]) -> bool:
    """A row *defines* a student when it carries a name.  Attendance and
    fee rows reference students by number only — they must not be indexed
    as student definitions (otherwise a bogus reference would "define"
    itself and evade orphan detection)."""
    return bool(_clean(record.get("first_name")) or _clean(record.get("last_name")))


def _is_iso_date(value: Any) -> bool:
    if value is None:
        return False
    try:
        datetime.date.fromisoformat(str(value).strip())
        return True
    except ValueError:
        return False


def _as_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _source_value_for_target(
    original: dict[str, Any],
    target: str,
    mapping: dict[str, Any] | None,
) -> str | None:
    """Find the original source value that fed ``target`` via the mapping."""
    if mapping:
        for source, spec in mapping.items():
            if isinstance(spec, dict) and spec.get("target") == target:
                value = _clean(original.get(source))
                if value:
                    return value
    return None


def validate_records(
    records: list[dict[str, Any]],
    original_rows: list[dict[str, Any]] | None = None,
    mapping: dict[str, Any] | None = None,
) -> WorkspaceValidation:
    """Validate transformed records (and their source rows) for Step 2.

    ``records`` are the output of ``apply_mapping`` — only *mapped* target
    fields are present, so field presence doubles as the mapping signal.
    ``original_rows`` are the raw parsed rows and ``mapping`` is the saved
    field mapping — together they distinguish "empty source value" from
    "source value the transform could not parse".
    """
    validation = WorkspaceValidation()
    original = original_rows or records

    # ── Pass 1: index student identity + class/section combos. ─────────
    # Only person rows (rows with a name) define a student.
    identity: dict[str, int] = {}  # student_number -> first row (1-based)
    class_combos: set[tuple[str, str]] = set()  # (class, section) from person rows
    student_combo: dict[str, tuple[str, str]] = {}

    for i, rec in enumerate(records):
        if not _is_person_row(rec):
            continue
        number = _clean(rec.get("student_number"))
        if number:
            if number in identity:
                validation.blocking.append(
                    Finding(
                        row=i + 1,
                        category="duplicate",
                        severity=BLOCKING,
                        message=(
                            f"Duplicate student number '{number}' "
                            f"(first seen on row {identity[number]})"
                        ),
                        field="student_number",
                        value=number,
                    )
                )
            else:
                identity[number] = i + 1
        combo = (_clean(rec.get("class_name")), _clean(rec.get("section_name")))
        if combo[0]:
            class_combos.add(combo)
            if number:
                student_combo.setdefault(number, combo)

    # ── Pass 2: per-row field + reference checks. ──────────────────────
    for i, rec in enumerate(records):
        row = i + 1
        orig = original[i] if i < len(original) else rec

        # Dates: a mapped date that is empty in the source is fine; a
        # mapped date that was non-empty but did not survive the transform
        # (or is not ISO) blocks.
        for field_name in DATE_TARGET_FIELDS:
            if field_name not in rec:
                continue
            orig_value = _source_value_for_target(orig, field_name, mapping) or _clean(
                orig.get(field_name)
            )
            if orig_value and not _is_iso_date(rec.get(field_name)):
                validation.blocking.append(
                    Finding(
                        row=row,
                        category="invalid_date",
                        severity=BLOCKING,
                        message=(
                            f"'{field_name}' is not a valid date: "
                            f"'{rec.get(field_name) or orig_value}'"
                        ),
                        field=field_name,
                        value=str(rec.get(field_name) or orig_value),
                    )
                )

        # Amounts must be numeric and non-negative.
        for field_name in AMOUNT_TARGET_FIELDS:
            value = rec.get(field_name)
            if value is None or str(value).strip() == "":
                continue
            number = _as_number(value)
            if number is None:
                validation.blocking.append(
                    Finding(
                        row=row,
                        category="invalid_amount",
                        severity=BLOCKING,
                        message=f"'{field_name}' must be a number, got '{value}'",
                        field=field_name,
                        value=str(value),
                    )
                )
            elif number < 0:
                validation.blocking.append(
                    Finding(
                        row=row,
                        category="invalid_amount",
                        severity=BLOCKING,
                        message=f"'{field_name}' must be non-negative, got {value}",
                        field=field_name,
                        value=str(value),
                    )
                )

        # Email format.
        email = _clean(rec.get("email"))
        if email and not _EMAIL_RE.match(email):
            validation.blocking.append(
                Finding(
                    row=row,
                    category="invalid_email",
                    severity=BLOCKING,
                    message=f"'{email}' is not a valid email address",
                    field="email",
                    value=email,
                )
            )
        # Missing email on a student record → advisory, not blocking.
        if "email" in rec and not email and _is_person_row(rec):
            validation.warnings.append(
                Finding(
                    row=row,
                    category="missing_optional",
                    severity=WARNING,
                    message="Student record has no email address",
                    field="email",
                )
            )

        # Enum values that survived mapping must be in the allowed set.
        attendance_status = _clean(rec.get("attendance_status"))
        if attendance_status and attendance_status.lower() not in ATTENDANCE_STATUSES:
            validation.blocking.append(
                Finding(
                    row=row,
                    category="invalid_enum",
                    severity=BLOCKING,
                    message=(
                        f"Attendance status '{attendance_status}' is not one of "
                        "present/absent/late/excused/holiday"
                    ),
                    field="attendance_status",
                    value=attendance_status,
                )
            )
        gender = _clean(rec.get("gender"))
        if gender and gender.lower() not in GENDERS:
            validation.warnings.append(
                Finding(
                    row=row,
                    category="unknown_value",
                    severity=WARNING,
                    message=f"Gender '{gender}' is not mapped to male/female",
                    field="gender",
                    value=gender,
                )
            )

        # Orphan / conflicting references.
        number = _clean(rec.get("student_number"))
        is_attendance = bool(_clean(rec.get("attendance_date")))
        is_financial = (
            rec.get("amount_paid") is not None and str(rec.get("amount_paid")).strip() != ""
        )
        combo = (_clean(rec.get("class_name")), _clean(rec.get("section_name")))

        if (is_attendance or is_financial) and number and number not in identity:
            validation.blocking.append(
                Finding(
                    row=row,
                    category="orphan_reference",
                    severity=BLOCKING,
                    message=(
                        f"Row references student '{number}', which does not "
                        "exist in the source file"
                    ),
                    field="student_number",
                    value=number,
                )
            )
        if is_attendance and combo[0] and class_combos:
            if combo not in class_combos:
                # No student row uses this class/section → orphan structure.
                validation.blocking.append(
                    Finding(
                        row=row,
                        category="orphan_reference",
                        severity=BLOCKING,
                        message=(
                            f"Attendance row references class '{combo[0]}' "
                            f"section '{combo[1] or '-'}', which no student "
                            "row in the file uses"
                        ),
                        field="class_name",
                    )
                )
            elif number in student_combo and student_combo[number] != combo:
                known = student_combo[number]
                validation.warnings.append(
                    Finding(
                        row=row,
                        category="conflicting_reference",
                        severity=WARNING,
                        message=(
                            f"Attendance row uses class '{combo[0]}' / "
                            f"'{combo[1] or '-'}' but the student's own row "
                            f"uses '{known[0]}' / '{known[1] or '-'}'"
                        ),
                        field="class_name",
                    )
                )

    return validation
