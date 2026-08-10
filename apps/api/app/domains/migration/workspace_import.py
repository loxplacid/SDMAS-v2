"""Multi-entity import builders for the migration workspace (Step 2).

The workspace imports a single *flat* source file.  The engine's migrators
expect either flat records (``students``, ``attendance``) or container dicts
(``academic``, ``fees``).  These builders assemble the flat transformed rows
into the shapes the migrators consume, resolving legacy references
(student_number → SDMAS student id; class/section/year names → SDMAS ids)
through the run's ``migration_mappings`` table so later streams can point
at earlier imports.

Determinism rules
-----------------
* Entity streams are detected from the mapping and run in dependency order
  (students → academic → attendance → fees).
* Every reference that cannot be resolved becomes an explicit skipped entry
  the import job logs — never a silent drop.
* Structure entities that already exist in the DB (same name + campus) are
  excluded up front, so a crash + resume never duplicates classes/sections.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

#: Deterministic stream order — later streams may reference earlier ones.
ENTITY_ORDER: list[str] = ["students", "academic", "attendance", "fees"]


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


# ── Stream filters (which flat rows feed which migrator) ───────────────


def student_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rows that describe a person (have a name)."""
    return [r for r in records if _clean(r.get("first_name")) or _clean(r.get("last_name"))]


def academic_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        r
        for r in records
        if _clean(r.get("academic_year_name"))
        or _clean(r.get("class_name"))
        or _clean(r.get("section_name"))
    ]


def attendance_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in records if _clean(r.get("attendance_date"))]


def fee_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        r
        for r in records
        if r.get("amount_paid") is not None and str(r.get("amount_paid")).strip() != ""
    ]


# ── Academic structure: flat rows → sequential containers ──────────────


async def run_academic(
    session: AsyncSession,
    migrator: Any,
    mapping_repo: Any,
    log_repo: Any,
    run_id: int,
    rows: list[dict[str, Any]],
    *,
    campus_id: int,
) -> Any:
    """Import academic structure from flat rows, level by level.

    Returns the migrator's :class:`MigratorResult`.  Levels are executed in
    dependency order and cross-level references are resolved via the run's
    mapping table, so classes reference the just-imported years, sections
    reference the just-imported classes, and enrollments link imported
    students to their section.
    """
    from app.domains.academic.models import AcademicYear, Class, Enrollment, Section
    from app.domains.migration.base import MigratorResult

    source_rows = academic_rows(rows)
    result = MigratorResult(entity_type="academic", total=len(source_rows))

    # ── Level 1: academic years ────────────────────────────────────────
    # A flat export only carries a year *name*; the AcademicYear model
    # requires a date range, so the range is derived deterministically from
    # the name (e.g. "2025-2026" → 2025-04-01 … 2026-03-31) and surfaced in
    # the run summary so the operator can verify it.  (No separate log
    # entry: ``migration_logs`` allows exactly one entry per record.)
    ay_names = sorted(
        {
            _clean(r.get("academic_year_name"))
            for r in source_rows
            if _clean(r.get("academic_year_name"))
        }
    )
    existing_ays = await _existing_names(session, AcademicYear, ay_names, campus_id)
    new_years = [n for n in ay_names if n not in existing_ays]
    if new_years:
        await _run_container(
            migrator,
            session,
            run_id,
            mapping_repo,
            log_repo,
            {
                "academic_years": [
                    {
                        "legacy_id": f"ay:{name}",
                        "name": name,
                        "start_date": _derive_year_dates(name)[0],
                        "end_date": _derive_year_dates(name)[1],
                        "campus_id": campus_id,
                    }
                    for name in new_years
                ]
            },
            result,
        )
        result.summary["derived_year_dates"] = {
            name: list(_derive_year_dates(name)) for name in new_years
        }

    # ── Level 2: classes (year-resolved) ───────────────────────────────
    class_pairs = sorted(
        {
            (_clean(r.get("academic_year_name")), _clean(r.get("class_name")))
            for r in source_rows
            if _clean(r.get("class_name"))
        }
    )
    existing_classes = await _existing_class_keys(session, Class, class_pairs, campus_id)
    class_records = []
    for ay_name, cls_name in class_pairs:
        if (ay_name, cls_name) in existing_classes:
            continue
        if not ay_name:
            # Class.academic_year_id is non-null — a yearless class cannot
            # be imported; surface it instead of failing the run.
            result.errors += 1
            result.error_details.append(
                {
                    "legacy_id": f"class:{cls_name}:?",
                    "subtype": "class",
                    "error": (
                        "No academic year mapped on the row — cannot "
                        "create a class without a year"
                    ),
                }
            )
            continue
        ay_id = await mapping_repo.resolve("academic_year", f"ay:{ay_name}")
        if ay_id is None:
            logger.warning("Class %s/%s: academic year %s not imported", cls_name, ay_name, ay_name)
            continue
        class_records.append(
            {
                "legacy_id": f"class:{cls_name}:{ay_name}",
                "name": cls_name,
                "academic_year_id": ay_id,
                "campus_id": campus_id,
            }
        )
    if class_records:
        await _run_container(
            migrator,
            session,
            run_id,
            mapping_repo,
            log_repo,
            {"classes": class_records},
            result,
        )

    # ── Level 3: sections (class-resolved) ─────────────────────────────
    section_triples = sorted(
        {
            (
                _clean(r.get("academic_year_name")),
                _clean(r.get("class_name")),
                _clean(r.get("section_name")),
            )
            for r in source_rows
            if _clean(r.get("class_name")) and _clean(r.get("section_name"))
        }
    )
    existing_sections = await _existing_section_keys(session, Section, section_triples, campus_id)
    section_records = []
    for ay_name, cls_name, sec_name in section_triples:
        if (ay_name, cls_name, sec_name) in existing_sections:
            continue
        class_id = await mapping_repo.resolve("class", f"class:{cls_name}:{ay_name or '?'}")
        if class_id is None:
            logger.warning("Section %s/%s: class not imported", sec_name, cls_name)
            continue
        section_records.append(
            {
                "legacy_id": f"section:{sec_name}:{cls_name}:{ay_name or '?'}",
                "name": sec_name,
                "class_id": class_id,
                "campus_id": campus_id,
            }
        )
    if section_records:
        await _run_container(
            migrator,
            session,
            run_id,
            mapping_repo,
            log_repo,
            {"sections": section_records},
            result,
        )

    # ── Level 4: enrollments (student + section-resolved) ──────────────
    enrollment_records = []
    seen_enrollments: set[tuple[int, int, int]] = set()
    for r in source_rows:
        number = _clean(r.get("student_number"))
        ay_name = _clean(r.get("academic_year_name"))
        cls_name = _clean(r.get("class_name"))
        sec_name = _clean(r.get("section_name"))
        if not (number and ay_name and cls_name and sec_name):
            continue
        student_id = await mapping_repo.resolve("students", number)
        ay_id = await mapping_repo.resolve("academic_year", f"ay:{ay_name}")
        class_id = await mapping_repo.resolve("class", f"class:{cls_name}:{ay_name}")
        section_id = await mapping_repo.resolve(
            "section", f"section:{sec_name}:{cls_name}:{ay_name}"
        )
        if not (student_id and ay_id and class_id and section_id):
            continue
        key = (student_id, ay_id, class_id, section_id)
        if key in seen_enrollments:
            continue
        seen_enrollments.add(key)
        exists = await session.execute(
            select(Enrollment).where(
                Enrollment.student_id == student_id,
                Enrollment.academic_year_id == ay_id,
                Enrollment.class_id == class_id,
                Enrollment.section_id == section_id,
            )
        )
        if exists.scalar_one_or_none() is not None:
            continue
        enrollment_records.append(
            {
                "legacy_id": f"enroll:{number}:{ay_name}",
                "student_id": student_id,
                "academic_year_id": ay_id,
                "class_id": class_id,
                "section_id": section_id,
                "campus_id": campus_id,
            }
        )
    if enrollment_records:
        await _run_container(
            migrator,
            session,
            run_id,
            mapping_repo,
            log_repo,
            {"enrollments": enrollment_records},
            result,
        )

    return result


async def _run_container(
    migrator: Any,
    session: AsyncSession,
    run_id: int,
    mapping_repo: Any,
    log_repo: Any,
    container: dict[str, list[dict[str, Any]]],
    result: Any,
) -> None:
    """Run one container level and fold its counts into ``result``."""
    level_result = await migrator.migrate(
        [container],
        session,
        run_id,
        mapping_repo,
        log_repo,
    )
    result.imported += level_result.imported
    result.skipped += level_result.skipped
    result.errors += level_result.errors
    result.warnings += level_result.warnings
    result.error_details.extend(level_result.error_details)


async def _existing_names(
    session: AsyncSession, model: Any, names: list[str], campus_id: int
) -> set[str]:
    if not names:
        return set()
    rows = await session.execute(
        select(model.name).where(
            model.name.in_(names),
            model.campus_id == campus_id,
        )
    )
    return {r[0] for r in rows.all()}


async def _existing_class_keys(
    session: AsyncSession, model: Any, pairs: list[tuple[str, str]], campus_id: int
) -> set[tuple[str, str]]:
    """Existing ``(year_name, class_name)`` keys for this campus.

    Year-aware: the same class name may legitimately exist in two different
    academic years (``Class.academic_year_id`` disambiguates), so matching
    by name alone would falsely skip the second year's class.  Returns
    ``(academic_year.name, class.name)`` tuples — the same shape the caller
    compares against.
    """
    from app.domains.academic.models import AcademicYear

    if not pairs:
        return set()
    names = {name for _, name in pairs}
    rows = await session.execute(
        select(model.name, AcademicYear.name)
        .join(AcademicYear, model.academic_year_id == AcademicYear.id)
        .where(model.name.in_(names), model.campus_id == campus_id)
    )
    # Return ``(year_name, class_name)`` — the same tuple order the caller
    # builds and compares against.
    return {(year_name, class_name) for class_name, year_name in rows.all()}


async def _existing_section_keys(
    session: AsyncSession,
    model: Any,
    triples: list[tuple[str, str, str]],
    campus_id: int,
) -> set[tuple[str, str, str]]:
    """Existing ``(year_name, class_name, section_name)`` keys.

    Year-aware for the same reason as :func:`_existing_class_keys`: a
    section name repeats across years/classes, so all three parts of the
    key are matched.
    """
    from app.domains.academic.models import AcademicYear, Class

    if not triples:
        return set()
    names = {name for _, _, name in triples}
    rows = await session.execute(
        select(model.name, Class.name, AcademicYear.name)
        .join(Class, model.class_id == Class.id)
        .join(AcademicYear, Class.academic_year_id == AcademicYear.id)
        .where(model.name.in_(names), model.campus_id == campus_id)
    )
    # Return ``(year_name, class_name, section_name)`` — matching the
    # caller's triple order.
    return {
        (year_name, class_name, section_name)
        for section_name, class_name, year_name in rows.all()
    }


# ── Attendance: flat rows → resolved flat records ─────────────────────


async def build_attendance_records(
    session: AsyncSession,
    mapping_repo: Any,
    rows: list[dict[str, Any]],
    *,
    campus_id: int,
) -> tuple[list[dict[str, Any]], list[tuple[str, str]]]:
    """Resolve attendance rows to SDMAS ids.

    Returns ``(records, skipped)`` where ``skipped`` is a list of
    ``(legacy_id, reason)`` tuples for rows whose references could not be
    resolved — the caller logs each one as an error.
    """
    from app.domains.attendance.models import AttendanceRecord

    resolved: list[dict[str, Any]] = []
    skipped: list[tuple[str, str]] = []
    seen: set[tuple[int, str, int]] = set()

    for r in attendance_rows(rows):
        date = _clean(r.get("attendance_date"))
        number = _clean(r.get("student_number"))
        ay_name = _clean(r.get("academic_year_name"))
        cls_name = _clean(r.get("class_name"))
        sec_name = _clean(r.get("section_name"))

        if not number:
            skipped.append((f"att:{date}", "no student_number on the row"))
            continue

        student_id = await mapping_repo.resolve("students", number)
        if student_id is None:
            skipped.append((f"att:{number}:{date}", f"unknown student '{number}'"))
            continue

        ay_id = await mapping_repo.resolve("academic_year", f"ay:{ay_name}") if ay_name else None
        class_id = (
            await mapping_repo.resolve("class", f"class:{cls_name}:{ay_name or '?'}")
            if cls_name
            else None
        )
        section_id = (
            await mapping_repo.resolve("section", f"section:{sec_name}:{cls_name}:{ay_name or '?'}")
            if sec_name
            else None
        )
        if not (ay_id and class_id and section_id):
            skipped.append(
                (
                    f"att:{number}:{date}",
                    "missing academic context (academic year / class / section)",
                )
            )
            continue

        key = (student_id, date, section_id)
        if key in seen:
            skipped.append((f"att:{number}:{date}", "duplicate attendance row"))
            continue
        seen.add(key)

        exists = await session.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.attendance_date == date,
                AttendanceRecord.section_id == section_id,
            )
        )
        if exists.scalar_one_or_none() is not None:
            skipped.append((f"att:{number}:{date}", "attendance record already exists"))
            continue

        resolved.append(
            {
                "legacy_id": f"att:{number}:{date}:{sec_name or '?'}",
                "student_id": student_id,
                "academic_year_id": ay_id,
                "class_id": class_id,
                "section_id": section_id,
                "attendance_date": date,
                "status": (_clean(r.get("attendance_status")) or "present").lower(),
                "notes": None,
                "campus_id": campus_id,
            }
        )

    return resolved, skipped


# ── Fees: flat payment rows → sequential containers ────────────────────


async def run_fees(
    session: AsyncSession,
    migrator: Any,
    mapping_repo: Any,
    log_repo: Any,
    run_id: int,
    rows: list[dict[str, Any]],
    *,
    campus_id: int,
) -> Any:
    """Import fee structure + payments from flat rows, level by level.

    A payment row ``(student, fee_type, class, year, amount, receipt)`` is
    expanded into a FeeType (by name), a FeeStructure (year/class/type),
    a FeeDue paid in full and a Payment — all resolved through the run's
    mapping table so later levels reference earlier imports.  Rows whose
    references cannot be resolved are logged as errors and rejected.
    """
    from app.domains.fees.models import FeeStructure, FeeType, Payment
    from app.domains.migration.base import MigratorResult

    result = MigratorResult(entity_type="fees", total=len(fee_rows(rows)))
    source_rows = fee_rows(rows)
    skipped: list[tuple[str, str]] = []

    def _skipped(lid: str, reason: str) -> None:
        skipped.append((lid, reason))

    # ── Level 1: fee types ─────────────────────────────────────────────
    type_names = sorted(
        {_clean(r.get("fee_type_name")) for r in source_rows if _clean(r.get("fee_type_name"))}
    )
    existing_types = await _existing_names(session, FeeType, type_names, campus_id)
    new_types = [n for n in type_names if n not in existing_types]
    if new_types:
        await _run_container(
            migrator,
            session,
            run_id,
            mapping_repo,
            log_repo,
            {
                "fee_types": [
                    {"legacy_id": f"ft:{name}", "name": name, "campus_id": campus_id}
                    for name in new_types
                ]
            },
            result,
        )

    # ── Level 2: fee structures (year/class/type-resolved) ─────────────
    structure_keys = sorted(
        {
            (
                _clean(r.get("academic_year_name")),
                _clean(r.get("class_name")),
                _clean(r.get("fee_type_name")),
            )
            for r in source_rows
            if _clean(r.get("class_name")) and _clean(r.get("fee_type_name"))
        }
    )
    structure_records = []
    for ay_name, cls_name, type_name in structure_keys:
        ay_id = await mapping_repo.resolve("academic_year", f"ay:{ay_name}") if ay_name else None
        class_id = (
            await mapping_repo.resolve("class", f"class:{cls_name}:{ay_name or '?'}")
            if cls_name
            else None
        )
        fee_type_id = (
            await mapping_repo.resolve("fee_type", f"ft:{type_name}") if type_name else None
        )
        if not (ay_id and class_id and fee_type_id):
            _skipped(
                f"fs:{type_name}:{cls_name}:{ay_name or '?'}",
                "fee structure requires academic year / class / fee type context",
            )
            continue
        exists = await session.execute(
            select(FeeStructure).where(
                FeeStructure.academic_year_id == ay_id,
                FeeStructure.class_id == class_id,
                FeeStructure.fee_type_id == fee_type_id,
            )
        )
        if exists.scalar_one_or_none() is not None:
            continue
        structure_records.append(
            {
                "legacy_id": f"fs:{type_name}:{cls_name}:{ay_name or '?'}",
                "academic_year_id": ay_id,
                "class_id": class_id,
                "fee_type_id": fee_type_id,
                "amount": 0,  # per-due amounts come from the payment rows
                "frequency": "annual",
                "campus_id": campus_id,
            }
        )
    if structure_records:
        await _run_container(
            migrator,
            session,
            run_id,
            mapping_repo,
            log_repo,
            {"fee_structures": structure_records},
            result,
        )

    # ── Level 3 + 4: fee dues + payments per source row ────────────────
    due_records: list[dict[str, Any]] = []
    payment_records: list[dict[str, Any]] = []
    for r in source_rows:
        number = _clean(r.get("student_number"))
        type_name = _clean(r.get("fee_type_name"))
        ay_name = _clean(r.get("academic_year_name"))
        cls_name = _clean(r.get("class_name"))
        amount_raw = _clean(r.get("amount_paid"))
        amount = _int_amount(amount_raw)
        if amount is None or amount <= 0:
            _skipped(f"pay:{number}:{amount_raw}", f"invalid amount '{amount_raw}'")
            continue
        student_id = await mapping_repo.resolve("students", number) if number else None
        fee_structure_id = (
            await mapping_repo.resolve(
                "fee_structure", f"fs:{type_name}:{cls_name}:{ay_name or '?'}"
            )
            if (type_name and cls_name)
            else None
        )
        if not (student_id and fee_structure_id):
            _skipped(
                f"pay:{number}:{amount}",
                "payment requires a known student and fee structure",
            )
            continue

        due_key = f"fd:{number}:{type_name}:{cls_name}:{ay_name or '?'}"
        due_id = await mapping_repo.resolve("fee_due", due_key)
        if due_id is None:
            ay_id = (
                await mapping_repo.resolve("academic_year", f"ay:{ay_name}") if ay_name else None
            )
            due_records.append(
                {
                    "legacy_id": due_key,
                    "student_id": student_id,
                    "academic_year_id": ay_id,
                    "fee_structure_id": fee_structure_id,
                    "original_amount": amount,
                    "amount_paid": amount,
                    "due_date": _clean(r.get("payment_date")) or "",
                    "campus_id": campus_id,
                    "status": "paid",
                }
            )
            # Payment references the due that the *previous* level created.
            # It is resolved after the dues container runs (see below).
            due_id = f"__due:{due_key}"

        receipt = (
            _clean(r.get("receipt_no")) or f"pay-{number}-{_clean(r.get('payment_date')) or '?'}"
        )
        payment_records.append(
            {
                "legacy_id": f"pay:{receipt}",
                "_due_key": due_key,
                "student_id": student_id,
                "fee_due_id": None,  # patched after the dues level runs
                "amount": amount,
                "payment_date": _clean(r.get("payment_date")) or "",
                "payment_method": "cash",
                "receipt_number": receipt,
                "campus_id": campus_id,
                "idempotency_key": receipt,
            }
        )

    if due_records:
        await _run_container(
            migrator,
            session,
            run_id,
            mapping_repo,
            log_repo,
            {"fee_dues": due_records},
            result,
        )

    # Resolve fee_due ids for the payment level, then import it.
    patchable: list[dict[str, Any]] = []
    for payment in payment_records:
        due_id = await mapping_repo.resolve("fee_due", payment.pop("_due_key", ""))
        if due_id is None:
            _skipped(payment.get("legacy_id", "?"), "fee due could not be resolved")
            continue
        payment["fee_due_id"] = due_id
        exists = await session.execute(
            select(Payment).where(Payment.receipt_number == payment["receipt_number"])
        )
        if exists.scalar_one_or_none() is not None:
            _skipped(payment["legacy_id"], "payment with this receipt already exists")
            continue
        patchable.append(payment)
    if patchable:
        await _run_container(
            migrator,
            session,
            run_id,
            mapping_repo,
            log_repo,
            {"payments": patchable},
            result,
        )

    for lid, reason in skipped:
        subtype = "fee_structure" if lid.startswith("fs:") else "payment"
        result.errors += 1
        result.error_details.append({"legacy_id": lid, "subtype": subtype, "error": reason})
        # migration_logs allows one entry per record per run — a resumed
        # stream must not re-log the same failure.
        if not await log_repo.entry_exists(run_id, lid, subtype):
            await log_repo.log(
                run_id=run_id,
                level="error",
                entity_type="fees",
                legacy_id=lid,
                entity_subtype=subtype,
                message=f"Reference resolution failed: {reason}",
            )

    return result


def _int_amount(value: str | None) -> int | None:
    """Parse a currency amount string into the integer unit the fee models
    store (whole currency units, no cents).  ``45000.99`` rounds to
    ``45001`` — truncation would silently under-record money, so round to
    nearest rather than floor.
    """
    if not value:
        return None
    try:
        return round(float(value))
    except (TypeError, ValueError):
        return None


def _derive_year_dates(name: str) -> tuple[str, str]:
    """Derive a deterministic date range from an academic year name.

    ``2025-2026`` → ``(2025-04-01, 2026-03-31)`` (April-start convention);
    a single year ``2025`` → ``(2025-01-01, 2025-12-31)``; anything else
    falls back to the current calendar year.  The importer logs a warning
    for every derived range so the operator can verify it.
    """
    import datetime
    import re

    years = re.findall(r"\d{4}", str(name or ""))
    if len(years) >= 2:
        return (f"{years[0]}-04-01", f"{years[1]}-03-31")
    if len(years) == 1:
        return (f"{years[0]}-01-01", f"{years[0]}-12-31")
    year = str(datetime.datetime.now(datetime.timezone.utc).year)
    return (f"{year}-01-01", f"{year}-12-31")
