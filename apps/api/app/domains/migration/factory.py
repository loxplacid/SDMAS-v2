"""Migration Factory — pure pipeline stages (TASK 15).

Upgrades the existing migration workspace with the stages an enterprise
migration needs, reusing the existing discovery/mapping/validation/
reconciliation machinery.  Everything in this module is **pure and
deterministic** — no database access, no randomness — so every stage is
repeatable, explainable, and unit-testable in isolation:

- ``profile_source``   — source profiling: entity distribution, quality
  scorecard (fill rates of required targets), PII/contact columns, and
  duplicate-key candidates (DISCOVER + PROFILE)
- ``match_identity``   — deterministic legacy→SDMAS identity matching
  (exact student_number → normalized email → normalized phone → name+DOB
  → fuzzy name), returning match / no_match / ambiguous with confidence
  (IDENTITY MATCH)
- ``classify_rows``    — per-row CREATE / UPDATE / SKIP / ERROR
  classification against the target state (DRY RUN / PREVIEW)
- ``format_verification`` — source-vs-target verification report shape
  (VERIFY)

The service layer (``project_service.py``) wires these to the repository,
the target database, and the platform evidence foundation.
"""

from __future__ import annotations

import re
from typing import Any

from app.domains.migration.discovery import ENTITY_TARGETS, detect_entities
from app.intelligence.similarity import (
    jaro_winkler,
    normalize_email,
    normalize_phone,
    normalize_text,
)

#: Identity-match decisions.
MATCH_MATCHED = "match"
MATCH_NO_MATCH = "no_match"
MATCH_AMBIGUOUS = "ambiguous"

#: Confidence tiers for identity matches.
CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------------------
# Source profiling (DISCOVER + PROFILE)
# ---------------------------------------------------------------------------


def profile_source(
    records: list[dict[str, Any]],
    mapping: dict[str, Any],
) -> dict[str, Any]:
    """Build a source profile for the workspace.

    Deterministic over ``(records, mapping)``:

    - entity distribution — how many source rows carry a mapped target
      for each detected entity (a row can belong to several streams)
    - quality scorecard — fill rate of every mapped target field across
      the rows that should carry it
    - PII/contact columns — which source columns look like email, phone,
      or birth-date data
    - duplicate-key candidates — rows sharing a mapped ``student_number``
      (the importer's primary natural key)
    """
    if not records:
        return {
            "row_count": 0,
            "entities": {},
            "scorecard": {},
            "pii_columns": [],
            "duplicate_candidates": [],
        }

    targets_by_source = {
        str(source): str(spec.get("target", ""))
        for source, spec in (mapping or {}).items()
        if isinstance(spec, dict) and spec.get("target")
    }

    # Entity distribution: a row belongs to an entity when it carries at
    # least one mapped value for one of the entity's target fields.
    entity_field_targets = {entity: set(fields) for entity, fields in ENTITY_TARGETS.items()}
    entity_rows: dict[str, int] = {}
    for entity in detect_entities(mapping):
        needed = entity_field_targets.get(entity, set())
        count = 0
        for record in records:
            has = any(
                record.get(source) not in (None, "") and target in needed
                for source, target in targets_by_source.items()
            )
            if has:
                count += 1
        entity_rows[entity] = count

    # Quality scorecard: fill rate of each mapped target field.
    scorecard: dict[str, dict[str, Any]] = {}
    for source, target in targets_by_source.items():
        non_empty = 0
        for record in records:
            value = record.get(source)
            if value is not None and str(value).strip():
                non_empty += 1
        scorecard[target] = {
            "source": source,
            "filled": non_empty,
            "total": len(records),
            "fill_rate": round(non_empty / len(records), 4) if records else 0.0,
        }

    # PII/contact columns (deterministic probes over non-empty values).
    pii_columns: list[str] = []
    if records:
        names = list(records[0].keys())
        for name in names:
            values = [
                str(r.get(name))
                for r in records
                if r.get(name) not in (None, "") and str(r.get(name)).strip()
            ]
            if not values:
                continue
            probe = values[: max(1, len(values) // 2) + 1]
            if sum(1 for v in probe if _EMAIL_RE.match(v)) >= max(1, len(probe) // 2):
                pii_columns.append(name)  # email
            elif re.match(r"^\+?[\d\s\-().]{7,}$", probe[0]):
                pii_columns.append(name)  # phone
            elif re.match(
                r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$|^\d{1,2}[-/]\d{1,2}[-/]\d{4}$",
                probe[0],
            ):
                pii_columns.append(name)  # date

    # Duplicate-key candidates on the mapped student_number column.
    duplicate_candidates: list[dict[str, Any]] = []
    number_source = next(
        (source for source, target in targets_by_source.items() if target == "student_number"),
        None,
    )
    if number_source:
        seen: dict[str, list[int]] = {}
        for index, record in enumerate(records, start=1):
            value = record.get(number_source)
            key = str(value).strip() if value is not None else ""
            if key:
                seen.setdefault(key, []).append(index)
        for key, rows in seen.items():
            if len(rows) > 1:
                duplicate_candidates.append({"value": key, "rows": rows})

    return {
        "row_count": len(records),
        "entities": entity_rows,
        "scorecard": scorecard,
        "pii_columns": pii_columns,
        "duplicate_candidates": duplicate_candidates,
    }


# ---------------------------------------------------------------------------
# Identity matching (IDENTITY MATCH)
# ---------------------------------------------------------------------------


def match_identity(
    transformed: list[dict[str, Any]],
    existing_students: list[dict[str, Any]],
) -> dict[str, Any]:
    """Match every transformed row against existing SDMAS students.

    Deterministic matching ladder (first hit wins):

    1. ``student_number`` exact (case/space folded)         → high
    2. ``email`` normalized exact                           → high
    3. ``guardian_phone`` normalized exact                  → medium
    4. first + last name AND date-of-birth exact            → medium
    5. full-name fuzzy (Jaro-Winkler >= 0.94)               → low

    More than one candidate at any tier → ``ambiguous``.  Rows with no
    matching student are ``no_match`` (they will be created).  The result
    is persisted on the project so the operator can review and correct.
    """
    rows: list[dict[str, Any]] = []
    matched = no_match = ambiguous = 0

    by_number: dict[str, list[dict[str, Any]]] = {}
    by_email: dict[str, list[dict[str, Any]]] = {}
    by_phone: dict[str, list[dict[str, Any]]] = {}
    by_name_dob: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for student in existing_students:
        number = _fold(str(student.get("student_number") or ""))
        raw_email = student.get("email")
        email = normalize_email(raw_email) if raw_email else ""
        phone = normalize_phone(student.get("guardian_phone"))
        name_dob = (
            _fold(f"{student.get('first_name') or ''} {student.get('last_name') or ''}"),
            _iso_date(student.get("date_of_birth")),
        )
        if number:
            by_number.setdefault(number, []).append(student)
        if email:
            by_email.setdefault(email, []).append(student)
        if phone:
            by_phone.setdefault(phone, []).append(student)
        if name_dob[0] and name_dob[1]:
            by_name_dob.setdefault(name_dob, []).append(student)

    for index, record in enumerate(transformed, start=1):
        decision = _match_one(record, by_number, by_email, by_phone, by_name_dob)
        rows.append(
            {
                "row": index,
                "decision": decision["decision"],
                "confidence": decision["confidence"],
                "method": decision["method"],
                "sdmas_id": decision["sdmas_id"],
                "matched_name": decision["matched_name"],
                "candidates": decision["candidates"],
            }
        )
        if decision["decision"] == MATCH_MATCHED:
            matched += 1
        elif decision["decision"] == MATCH_AMBIGUOUS:
            ambiguous += 1
        else:
            no_match += 1

    return {
        "total": len(rows),
        "matched": matched,
        "no_match": no_match,
        "ambiguous": ambiguous,
        "matched_at": None,  # set by the service layer
        "rows": rows,
    }


def _match_one(
    record: dict[str, Any],
    by_number: dict[str, list[dict[str, Any]]],
    by_email: dict[str, list[dict[str, Any]]],
    by_phone: dict[str, list[dict[str, Any]]],
    by_name_dob: dict[tuple[str, str], list[dict[str, Any]]],
) -> dict[str, Any]:
    """Single-row matching ladder; returns the decision dict."""

    def _pick(candidates: list[dict[str, Any]], method: str, confidence: str) -> dict[str, Any]:
        if len(candidates) == 1:
            student = candidates[0]
            return {
                "decision": MATCH_MATCHED,
                "confidence": confidence,
                "method": method,
                "sdmas_id": student.get("id"),
                "matched_name": (
                    f"{student.get('first_name') or ''} {student.get('last_name') or ''}".strip()
                    or None
                ),
                "candidates": len(candidates),
            }
        return {
            "decision": MATCH_AMBIGUOUS,
            "confidence": confidence,
            "method": method,
            "sdmas_id": None,
            "matched_name": None,
            "candidates": len(candidates),
        }

    number = _fold(str(record.get("student_number") or ""))
    if number and number in by_number:
        return _pick(by_number[number], "student_number", CONFIDENCE_HIGH)

    raw_email = record.get("email")
    email = normalize_email(raw_email) if raw_email else ""
    if email and email in by_email:
        return _pick(by_email[email], "email", CONFIDENCE_HIGH)

    phone = normalize_phone(record.get("guardian_phone"))
    if phone and phone in by_phone:
        return _pick(by_phone[phone], "guardian_phone", CONFIDENCE_MEDIUM)

    name = _fold(f"{record.get('first_name') or ''} {record.get('last_name') or ''}")
    dob = _iso_date(record.get("date_of_birth"))
    if name and dob and (name, dob) in by_name_dob:
        return _pick(by_name_dob[(name, dob)], "name_dob", CONFIDENCE_MEDIUM)

    # Fuzzy name fallback (low confidence) — only against unique-name
    # candidates to avoid spurious hits.
    if name:
        full = f"{record.get('first_name') or ''} {record.get('last_name') or ''}".strip()
        candidates: list[dict[str, Any]] = []
        for student in _all_students(by_number, by_email, by_phone, by_name_dob):
            student_full = (
                f"{student.get('first_name') or ''} {student.get('last_name') or ''}".strip()
            )
            if student_full and jaro_winkler(full, student_full) >= 0.94:
                candidates.append(student)
        if candidates:
            return _pick(candidates, "fuzzy_name", CONFIDENCE_LOW)

    return {
        "decision": MATCH_NO_MATCH,
        "confidence": CONFIDENCE_LOW,
        "method": None,
        "sdmas_id": None,
        "matched_name": None,
        "candidates": 0,
    }


def _all_students(
    by_number: dict[str, list[dict[str, Any]]],
    by_email: dict[str, list[dict[str, Any]]],
    by_phone: dict[str, list[dict[str, Any]]],
    by_name_dob: dict[tuple[str, str], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    seen: dict[int, dict[str, Any]] = {}
    for bucket in (by_number, by_email, by_phone):
        for students in bucket.values():
            for student in students:
                if student.get("id") is not None:
                    seen[int(student["id"])] = student
    for students in by_name_dob.values():
        for student in students:
            if student.get("id") is not None:
                seen[int(student["id"])] = student
    return list(seen.values())


# ---------------------------------------------------------------------------
# Row classification (DRY RUN / PREVIEW)
# ---------------------------------------------------------------------------


def classify_rows(
    transformed: list[dict[str, Any]],
    records: list[dict[str, Any]],
    blocking_by_row: dict[int, list[str]],
    existing_numbers: set[str],
) -> list[dict[str, Any]]:
    """Classify every row CREATE / UPDATE / SKIP / ERROR against the
    current target state.

    Mirrors the workspace preview semantics but runs over the FULL set
    (the preview samples the first N rows):
    ERROR (blocking validation) → UPDATE (student exists) → CREATE →
    SKIP (no mapped target fields).
    """
    rows: list[dict[str, Any]] = []
    for i, after in enumerate(transformed):
        row_no = i + 1
        before = records[i] if i < len(records) else {}
        issues = blocking_by_row.get(row_no, [])
        if issues:
            action, reason = "ERROR", " ".join(issues)
        elif after.get("student_number") and str(after["student_number"]) in existing_numbers:
            action, reason = "UPDATE", "Student already exists in SDMAS — will be skipped"
        elif _has_mapped_target(after):
            action, reason = "CREATE", "A new record will be created"
        else:
            action, reason = "SKIP", "No mapped target fields on this row"
        rows.append(
            {
                "row": row_no,
                "before": _trim_record(before),
                "after": _trim_record(after),
                "status": "error" if issues else "ok",
                "action": action,
                "action_reason": reason,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Verification (VERIFY)
# ---------------------------------------------------------------------------


def format_verification(
    *,
    source_row_count: int,
    entities: list[str],
    counts: dict[str, dict[str, int]],
    spot_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the post-import verification report.

    ``counts`` maps entity → {source, target}; a mismatch is reported per
    entity.  ``spot_checks`` are operator-visible sample comparisons.
    """
    per_entity: list[dict[str, Any]] = []
    all_ok = True
    for entity in entities:
        row = counts.get(entity, {})
        source = row.get("source", 0)
        target = row.get("target", 0)
        ok = source == target
        all_ok = all_ok and ok
        per_entity.append(
            {
                "entity": entity,
                "source": source,
                "target": target,
                "difference": target - source,
                "ok": ok,
            }
        )
    return {
        "source_row_count": source_row_count,
        "entities": per_entity,
        "spot_checks": spot_checks,
        "passed": all_ok,
        "verified_at": None,  # set by the service layer
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fold(value: str) -> str:
    return normalize_text(value)


def _iso_date(value: Any) -> str:
    if value is None:
        return ""
    raw = str(value).strip()
    match = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", raw)
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    match = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$", raw)
    if match:
        day, month, year = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    return raw


def _trim_record(record: dict[str, Any]) -> dict[str, Any]:
    return {k: str(v)[:80] for k, v in list(record.items())[:10]}


def _has_mapped_target(record: dict[str, Any]) -> bool:
    targets = {
        "student_number",
        "first_name",
        "last_name",
        "email",
        "date_of_birth",
        "gender",
        "status",
        "guardian_phone",
        "class_name",
        "section_name",
        "academic_year_name",
        "attendance_date",
        "attendance_status",
        "amount_paid",
        "fee_type_name",
        "payment_date",
        "receipt_no",
    }
    return any(record.get(field) is not None for field in targets)


__all__ = [
    "MATCH_MATCHED",
    "MATCH_NO_MATCH",
    "MATCH_AMBIGUOUS",
    "CONFIDENCE_HIGH",
    "CONFIDENCE_MEDIUM",
    "CONFIDENCE_LOW",
    "profile_source",
    "match_identity",
    "classify_rows",
    "format_verification",
]
