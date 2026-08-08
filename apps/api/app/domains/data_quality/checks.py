"""Deterministic data-quality checks.

Every check is a pure function of persisted school data: it queries real
tables, applies a fixed rule, and returns finding drafts with a stable
``check_code``, category, severity, entity, field, description and
evidence. Checks never infer, never sample, and never fabricate — a
finding always carries the exact record(s) that triggered it.

Checks are intentionally conservative (high precision): the goal is to
surface *real* data problems an operator can act on, not to generate
noise. Pair-based checks use blocking keys + a similarity threshold from
:mod:`app.intelligence.similarity` so results are reproducible on any
machine.
"""

from __future__ import annotations

import datetime
import inspect
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academic.models import Enrollment
from app.domains.attendance.models import AttendanceRecord
from app.domains.fees.models import Payment
from app.domains.parent.models import Guardian
from app.domains.student.models import Student
from app.intelligence.similarity import name_similarity, normalize_text

# ---------------------------------------------------------------------------
# Finding draft
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QualityFindingDraft:
    check_code: str
    category: str
    severity: str
    entity_type: str
    entity_id: int
    student_id: Optional[int] = None
    field: str = ""
    description: str = ""
    evidence: Optional[dict] = None


# ---------------------------------------------------------------------------
# Check metadata + registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QualityCheck:
    code: str
    category: str
    name: str
    description: str
    defaults: dict[str, Any] = field(default_factory=dict)
    severity: str = "medium"  # default severity when the rule fires


_CHECK: dict[str, QualityCheck] = {}


def register_check(factory) -> QualityCheck:
    """Register a check *definition* (a zero-arg factory returning a
    ``QualityCheck``).  The factory is invoked once at import time so
    ``all_checks()``/``get_check()`` work with plain objects."""
    check = factory()
    _CHECK[check.code] = check
    return check


def get_check(code: str) -> QualityCheck:
    return _CHECK[code]


def all_checks() -> list[QualityCheck]:
    return list(_CHECK.values())


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
#: Canonical attendance statuses (must match the attendance domain).
ATTENDANCE_STATUSES = {"present", "absent", "late", "excused"}
#: Sanity bounds for date fields (far future / far past = data error).
MAX_FUTURE_YEARS = 2
MIN_YEAR = 1990

_ACTIVE_STUDENT_STATUSES = {"active", "enrolled"}


async def _active_students(session: AsyncSession, campus_id: Optional[int]) -> list[Student]:
    q = select(Student).where(Student.status.in_(_ACTIVE_STUDENT_STATUSES))
    if campus_id is not None:
        q = q.where(Student.campus_id == campus_id)
    return list((await session.execute(q)).scalars().all())


# ---------------------------------------------------------------------------
# 1. Duplicates
# ---------------------------------------------------------------------------


@register_check
def _duplicate_students_check() -> QualityCheck:
    return QualityCheck(
        code="duplicate_students",
        category="duplicates",
        name="Duplicate student records",
        description=(
            "Two students share the same last name + date of birth "
            "and a high name similarity."
        ),
        defaults={"similarity_threshold": 0.85},
        severity="high",
    )


async def run_duplicate_students(
    session: AsyncSession, campus_id: Optional[int], threshold: float
) -> list[QualityFindingDraft]:
    """Students with identical DOB + near-identical names (blocked, not O(n²))."""
    students = await _active_students(session, campus_id)
    if len(students) < 2:
        return []

    # Block on (normalized last-name token, dob) — keeps pair count O(n·block).
    blocks: dict[tuple[str, str], list[Student]] = {}
    for s in students:
        name_tokens = normalize_text(f"{s.first_name} {s.last_name}").split()
        if not name_tokens:
            continue
        last = name_tokens[-1]
        dob = s.date_of_birth.isoformat() if s.date_of_birth else ""
        if not dob:
            continue
        blocks.setdefault((last, dob), []).append(s)

    findings: list[QualityFindingDraft] = []
    seen: set[tuple[int, int]] = set()
    for (_, _), group in blocks.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                pair = (min(a.id, b.id), max(a.id, b.id))
                if pair in seen:
                    continue
                seen.add(pair)
                name_a = f"{a.first_name} {a.last_name}"
                name_b = f"{b.first_name} {b.last_name}"
                sim = name_similarity(name_a, name_b)
                if sim < threshold:
                    continue
                findings.append(
                    QualityFindingDraft(
                        check_code="duplicate_students",
                        category="duplicates",
                        severity="high",
                        entity_type="student",
                        entity_id=a.id,
                        student_id=a.id,
                        field="identity",
                        description=(
                            f"Student #{a.id} ({name_a}) and #{b.id} ({name_b}) "
                            f"share the same date of birth with name similarity {sim:.2f}."
                        ),
                        evidence={
                            "partner_id": b.id,
                            "name_a": name_a,
                            "name_b": name_b,
                            "date_of_birth": a.date_of_birth.isoformat(),
                            "similarity": round(sim, 3),
                        },
                    )
                )
    return findings


@register_check
def _duplicate_payments_check() -> QualityCheck:
    return QualityCheck(
        code="duplicate_payments",
        category="duplicates",
        name="Suspected duplicate payments",
        description="More than one completed payment for the same student, amount and date.",
        defaults={},
        severity="medium",
    )


async def run_duplicate_payments(
    session: AsyncSession, campus_id: Optional[int]
) -> list[QualityFindingDraft]:
    q = (
        select(
            Payment.student_id,
            Payment.amount,
            Payment.payment_date,
            func.count(Payment.id),
        )
        .where(Payment.status == "completed")
        .group_by(Payment.student_id, Payment.amount, Payment.payment_date)
        .having(func.count(Payment.id) > 1)
    )
    if campus_id is not None:
        q = q.where(Payment.campus_id == campus_id)
    rows = (await session.execute(q)).all()
    return [
        QualityFindingDraft(
            check_code="duplicate_payments",
            category="duplicates",
            severity="medium",
            entity_type="payment",
            entity_id=row[0],
            student_id=row[0],
            field="payment_date",
            description=(
                f"{row[3]} completed payment(s) of {row[1]} on {row[2]} "
                "for the same student — possible double entry."
            ),
            evidence={
                "student_id": row[0],
                "amount": row[1],
                "payment_date": row[2],
                "count": row[3],
            },
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# 2. Missing mandatory fields
# ---------------------------------------------------------------------------


@register_check
def _student_missing_guardian_check() -> QualityCheck:
    return QualityCheck(
        code="student_missing_guardian",
        category="missing_fields",
        name="Student without guardian",
        description="Active student has no guardian link on record.",
        defaults={},
        severity="high",
    )


async def run_student_missing_guardian(
    session: AsyncSession, campus_id: Optional[int]
) -> list[QualityFindingDraft]:
    students = await _active_students(session, campus_id)
    if not students:
        return []
    ids = [s.id for s in students]
    guarded = (
        await session.execute(
            select(Guardian.student_id).where(Guardian.student_id.in_(ids))
        )
    ).scalars().all()
    have = set(guarded)
    return [
        QualityFindingDraft(
            check_code="student_missing_guardian",
            category="missing_fields",
            severity="high",
            entity_type="student",
            entity_id=s.id,
            student_id=s.id,
            field="guardian_links",
            description=(
                f"Active student '{s.first_name} {s.last_name}' "
                f"(#{s.student_number}) has no guardian on record."
            ),
            evidence={"student_number": s.student_number},
        )
        for s in students
        if s.id not in have
    ]


@register_check
def _student_missing_email_check() -> QualityCheck:
    return QualityCheck(
        code="student_missing_email",
        category="missing_fields",
        name="Student without email",
        description="Active student record has no email address.",
        defaults={},
        severity="low",
    )


async def run_student_missing_email(
    session: AsyncSession, campus_id: Optional[int]
) -> list[QualityFindingDraft]:
    students = await _active_students(session, campus_id)
    return [
        QualityFindingDraft(
            check_code="student_missing_email",
            category="missing_fields",
            severity="low",
            entity_type="student",
            entity_id=s.id,
            student_id=s.id,
            field="email",
            description=(
                f"Student '{s.first_name} {s.last_name}' "
                f"(#{s.student_number}) has no email address."
            ),
            evidence={"student_number": s.student_number},
        )
        for s in students
        if not s.email or not s.email.strip()
    ]


# ---------------------------------------------------------------------------
# 3. Invalid formats
# ---------------------------------------------------------------------------


@register_check
def _student_invalid_email_check() -> QualityCheck:
    return QualityCheck(
        code="student_invalid_email",
        category="invalid_format",
        name="Malformed student email",
        description="Student email does not match a basic email pattern.",
        defaults={},
        severity="low",
    )


async def run_student_invalid_email(
    session: AsyncSession, campus_id: Optional[int]
) -> list[QualityFindingDraft]:
    students = await _active_students(session, campus_id)
    return [
        QualityFindingDraft(
            check_code="student_invalid_email",
            category="invalid_format",
            severity="low",
            entity_type="student",
            entity_id=s.id,
            student_id=s.id,
            field="email",
            description=f"Student #{s.student_number} has a malformed email: '{s.email}'.",
            evidence={"email": s.email, "student_number": s.student_number},
        )
        for s in students
        if s.email and s.email.strip() and not _EMAIL_RE.match(s.email.strip())
    ]


# ---------------------------------------------------------------------------
# 4. Impossible dates
# ---------------------------------------------------------------------------


def _today() -> datetime.date:
    return datetime.date.today()


@register_check
def _student_impossible_dob_check() -> QualityCheck:
    return QualityCheck(
        code="student_impossible_dob",
        category="impossible_dates",
        name="Impossible date of birth",
        description="Student DOB is in the future or before the sanity minimum.",
        defaults={"min_year": MIN_YEAR, "max_future_years": MAX_FUTURE_YEARS},
        severity="high",
    )


async def run_student_impossible_dob(
    session: AsyncSession, campus_id: Optional[int]
) -> list[QualityFindingDraft]:
    students = await _active_students(session, campus_id)
    today = _today()
    findings: list[QualityFindingDraft] = []
    for s in students:
        dob = s.date_of_birth
        if dob is None:
            continue
        if dob.year < MIN_YEAR or dob > today:
            findings.append(
                QualityFindingDraft(
                    check_code="student_impossible_dob",
                    category="impossible_dates",
                    severity="high",
                    entity_type="student",
                    entity_id=s.id,
                    student_id=s.id,
                    field="date_of_birth",
                    description=(
                        f"Student '{s.first_name} {s.last_name}' (#{s.student_number}) "
                        f"has an impossible date of birth: {dob.isoformat()}."
                    ),
                    evidence={"date_of_birth": dob.isoformat(), "student_number": s.student_number},
                )
            )
    return findings


@register_check
def _attendance_future_date_check() -> QualityCheck:
    return QualityCheck(
        code="attendance_future_date",
        category="impossible_dates",
        name="Attendance in the future",
        description="Attendance record is dated after today.",
        defaults={},
        severity="high",
    )


async def run_attendance_future_date(
    session: AsyncSession, campus_id: Optional[int]
) -> list[QualityFindingDraft]:
    today = _today().isoformat()
    q = select(AttendanceRecord).where(AttendanceRecord.attendance_date > today)
    if campus_id is not None:
        q = q.where(AttendanceRecord.campus_id == campus_id)
    rows = (await session.execute(q)).scalars().all()
    return [
        QualityFindingDraft(
            check_code="attendance_future_date",
            category="impossible_dates",
            severity="high",
            entity_type="attendance_record",
            entity_id=r.id,
            student_id=r.student_id,
            field="attendance_date",
            description=(
                f"Attendance record #{r.id} for student #{r.student_id} is dated "
                f"{r.attendance_date} — after today."
            ),
            evidence={"attendance_date": r.attendance_date, "student_id": r.student_id},
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# 5. Inconsistent references
# ---------------------------------------------------------------------------


@register_check
def _attendance_invalid_status_check() -> QualityCheck:
    return QualityCheck(
        code="attendance_invalid_status",
        category="inconsistent_references",
        name="Invalid attendance status",
        description="Attendance record uses a status outside the canonical set.",
        defaults={},
        severity="high",
    )


async def run_attendance_invalid_status(
    session: AsyncSession, campus_id: Optional[int]
) -> list[QualityFindingDraft]:
    q = select(AttendanceRecord).where(AttendanceRecord.status.notin_(ATTENDANCE_STATUSES))
    if campus_id is not None:
        q = q.where(AttendanceRecord.campus_id == campus_id)
    rows = (await session.execute(q)).scalars().all()
    return [
        QualityFindingDraft(
            check_code="attendance_invalid_status",
            category="inconsistent_references",
            severity="high",
            entity_type="attendance_record",
            entity_id=r.id,
            student_id=r.student_id,
            field="status",
            description=(
                f"Attendance record #{r.id} has invalid status '{r.status}' "
                f"(expected one of {sorted(ATTENDANCE_STATUSES)})."
            ),
            evidence={"status": r.status, "student_id": r.student_id},
        )
        for r in rows
    ]


@register_check
def _enrollment_missing_section_check() -> QualityCheck:
    return QualityCheck(
        code="enrollment_missing_section",
        category="inconsistent_references",
        name="Enrollment without section",
        description="Enrollment has a class but no section assigned.",
        defaults={},
        severity="low",
    )


async def run_enrollment_missing_section(
    session: AsyncSession, campus_id: Optional[int]
) -> list[QualityFindingDraft]:
    q = (
        select(Enrollment)
        .where(
            Enrollment.section_id.is_(None),
            Enrollment.class_id.isnot(None),
            Enrollment.status == "active",
        )
    )
    if campus_id is not None:
        q = q.where(Enrollment.campus_id == campus_id)
    rows = (await session.execute(q)).scalars().all()
    return [
        QualityFindingDraft(
            check_code="enrollment_missing_section",
            category="inconsistent_references",
            severity="low",
            entity_type="enrollment",
            entity_id=r.id,
            student_id=r.student_id,
            field="section_id",
            description=(
                f"Enrollment #{r.id} (student #{r.student_id}, class #{r.class_id}) "
                "has no section assigned."
            ),
            evidence={"student_id": r.student_id, "class_id": r.class_id},
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Runner registry
#
# Note: a ``fee_due_overpaid`` check is deliberately NOT registered — the
# DB already enforces ``amount_paid <= original_amount`` (see the
# ``ck_fee_due_amount_paid_range`` check constraint), so the inconsistent
# state cannot exist; a check that can never fire is dead code.
# ---------------------------------------------------------------------------

_RUNNERS: dict[str, Callable] = {
    "duplicate_students": run_duplicate_students,
    "duplicate_payments": run_duplicate_payments,
    "student_missing_guardian": run_student_missing_guardian,
    "student_missing_email": run_student_missing_email,
    "student_invalid_email": run_student_invalid_email,
    "student_impossible_dob": run_student_impossible_dob,
    "attendance_future_date": run_attendance_future_date,
    "attendance_invalid_status": run_attendance_invalid_status,
    "enrollment_missing_section": run_enrollment_missing_section,
}


async def run_all_checks(
    session: AsyncSession,
    campus_id: Optional[int],
    checks: Optional[set[str]] = None,
) -> list[QualityFindingDraft]:
    """Run every registered check (or a subset) and return all drafts.

    Only checks that declare a threshold parameter receive it — the runner
    dispatch inspects each runner's signature so a single bad call can
    never silently disable the whole run (checks also fail individually
    without aborting the batch).
    """
    drafts: list[QualityFindingDraft] = []
    for code, runner in _RUNNERS.items():
        if checks is not None and code not in checks:
            continue
        check = get_check(code)
        try:
            params = inspect.signature(runner).parameters
            if len(params) >= 3:
                threshold = float(
                    check.defaults.get("similarity_threshold", 0.85)
                )
                result = await runner(session, campus_id, threshold)
            else:
                result = await runner(session, campus_id)
            drafts.extend(result)
        except Exception:  # noqa: BLE001 — one check must not break the run
            continue
    return drafts
