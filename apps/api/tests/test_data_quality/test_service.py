"""Tests for the Data Quality Center.

Covers:
  - each deterministic check's detection logic
  - recompute persistence (upsert, idempotence, stale-close)
  - overview + overall-quality score (deterministic)
  - RBAC (financial entity types hidden from staff)
  - tenant isolation (campus-scoped scans + reads)
  - audit trail (run, resolve, ignore)
"""

from __future__ import annotations

import datetime
from datetime import timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academic.models import AcademicYear, Class, Section
from app.domains.attendance.models import AttendanceRecord
from app.domains.audit.models import AuditLog
from app.domains.data_quality.models import DataQualityFinding
from app.domains.data_quality.service import DataQualityService
from app.domains.fees.models import FeeDue, FeeStructure, FeeType, Payment
from app.domains.parent.models import Guardian
from app.domains.student.models import Student

NOW = datetime.datetime.now(timezone.utc)
TODAY = datetime.date.today()
TODAY_ISO = TODAY.isoformat()


async def _seed_structure(db_session: AsyncSession, campus_id: int, prefix: str):
    year = AcademicYear(
        name=f"{prefix} Year",
        start_date=datetime.date(2026, 1, 1),
        end_date=datetime.date(2026, 12, 31),
        campus_id=campus_id,
        status="active",
    )
    db_session.add(year)
    await db_session.flush()
    cls = Class(
        name=f"{prefix} Grade 10", academic_year_id=year.id,
        campus_id=campus_id, status="active",
    )
    db_session.add(cls)
    await db_session.flush()
    sec = Section(
        name=f"{prefix} A", class_id=cls.id, campus_id=campus_id, status="active"
    )
    db_session.add(sec)
    await db_session.flush()
    return {"year": year, "class": cls, "section": sec}


_STUDENT_SEQ = 0


async def _seed_student(
    db_session: AsyncSession,
    campus_id: int,
    prefix: str,
    *,
    n: int = 1,
    first_name: str | None = None,
    dob: datetime.date | None = None,
    email: str | None = None,
    status: str = "active",
) -> list[Student]:
    """Seed students with globally unique student numbers."""
    global _STUDENT_SEQ
    students = []
    for i in range(n):
        _STUDENT_SEQ += 1
        s = Student(
            first_name=first_name or f"{prefix}S{i}",
            last_name="Test",
            student_number=f"{prefix.upper()}{_STUDENT_SEQ:05d}",
            campus_id=campus_id,
            status=status,
            email=email,
            date_of_birth=dob,
        )
        db_session.add(s)
        students.append(s)
    await db_session.flush()
    return students


async def _seed_fee_due(
    db_session: AsyncSession,
    campus_id: int,
    structure: dict,
    student: Student,
    *,
    original: int = 50_000_00,
    paid: int = 0,
) -> FeeDue:
    ft = FeeType(name=f"Tuition {student.id}", campus_id=campus_id, status="active")
    db_session.add(ft)
    await db_session.flush()
    fs = FeeStructure(
        academic_year_id=structure["year"].id, class_id=structure["class"].id,
        fee_type_id=ft.id, campus_id=campus_id, amount=original,
        frequency="annual", status="active",
    )
    db_session.add(fs)
    await db_session.flush()
    due = FeeDue(
        student_id=student.id, academic_year_id=structure["year"].id,
        fee_structure_id=fs.id, original_amount=original, campus_id=campus_id,
        amount_paid=paid, due_date=TODAY_ISO,
        status="paid" if paid >= original else "unpaid",
    )
    db_session.add(due)
    await db_session.flush()
    return due


async def _recompute(db_session: AsyncSession, campus_id=1, actor_user_id=1):
    svc = DataQualityService(db_session)
    return await svc.recompute(campus_id, actor_user_id=actor_user_id)


# ---------------------------------------------------------------------------
# A. Check detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_duplicate_students_check(db_session: AsyncSession):
    await _seed_structure(db_session, 1, "A")
    same_dob = datetime.date(2012, 5, 10)
    await _seed_student(db_session, 1, "A", n=1, first_name="John", dob=same_dob)
    await _seed_student(db_session, 1, "A", n=1, first_name="Jon", dob=same_dob)
    await _seed_student(db_session, 1, "A", n=1, first_name="Zara", dob=datetime.date(2011, 1, 1))

    result = await _recompute(db_session)

    findings = (
        await db_session.execute(
            select(DataQualityFinding).where(
                DataQualityFinding.check_code == "duplicate_students"
            )
        )
    ).scalars().all()
    assert findings, "expected duplicate detection"
    assert findings[0].category == "duplicates"
    assert findings[0].severity == "high"
    # Zara must not be involved.
    names = [f.evidence.get("name_a") for f in findings] + [
        f.evidence.get("name_b") for f in findings
    ]
    assert all("Zara" not in (n or "") for n in names)
    assert result["created"] >= 1


@pytest.mark.asyncio
async def test_duplicate_payments_check(db_session: AsyncSession):
    structure = await _seed_structure(db_session, 1, "A")
    s = (await _seed_student(db_session, 1, "A"))[0]
    due = await _seed_fee_due(db_session, 1, structure, s)

    # Two identical completed payments = suspected duplicate entry.
    db_session.add_all(
        [
            Payment(
                student_id=s.id, fee_due_id=due.id, campus_id=1,
                amount=10_000_00, payment_date=TODAY_ISO, status="completed",
            ),
            Payment(
                student_id=s.id, fee_due_id=due.id, campus_id=1,
                amount=10_000_00, payment_date=TODAY_ISO, status="completed",
            ),
        ]
    )
    await db_session.flush()

    await _recompute(db_session)

    findings = (
        await db_session.execute(
            select(DataQualityFinding).where(
                DataQualityFinding.check_code == "duplicate_payments"
            )
        )
    ).scalars().all()
    assert findings
    assert findings[0].evidence["count"] == 2


@pytest.mark.asyncio
async def test_missing_guardian_and_email_checks(db_session: AsyncSession):
    await _seed_structure(db_session, 1, "A")
    s = (await _seed_student(db_session, 1, "A", email=None))[0]

    await _recompute(db_session)

    no_guardian = (
        await db_session.execute(
            select(DataQualityFinding).where(
                DataQualityFinding.check_code == "student_missing_guardian"
            )
        )
    ).scalars().all()
    assert no_guardian
    assert no_guardian[0].entity_id == s.id

    no_email = (
        await db_session.execute(
            select(DataQualityFinding).where(
                DataQualityFinding.check_code == "student_missing_email"
            )
        )
    ).scalars().all()
    assert no_email
    assert no_email[0].field == "email"


@pytest.mark.asyncio
async def test_guardian_present_no_finding(db_session: AsyncSession):
    await _seed_structure(db_session, 1, "A")
    s = (await _seed_student(db_session, 1, "A"))[0]
    db_session.add(Guardian(user_id=1, student_id=s.id, relationship="parent"))
    await db_session.flush()

    await _recompute(db_session)

    findings = (
        await db_session.execute(
            select(DataQualityFinding).where(
                DataQualityFinding.check_code == "student_missing_guardian"
            )
        )
    ).scalars().all()
    assert findings == []


@pytest.mark.asyncio
async def test_invalid_email_and_impossible_dob(db_session: AsyncSession):
    await _seed_structure(db_session, 1, "A")
    await _seed_student(
        db_session, 1, "A",
        n=1, email="not-an-email", dob=datetime.date(2050, 1, 1),
    )

    await _recompute(db_session)

    invalid_email = (
        await db_session.execute(
            select(DataQualityFinding).where(
                DataQualityFinding.check_code == "student_invalid_email"
            )
        )
    ).scalars().all()
    assert invalid_email
    assert invalid_email[0].severity == "low"

    bad_dob = (
        await db_session.execute(
            select(DataQualityFinding).where(
                DataQualityFinding.check_code == "student_impossible_dob"
            )
        )
    ).scalars().all()
    assert bad_dob
    assert bad_dob[0].severity == "high"


@pytest.mark.asyncio
async def test_attendance_future_date_and_invalid_status(db_session: AsyncSession):
    structure = await _seed_structure(db_session, 1, "A")
    s = (await _seed_student(db_session, 1, "A"))[0]
    db_session.add(
        AttendanceRecord(
            student_id=s.id, campus_id=1, academic_year_id=structure["year"].id,
            class_id=structure["class"].id, section_id=structure["section"].id,
            attendance_date=(TODAY + datetime.timedelta(days=5)).isoformat(),
            status="present", recorded_at=NOW, updated_at=NOW,
        )
    )
    db_session.add(
        AttendanceRecord(
            student_id=s.id, campus_id=1, academic_year_id=structure["year"].id,
            class_id=structure["class"].id, section_id=structure["section"].id,
            attendance_date=TODAY_ISO,
            status="weird-status", recorded_at=NOW, updated_at=NOW,
        )
    )
    await db_session.flush()

    await _recompute(db_session)

    future = (
        await db_session.execute(
            select(DataQualityFinding).where(
                DataQualityFinding.check_code == "attendance_future_date"
            )
        )
    ).scalars().all()
    assert future
    assert future[0].severity == "high"

    invalid = (
        await db_session.execute(
            select(DataQualityFinding).where(
                DataQualityFinding.check_code == "attendance_invalid_status"
            )
        )
    ).scalars().all()
    assert invalid
    assert "weird-status" in invalid[0].description


# ---------------------------------------------------------------------------
# B. Recompute persistence semantics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recompute_is_idempotent(db_session: AsyncSession):
    await _seed_structure(db_session, 1, "A")
    await _seed_student(db_session, 1, "A", email=None)

    r1 = await _recompute(db_session)
    r2 = await _recompute(db_session)

    assert r1["created"] > 0
    assert r2["created"] == 0  # no duplicates on the second run


@pytest.mark.asyncio
async def test_recompute_closes_stale_findings(db_session: AsyncSession):
    await _seed_structure(db_session, 1, "A")
    s = (await _seed_student(db_session, 1, "A", email=None))[0]

    await _recompute(db_session)
    open_findings = (
        await db_session.execute(
            select(DataQualityFinding).where(
                DataQualityFinding.status == "open"
            )
        )
    ).scalars().all()
    assert open_findings, "missing-email finding should be open"

    # Fix the email, recompute → stale open finding resolves itself.
    s.email = "fixed@test.local"
    await db_session.flush()
    await _recompute(db_session)

    stale = (
        await db_session.execute(
            select(DataQualityFinding).where(
                DataQualityFinding.check_code == "student_missing_email"
            )
        )
    ).scalars().all()
    assert stale
    assert all(f.status == "resolved" for f in stale)
    assert all(f.resolved_reason == "rule_no_longer_applies" for f in stale)


@pytest.mark.asyncio
async def test_recompute_keeps_history_never_deletes(db_session: AsyncSession):
    await _seed_structure(db_session, 1, "A")
    s = (await _seed_student(db_session, 1, "A", email=None))[0]

    await _recompute(db_session)
    s.email = "fixed@test.local"
    await db_session.flush()
    await _recompute(db_session)

    rows = (
        await db_session.execute(
            select(DataQualityFinding).where(
                DataQualityFinding.check_code == "student_missing_email"
            )
        )
    ).scalars().all()
    # The historical row is preserved as resolved — never deleted.
    assert len(rows) == 1
    assert rows[0].status == "resolved"


# ---------------------------------------------------------------------------
# C. Overview + deterministic quality score
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_overview_counts_and_quality_score(db_session: AsyncSession):
    await _seed_structure(db_session, 1, "A")
    await _seed_student(db_session, 1, "A", email=None)  # low severity

    await _recompute(db_session)

    svc = DataQualityService(db_session)
    overview = await svc.get_overview(1, role="admin")

    assert overview["total"] > 0
    assert overview["low"] >= 1
    assert overview["total_checks"] >= 1
    assert "overall_quality" in overview
    assert overview["overall_quality"] < 100.0  # penalties applied
    assert overview["overall_quality"] >= 0.0
    assert "severity_weights" in overview


@pytest.mark.asyncio
async def test_overview_clean_school_scores_100(db_session: AsyncSession):
    await _seed_structure(db_session, 1, "A")
    s = (await _seed_student(db_session, 1, "A", email="ok@test.local"))[0]
    # A fully-populated record: guardian present, valid email, sane DOB.
    db_session.add(Guardian(user_id=1, student_id=s.id, relationship="parent"))
    await db_session.flush()
    # Clean records → no findings at all.

    await _recompute(db_session)

    svc = DataQualityService(db_session)
    overview = await svc.get_overview(1, role="admin")
    assert overview["total"] == 0
    assert overview["overall_quality"] == 100.0


# ---------------------------------------------------------------------------
# D. RBAC
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_staff_hides_financial_entity_types(db_session: AsyncSession):
    structure = await _seed_structure(db_session, 1, "A")
    s = (await _seed_student(db_session, 1, "A", email=None))[0]
    due = await _seed_fee_due(db_session, 1, structure, s)
    # Two identical completed payments → a financial (payment) finding.
    db_session.add_all(
        [
            Payment(
                student_id=s.id, fee_due_id=due.id, campus_id=1,
                amount=10_000_00, payment_date=TODAY_ISO, status="completed",
            ),
            Payment(
                student_id=s.id, fee_due_id=due.id, campus_id=1,
                amount=10_000_00, payment_date=TODAY_ISO, status="completed",
            ),
        ]
    )
    await db_session.flush()

    await _recompute(db_session)

    svc = DataQualityService(db_session)
    staff_rows, _ = await svc.list_findings(1, role="staff")
    assert all(f.entity_type not in ("payment", "fee_due") for f in staff_rows)
    assert all(f.entity_type in ("student", "attendance_record", "enrollment") for f in staff_rows)

    admin_rows, _ = await svc.list_findings(1, role="admin")
    assert any(f.entity_type == "payment" for f in admin_rows)


@pytest.mark.asyncio
async def test_staff_overview_excludes_financial_counts(db_session: AsyncSession):
    structure = await _seed_structure(db_session, 1, "A")
    s = (await _seed_student(db_session, 1, "A", email=None))[0]
    due = await _seed_fee_due(db_session, 1, structure, s)
    db_session.add_all(
        [
            Payment(
                student_id=s.id, fee_due_id=due.id, campus_id=1,
                amount=10_000_00, payment_date=TODAY_ISO, status="completed",
            ),
            Payment(
                student_id=s.id, fee_due_id=due.id, campus_id=1,
                amount=10_000_00, payment_date=TODAY_ISO, status="completed",
            ),
        ]
    )
    await db_session.flush()

    await _recompute(db_session)

    svc = DataQualityService(db_session)
    admin = await svc.get_overview(1, role="admin")
    staff = await svc.get_overview(1, role="staff")

    assert admin["total"] > staff["total"]  # admin sees the payment finding too


# ---------------------------------------------------------------------------
# E. Tenant isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tenant_isolation_between_campuses(db_session: AsyncSession):
    await _seed_structure(db_session, 1, "A")
    await _seed_student(db_session, 1, "A", email=None)
    await _seed_structure(db_session, 2, "B")
    b_s = (await _seed_student(db_session, 2, "B", email="ok@test.local"))[0]
    # Campus B is fully clean (guardian present) → zero findings for it.
    db_session.add(Guardian(user_id=1, student_id=b_s.id, relationship="parent"))
    await db_session.flush()

    await _recompute(db_session, campus_id=1)
    await _recompute(db_session, campus_id=2)

    svc = DataQualityService(db_session)
    a_rows, a_total = await svc.list_findings(1, role="admin")
    b_rows, b_total = await svc.list_findings(2, role="admin")

    assert a_total > 0
    assert b_total == 0


# ---------------------------------------------------------------------------
# F. Lifecycle transitions + audit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_finding_writes_audit(db_session: AsyncSession):
    await _seed_structure(db_session, 1, "A")
    await _seed_student(db_session, 1, "A", email=None)
    await _recompute(db_session)

    f = (
        await db_session.execute(
            select(DataQualityFinding).where(
                DataQualityFinding.check_code == "student_missing_email"
            )
        )
    ).scalar_one()

    svc = DataQualityService(db_session)
    resolved = await svc.resolve_finding(f.id, 1, actor_user_id=7, reason="Email added")
    assert resolved.status == "resolved"
    assert resolved.resolved_by == 7

    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.resource_type == "data_quality_finding",
                AuditLog.resource_id == str(f.id),
            )
        )
    ).scalars().all()
    assert audit
    assert audit[0].action == "RESOLVE"
    assert "Email added" in (audit[0].details or "")


@pytest.mark.asyncio
async def test_ignore_finding_writes_audit(db_session: AsyncSession):
    await _seed_structure(db_session, 1, "A")
    await _seed_student(db_session, 1, "A", email=None)
    await _recompute(db_session)

    f = (
        await db_session.execute(
            select(DataQualityFinding).where(
                DataQualityFinding.check_code == "student_missing_email"
            )
        )
    ).scalar_one()

    svc = DataQualityService(db_session)
    ignored = await svc.ignore_finding(f.id, 1, actor_user_id=3, reason="Legacy student")
    assert ignored.status == "ignored"

    audit = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.resource_type == "data_quality_finding")
        )
    ).scalars().all()
    assert audit
    assert audit[0].action == "IGNORE"


@pytest.mark.asyncio
async def test_recompute_writes_audit(db_session: AsyncSession):
    await _seed_structure(db_session, 1, "A")
    await _recompute(db_session)
    audit = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.resource_type == "data_quality_recompute")
        )
    ).scalars().all()
    assert audit
    assert audit[0].action == "RUN"


@pytest.mark.asyncio
async def test_resolve_requires_reason(db_session: AsyncSession):
    await _seed_structure(db_session, 1, "A")
    await _seed_student(db_session, 1, "A", email=None)
    await _recompute(db_session)

    f = (
        await db_session.execute(
            select(DataQualityFinding).where(
                DataQualityFinding.check_code == "student_missing_email"
            )
        )
    ).scalar_one()

    from app.core.exceptions import ValidationError

    svc = DataQualityService(db_session)
    with pytest.raises(ValidationError):
        await svc.resolve_finding(f.id, 1, actor_user_id=1, reason="   ")


@pytest.mark.asyncio
async def test_resolve_unknown_finding_raises_not_found(db_session: AsyncSession):
    from app.core.exceptions import NotFoundError

    svc = DataQualityService(db_session)
    with pytest.raises(NotFoundError):
        await svc.resolve_finding(99999, 1, actor_user_id=1, reason="nope")


# ---------------------------------------------------------------------------
# P11 — single-finding deep-link (case → finding context)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_finding_rbac_and_campus_scope(db_session: AsyncSession):
    """P11 — ``get_finding`` (case → Data Quality deep-link) behaves like the
    list: campus-scoped and RBAC-entity-filtered, never leaking."""
    from app.core.exceptions import NotFoundError

    f_payment = DataQualityFinding(
        campus_id=1, check_code="duplicate_payments", category="duplicates",
        severity="high", entity_type="payment", entity_id=11, field="amount",
        description="Duplicate payment", status="open",
    )
    f_student = DataQualityFinding(
        campus_id=1, check_code="student_missing_email", category="missing_fields",
        severity="low", entity_type="student", entity_id=12, field="email",
        description="Missing email", status="open",
    )
    f_b = DataQualityFinding(
        campus_id=2, check_code="student_missing_email", category="missing_fields",
        severity="low", entity_type="student", entity_id=13, field="email",
        description="Other campus", status="open",
    )
    db_session.add_all([f_payment, f_student, f_b])
    await db_session.flush()

    svc = DataQualityService(db_session)
    # Admin may read financial (payment) findings.
    assert (await svc.get_finding(f_payment.id, 1, role="admin")).id == f_payment.id
    # Staff cannot see financial entity types → treated as missing.
    with pytest.raises(NotFoundError):
        await svc.get_finding(f_payment.id, 1, role="staff")
    # Campus isolation: campus 1 cannot read a campus 2 finding.
    with pytest.raises(NotFoundError):
        await svc.get_finding(f_b.id, 1, role="admin")
    # Staff CAN read student findings.
    assert (await svc.get_finding(f_student.id, 1, role="staff")).id == f_student.id
    # Unknown id → 404.
    with pytest.raises(NotFoundError):
        await svc.get_finding(999999, 1, role="admin")
