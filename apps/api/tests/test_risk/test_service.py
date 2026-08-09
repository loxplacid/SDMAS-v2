"""Tests for the Risk & Attention Engine.

Covers:
  - every rule's detection + scoring/severity
  - config overrides (threshold changes alter findings)
  - tenant isolation (campus-scoped recompute + reads)
  - RBAC (financial findings hidden from staff/teacher)
  - audit trail (recompute, resolve, config update)
  - notifications (leadership notified of severe findings)
"""

from __future__ import annotations

import datetime
from datetime import timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academic.models import (
    AcademicYear,
    Class,
    Enrollment,
    Section,
    Subject,
    Teacher,
    TeacherAssignment,
    Term,
)
from app.domains.academic_ops.models import GradeRecord
from app.domains.admission.models import AdmissionApplication
from app.domains.attendance.models import AttendanceRecord
from app.domains.audit.models import AuditLog
from app.domains.cases.models import (  # noqa: F401 — registers cases tables for create_all
    Case,
    CaseSLAConfig,
)
from app.domains.cases.service import CaseService
from app.domains.documents.models import Document, DocumentCategory
from app.domains.fees.models import FeeDue, FeeStructure, FeeType
from app.domains.notifications.models import Notification
from app.domains.risk.models import RiskFinding, RiskRuleConfig
from app.domains.risk.rules import RULE_REGISTRY
from app.domains.risk.service import RiskService
from app.domains.student.models import Student

NOW = datetime.datetime.now(timezone.utc)
TODAY = datetime.date.today()
TODAY_ISO = TODAY.isoformat()
PAST_30 = (TODAY - datetime.timedelta(days=30)).isoformat()
PAST_60 = (TODAY - datetime.timedelta(days=60)).isoformat()


class StubUser:
    def __init__(self, role: str = "admin", user_id: int = 1, email: str = "admin@test.local"):
        self.role = role
        self.id = user_id
        self.email = email


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------


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
    cls = Class(name=f"{prefix} Grade 10", academic_year_id=year.id, campus_id=campus_id, status="active")
    db_session.add(cls)
    await db_session.flush()
    sec = Section(name=f"{prefix} A", class_id=cls.id, campus_id=campus_id, status="active")
    db_session.add(sec)
    await db_session.flush()
    subject = Subject(name=f"{prefix} Maths", code=f"{prefix.upper()}_MATH", campus_id=campus_id, status="active")
    db_session.add(subject)
    await db_session.flush()
    term1 = Term(
        academic_year_id=year.id, name=f"{prefix} Term 1",
        start_date="2026-01-01", end_date="2026-03-31", campus_id=campus_id, status="active",
    )
    term2 = Term(
        academic_year_id=year.id, name=f"{prefix} Term 2",
        start_date="2026-04-01", end_date="2026-06-30", campus_id=campus_id, status="active",
    )
    db_session.add_all([term1, term2])
    await db_session.flush()
    return {"year": year, "class": cls, "section": sec, "subject": subject, "term1": term1, "term2": term2}


async def _seed_student(db_session: AsyncSession, campus_id: int, prefix: str, n: int = 1) -> list[Student]:
    students = []
    for i in range(n):
        s = Student(
            first_name=f"{prefix}S{i}", last_name="Test",
            student_number=f"{prefix.upper()}{i:03d}", campus_id=campus_id, status="active",
        )
        db_session.add(s)
        students.append(s)
    await db_session.flush()
    return students


async def _seed_attendance(
    db_session: AsyncSession,
    campus_id: int,
    structure: dict,
    student: Student,
    *,
    days_back: int = 30,
    present_ratio: float = 1.0,
) -> None:
    """Seed daily attendance for the student. present_ratio=1.0 → all present."""
    import random

    rng = random.Random(42 + student.id)
    for offset in range(days_back, 0, -1):
        date_iso = (TODAY - datetime.timedelta(days=offset)).isoformat()
        status = "present" if rng.random() < present_ratio else "absent"
        db_session.add(
            AttendanceRecord(
                student_id=student.id, campus_id=campus_id,
                academic_year_id=structure["year"].id,
                class_id=structure["class"].id,
                section_id=structure["section"].id,
                attendance_date=date_iso, status=status,
                recorded_at=NOW, updated_at=NOW,
            )
        )
    await db_session.flush()


async def _seed_fee(
    db_session: AsyncSession,
    campus_id: int,
    structure: dict,
    student: Student,
    *,
    amount: int = 50_000_00,
    paid: int = 0,
    due_date: str | None = PAST_30,
) -> FeeDue:
    ft = FeeType(name=f"Tuition {student.id}", campus_id=campus_id, status="active")
    db_session.add(ft)
    await db_session.flush()
    fs = FeeStructure(
        academic_year_id=structure["year"].id, class_id=structure["class"].id,
        fee_type_id=ft.id, campus_id=campus_id, amount=amount,
        frequency="annual", status="active",
    )
    db_session.add(fs)
    await db_session.flush()
    due = FeeDue(
        student_id=student.id, academic_year_id=structure["year"].id,
        fee_structure_id=fs.id, original_amount=amount, campus_id=campus_id,
        amount_paid=paid, due_date=due_date, status="unpaid" if paid < amount else "paid",
    )
    db_session.add(due)
    await db_session.flush()
    return due


async def _seed_grade(
    db_session: AsyncSession,
    campus_id: int,
    structure: dict,
    student: Student,
    *,
    marks: float = 90.0,
    max_marks: int = 100,
    term=None,
) -> None:
    # Reuse an existing enrollment for this student + year (unique constraint).
    existing = (
        await db_session.execute(
            select(Enrollment).where(
                Enrollment.student_id == student.id,
                Enrollment.academic_year_id == structure["year"].id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = Enrollment(
            student_id=student.id, academic_year_id=structure["year"].id,
            class_id=structure["class"].id, section_id=structure["section"].id,
            campus_id=campus_id, status="active", enrolled_at=NOW,
        )
        db_session.add(existing)
        await db_session.flush()
    db_session.add(
        GradeRecord(
            enrollment_id=existing.id, subject_id=structure["subject"].id,
            marks_obtained=marks, max_marks=max_marks, grade="A",
            term_id=term.id if term else structure["term1"].id,
            campus_id=campus_id, status="active",
        )
    )
    await db_session.flush()


async def _seed_document_category(db_session: AsyncSession, code: str) -> DocumentCategory:
    cat = DocumentCategory(
        code=code, name=code.replace("_", " "),
        allowed_roles=["admin", "staff"], owner_type="student", is_active=True,
    )
    db_session.add(cat)
    await db_session.flush()
    return cat


@pytest.fixture
async def seeded(db_session: AsyncSession):
    structure = await _seed_structure(db_session, 1, "A")
    students = await _seed_student(db_session, 1, "A", n=3)
    return {"structure": structure, "students": students}


async def _seed_enrollment(
    db_session: AsyncSession,
    structure: dict,
    student: Student,
    campus_id: int = 1,
) -> Enrollment:
    existing = (
        await db_session.execute(
            select(Enrollment).where(
                Enrollment.student_id == student.id,
                Enrollment.academic_year_id == structure["year"].id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = Enrollment(
            student_id=student.id, academic_year_id=structure["year"].id,
            class_id=structure["class"].id, section_id=structure["section"].id,
            campus_id=campus_id, status="active", enrolled_at=NOW,
        )
        db_session.add(existing)
        await db_session.flush()
    return existing


async def _seed_teacher(
    db_session: AsyncSession,
    campus_id: int = 1,
    prefix: str = "T",
) -> Teacher:
    t = Teacher(
        first_name=f"{prefix}each", last_name="Prof",
        employee_number=f"{prefix.upper()}E001", email=f"{prefix.lower()}@test.local",
        campus_id=campus_id, status="active",
    )
    db_session.add(t)
    await db_session.flush()
    return t


async def _assign_teacher(
    db_session: AsyncSession,
    teacher: Teacher,
    structure: dict,
    campus_id: int = 1,
    status: str = "active",
) -> TeacherAssignment:
    ta = TeacherAssignment(
        teacher_id=teacher.id, class_id=structure["class"].id,
        subject_id=structure["subject"].id, campus_id=campus_id, status=status,
    )
    db_session.add(ta)
    await db_session.flush()
    return ta


# ---------------------------------------------------------------------------
# Recompute baseline
# ---------------------------------------------------------------------------


async def _recompute(db_session: AsyncSession, campus_id=1, actor_user_id=1):
    svc = RiskService(db_session)
    return await svc.recompute(campus_id, actor_user_id=actor_user_id)


# ---------------------------------------------------------------------------
# A. Attendance rules
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_attendance_below_threshold_rule(db_session: AsyncSession, seeded):
    s = seeded["students"][0]
    # ~50% attendance over 30 days
    await _seed_attendance(db_session, 1, seeded["structure"], s, present_ratio=0.5)

    await _recompute(db_session)

    findings = (
        await db_session.execute(
            select(RiskFinding).where(
                RiskFinding.rule_code == "attendance_below_threshold",
                RiskFinding.student_id == s.id,
            )
        )
    ).scalars().all()
    assert findings, "expected low-attendance finding"
    f = findings[0]
    assert f.category == "attendance"
    assert f.severity in ("critical", "high", "medium", "low")
    assert f.score > 20
    assert "Attendance" in f.reason
    assert f.recommended_action


@pytest.mark.asyncio
async def test_attendance_above_threshold_no_finding(db_session: AsyncSession, seeded):
    s = seeded["students"][0]
    await _seed_attendance(db_session, 1, seeded["structure"], s, present_ratio=1.0)

    await _recompute(db_session)

    findings = (
        await db_session.execute(
            select(RiskFinding).where(
                RiskFinding.rule_code == "attendance_below_threshold",
                RiskFinding.student_id == s.id,
            )
        )
    ).scalars().all()
    assert findings == []


@pytest.mark.asyncio
async def test_attendance_consecutive_absences_rule(db_session: AsyncSession, seeded):
    s = seeded["students"][0]
    # 6 consecutive absences ending yesterday
    for i in range(1, 7):
        date_iso = (TODAY - datetime.timedelta(days=i)).isoformat()
        db_session.add(
            AttendanceRecord(
                student_id=s.id, campus_id=1,
                academic_year_id=seeded["structure"]["year"].id,
                class_id=seeded["structure"]["class"].id,
                section_id=seeded["structure"]["section"].id,
                attendance_date=date_iso, status="absent",
                recorded_at=NOW, updated_at=NOW,
            )
        )
    await db_session.flush()

    await _recompute(db_session)

    findings = (
        await db_session.execute(
            select(RiskFinding).where(
                RiskFinding.rule_code == "attendance_consecutive_absences",
                RiskFinding.student_id == s.id,
            )
        )
    ).scalars().all()
    assert findings
    assert "consecutive" in findings[0].reason


@pytest.mark.asyncio
async def test_attendance_declining_trend_rule(db_session: AsyncSession, seeded):
    s = seeded["students"][0]
    # Earlier window all present; recent window mostly absent → big decline
    for offset in range(40, 20, -1):
        date_iso = (TODAY - datetime.timedelta(days=offset)).isoformat()
        db_session.add(
            AttendanceRecord(
                student_id=s.id, campus_id=1,
                academic_year_id=seeded["structure"]["year"].id,
                class_id=seeded["structure"]["class"].id,
                section_id=seeded["structure"]["section"].id,
                attendance_date=date_iso, status="present",
                recorded_at=NOW, updated_at=NOW,
            )
        )
    for offset in range(20, 0, -1):
        date_iso = (TODAY - datetime.timedelta(days=offset)).isoformat()
        db_session.add(
            AttendanceRecord(
                student_id=s.id, campus_id=1,
                academic_year_id=seeded["structure"]["year"].id,
                class_id=seeded["structure"]["class"].id,
                section_id=seeded["structure"]["section"].id,
                attendance_date=date_iso, status="absent",
                recorded_at=NOW, updated_at=NOW,
            )
        )
    await db_session.flush()

    await _recompute(db_session)

    findings = (
        await db_session.execute(
            select(RiskFinding).where(
                RiskFinding.rule_code == "attendance_declining_trend",
                RiskFinding.student_id == s.id,
            )
        )
    ).scalars().all()
    assert findings
    assert "declined" in findings[0].reason


# ---------------------------------------------------------------------------
# B. Finance rules
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fees_overdue_rule(db_session: AsyncSession, seeded):
    s = seeded["students"][0]
    await _seed_fee(db_session, 1, seeded["structure"], s, paid=0, due_date=PAST_30)

    await _recompute(db_session)

    findings = (
        await db_session.execute(
            select(RiskFinding).where(
                RiskFinding.rule_code == "fees_overdue",
                RiskFinding.student_id == s.id,
            )
        )
    ).scalars().all()
    assert findings
    assert findings[0].category == "finance"
    assert "overdue" in findings[0].reason.lower()


@pytest.mark.asyncio
async def test_fees_overdue_duration_rule(db_session: AsyncSession, seeded):
    s = seeded["students"][0]
    await _seed_fee(db_session, 1, seeded["structure"], s, paid=0, due_date=PAST_60)

    await _recompute(db_session)

    findings = (
        await db_session.execute(
            select(RiskFinding).where(
                RiskFinding.rule_code == "fees_overdue_duration",
                RiskFinding.student_id == s.id,
            )
        )
    ).scalars().all()
    assert findings
    assert "overdue for" in findings[0].reason


@pytest.mark.asyncio
async def test_fees_high_outstanding_rule(db_session: AsyncSession, seeded):
    s = seeded["students"][0]
    await _seed_fee(db_session, 1, seeded["structure"], s, amount=2_000_000_00, paid=0, due_date=PAST_30)

    await _recompute(db_session)

    findings = (
        await db_session.execute(
            select(RiskFinding).where(
                RiskFinding.rule_code == "fees_high_outstanding",
                RiskFinding.student_id == s.id,
            )
        )
    ).scalars().all()
    assert findings
    assert "Outstanding balance" in findings[0].reason


@pytest.mark.asyncio
async def test_fees_paid_no_finding(db_session: AsyncSession, seeded):
    s = seeded["students"][0]
    await _seed_fee(db_session, 1, seeded["structure"], s, amount=50_000_00, paid=50_000_00, due_date=PAST_30)

    await _recompute(db_session)

    for rule in ("fees_overdue", "fees_overdue_duration", "fees_high_outstanding"):
        findings = (
            await db_session.execute(
                select(RiskFinding).where(
                    RiskFinding.rule_code == rule,
                    RiskFinding.student_id == s.id,
                )
            )
        ).scalars().all()
        assert findings == [], f"{rule} should not fire for a fully-paid due"


# ---------------------------------------------------------------------------
# C. Academic rules
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_academic_low_performance_rule(db_session: AsyncSession, seeded):
    s = seeded["students"][0]
    await _seed_grade(db_session, 1, seeded["structure"], s, marks=25.0)

    await _recompute(db_session)

    findings = (
        await db_session.execute(
            select(RiskFinding).where(
                RiskFinding.rule_code == "academic_low_performance",
                RiskFinding.student_id == s.id,
            )
        )
    ).scalars().all()
    assert findings
    assert "Average marks" in findings[0].reason


@pytest.mark.asyncio
async def test_academic_declining_performance_rule(db_session: AsyncSession, seeded):
    s = seeded["students"][0]
    await _seed_grade(db_session, 1, seeded["structure"], s, marks=90.0, term=seeded["structure"]["term1"])
    await _seed_grade(db_session, 1, seeded["structure"], s, marks=40.0, term=seeded["structure"]["term2"])

    await _recompute(db_session)

    findings = (
        await db_session.execute(
            select(RiskFinding).where(
                RiskFinding.rule_code == "academic_declining_performance",
                RiskFinding.student_id == s.id,
            )
        )
    ).scalars().all()
    assert findings
    assert "declined" in findings[0].reason


@pytest.mark.asyncio
async def test_academic_high_performance_no_finding(db_session: AsyncSession, seeded):
    s = seeded["students"][0]
    await _seed_grade(db_session, 1, seeded["structure"], s, marks=95.0)

    await _recompute(db_session)

    findings = (
        await db_session.execute(
            select(RiskFinding).where(
                RiskFinding.rule_code == "academic_low_performance",
                RiskFinding.student_id == s.id,
            )
        )
    ).scalars().all()
    assert findings == []


# ---------------------------------------------------------------------------
# D. Documents rule
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_documents_missing_required_rule(db_session: AsyncSession, seeded):
    s = seeded["students"][0]
    await _seed_document_category(db_session, "birth_certificate")

    await _recompute(db_session)

    findings = (
        await db_session.execute(
            select(RiskFinding).where(
                RiskFinding.rule_code == "documents_missing_required",
                RiskFinding.student_id == s.id,
            )
        )
    ).scalars().all()
    # Students with no documents at all are flagged
    assert findings


@pytest.mark.asyncio
async def test_documents_present_no_finding(db_session: AsyncSession, seeded):
    s = seeded["students"][0]
    # Both required categories must be present for a clean slate.
    for code in ("birth_certificate", "admission_form"):
        cat = await _seed_document_category(db_session, code)
        db_session.add(
            Document(
                category_id=cat.id, student_id=s.id, owner_type="student",
                original_filename=f"{code}.pdf", storage_key=f"{code}-{s.id}.pdf",
                mime_type="application/pdf", file_size=10, title=code,
                lifecycle_state="active", campus_id=1, uploaded_by=1,
            )
        )
    await db_session.flush()

    await _recompute(db_session)

    findings = (
        await db_session.execute(
            select(RiskFinding).where(
                RiskFinding.rule_code == "documents_missing_required",
                RiskFinding.student_id == s.id,
            )
        )
    ).scalars().all()
    assert findings == []


# ---------------------------------------------------------------------------
# E. Admissions rule
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admissions_stalled_rule(db_session: AsyncSession, seeded):
    stale = AdmissionApplication(
        applicant_name="Stale App", campus_id=1,
        status="application_submitted",
        created_at=NOW - datetime.timedelta(days=20),
        updated_at=NOW - datetime.timedelta(days=20),
    )
    fresh = AdmissionApplication(
        applicant_name="Fresh App", campus_id=1,
        status="application_submitted",
        created_at=NOW, updated_at=NOW,
    )
    db_session.add_all([stale, fresh])
    await db_session.flush()

    await _recompute(db_session)

    findings = (
        await db_session.execute(
            select(RiskFinding).where(RiskFinding.rule_code == "admissions_stalled")
        )
    ).scalars().all()
    entity_ids = {f.entity_id for f in findings}
    assert stale.id in entity_ids
    assert fresh.id not in entity_ids


# ---------------------------------------------------------------------------
# F. Operational rule (guarded — guardians table may be absent in tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_operational_no_guardian_rule_graceful(db_session: AsyncSession, seeded):
    """Must not crash when the guardians table is absent in the test DB."""
    result = await _recompute(db_session)
    assert result["created"] >= 0


# ---------------------------------------------------------------------------
# G. Persistence / recompute semantics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recompute_closes_stale_findings(db_session: AsyncSession, seeded):
    s = seeded["students"][0]
    await _seed_fee(db_session, 1, seeded["structure"], s, paid=0, due_date=PAST_30)
    await _recompute(db_session)

    open_fees = (
        await db_session.execute(
            select(RiskFinding).where(
                RiskFinding.rule_code == "fees_overdue",
                RiskFinding.status == "open",
            )
        )
    ).scalars().all()
    assert open_fees, "overdue fee finding should be open"

    # Pay the fee, recompute → the open finding must be resolved.
    due = (
        await db_session.execute(select(FeeDue).where(FeeDue.student_id == s.id))
    ).scalar_one()
    due.amount_paid = due.original_amount
    due.status = "paid"
    await db_session.flush()

    await _recompute(db_session)

    stale = (
        await db_session.execute(
            select(RiskFinding).where(
                RiskFinding.rule_code == "fees_overdue",
                RiskFinding.student_id == s.id,
            )
        )
    ).scalars().all()
    assert all(f.status == "resolved" for f in stale)
    assert all(f.resolved_reason == "rule_no_longer_applies" for f in stale)


@pytest.mark.asyncio
async def test_recompute_is_idempotent(db_session: AsyncSession, seeded):
    s = seeded["students"][0]
    await _seed_attendance(db_session, 1, seeded["structure"], s, present_ratio=0.4)

    r1 = await _recompute(db_session)
    r2 = await _recompute(db_session)

    assert r1["created"] > 0
    assert r2["created"] == 0  # no duplicates on second run


# ---------------------------------------------------------------------------
# H. Configuration overrides
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_config_update_changes_threshold(db_session: AsyncSession, seeded):
    s = seeded["students"][0]
    # Exactly 20 present / 10 absent over 30 days → 66.7% attendance.
    for offset in range(1, 31):
        status = "present" if offset % 3 != 0 else "absent"  # 20 present, 10 absent
        db_session.add(
            AttendanceRecord(
                student_id=s.id, campus_id=1,
                academic_year_id=seeded["structure"]["year"].id,
                class_id=seeded["structure"]["class"].id,
                section_id=seeded["structure"]["section"].id,
                attendance_date=(TODAY - datetime.timedelta(days=offset)).isoformat(),
                status=status, recorded_at=NOW, updated_at=NOW,
            )
        )
    await db_session.flush()

    # Default threshold 75% → 66.7% attendance is below 75 but scores only
    # (75-66.7)/75*100 ≈ 11 < MIN_FINDING_SCORE → no finding emitted.
    await _recompute(db_session)
    no_findings = (
        await db_session.execute(
            select(RiskFinding).where(
                RiskFinding.rule_code == "attendance_below_threshold",
                RiskFinding.student_id == s.id,
            )
        )
    ).scalars().all()
    assert no_findings == []

    # Raise the bar to 90% → (90-66.7)/90*100 ≈ 26 ≥ MIN_FINDING_SCORE → flagged.
    svc = RiskService(db_session)
    await svc.update_config(
        1, "attendance_below_threshold",
        thresholds={"min_percentage": 90.0},
        actor_user_id=1,
    )
    await _recompute(db_session)

    flagged = (
        await db_session.execute(
            select(RiskFinding).where(
                RiskFinding.rule_code == "attendance_below_threshold",
                RiskFinding.student_id == s.id,
            )
        )
    ).scalars().all()
    assert flagged


@pytest.mark.asyncio
async def test_config_disable_rule(db_session: AsyncSession, seeded):
    s = seeded["students"][0]
    await _seed_attendance(db_session, 1, seeded["structure"], s, present_ratio=0.4)

    svc = RiskService(db_session)
    await svc.update_config(1, "attendance_below_threshold", enabled=False, actor_user_id=1)
    await _recompute(db_session)

    findings = (
        await db_session.execute(
            select(RiskFinding).where(
                RiskFinding.rule_code == "attendance_below_threshold",
                RiskFinding.student_id == s.id,
            )
        )
    ).scalars().all()
    assert findings == []


# ---------------------------------------------------------------------------
# I. Tenant isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tenant_isolation(db_session: AsyncSession):
    structure_a = await _seed_structure(db_session, 1, "A")
    sa = await _seed_student(db_session, 1, "A", n=1)
    await _seed_fee(db_session, 1, structure_a, sa[0], paid=0, due_date=PAST_30)

    structure_b = await _seed_structure(db_session, 2, "B")
    sb = await _seed_student(db_session, 2, "B", n=1)
    # Campus B has no overdue fees.

    await _recompute(db_session, campus_id=1)
    await _recompute(db_session, campus_id=2)

    svc = RiskService(db_session)
    a_findings, _ = await svc.list_findings(1, role="admin")
    b_findings, _ = await svc.list_findings(2, role="admin")

    # Campus A finds its overdue student; campus B does not see it.
    a_entities = {(f.entity_type, f.entity_id) for f in a_findings}
    b_entities = {(f.entity_type, f.entity_id) for f in b_findings}
    assert ("student", sa[0].id) in a_entities
    assert ("student", sa[0].id) not in b_entities


# ---------------------------------------------------------------------------
# J. RBAC — financial data hidden
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_staff_role_hides_finance_findings(db_session: AsyncSession, seeded):
    s = seeded["students"][0]
    await _seed_fee(db_session, 1, seeded["structure"], s, paid=0, due_date=PAST_30)
    await _recompute(db_session)

    svc = RiskService(db_session)
    staff_findings, _ = await svc.list_findings(1, role="staff")
    assert all(f.category != "finance" for f in staff_findings)

    admin_findings, _ = await svc.list_findings(1, role="admin")
    assert any(f.category == "finance" for f in admin_findings)


@pytest.mark.asyncio
async def test_overview_rbac_hides_finance_for_staff(db_session: AsyncSession, seeded):
    s = seeded["students"][0]
    await _seed_fee(db_session, 1, seeded["structure"], s, paid=0, due_date=PAST_60)
    await _recompute(db_session)

    svc = RiskService(db_session)
    staff_overview = await svc.get_overview(1, role="staff")
    admin_overview = await svc.get_overview(1, role="admin")

    # Finance findings exist overall, but staff must not see the count.
    assert admin_overview["by_category"].get("finance", 0) > 0
    assert staff_overview["by_category"].get("finance", 0) == 0
    assert "finance" not in staff_overview["by_category"]


@pytest.mark.asyncio
async def test_acknowledge_then_recompute_reopens_not_duplicates(db_session: AsyncSession, seeded):
    s = seeded["students"][0]
    await _seed_fee(db_session, 1, seeded["structure"], s, paid=0, due_date=PAST_60)
    await _recompute(db_session)

    f = (
        await db_session.execute(
            select(RiskFinding).where(
                RiskFinding.rule_code == "fees_overdue",
                RiskFinding.student_id == s.id,
            )
        )
    ).scalar_one()

    svc = RiskService(db_session)
    await svc.acknowledge_finding(f.id, 1, actor_user_id=1)
    assert f.status == "acknowledged"

    # Recompute → the acknowledged finding is reopened, not duplicated.
    await _recompute(db_session)

    rows = (
        await db_session.execute(
            select(RiskFinding).where(
                RiskFinding.rule_code == "fees_overdue",
                RiskFinding.student_id == s.id,
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "open"


@pytest.mark.asyncio
async def test_student_findings_rbac(db_session: AsyncSession, seeded):
    s = seeded["students"][0]
    await _seed_fee(db_session, 1, seeded["structure"], s, paid=0, due_date=PAST_30)
    await _recompute(db_session)

    svc = RiskService(db_session)
    staff_view = await svc.get_student_findings(s.id, 1, role="staff")
    admin_view = await svc.get_student_findings(s.id, 1, role="admin")

    assert all(f.category != "finance" for f in staff_view)
    assert any(f.category == "finance" for f in admin_view)


# ---------------------------------------------------------------------------
# K. Audit trail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_finding_writes_audit(db_session: AsyncSession, seeded):
    s = seeded["students"][0]
    await _seed_fee(db_session, 1, seeded["structure"], s, paid=0, due_date=PAST_30)
    await _recompute(db_session)

    f = (
        await db_session.execute(
            select(RiskFinding).where(
                RiskFinding.rule_code == "fees_overdue",
                RiskFinding.student_id == s.id,
            )
        )
    ).scalar_one()

    svc = RiskService(db_session)
    resolved = await svc.resolve_finding(f.id, 1, actor_user_id=7, reason="Paid in cash")
    assert resolved.status == "resolved"
    assert resolved.resolved_by == 7

    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.resource_type == "risk_finding",
                AuditLog.resource_id == str(f.id),
            )
        )
    ).scalars().all()
    assert audit
    assert audit[0].action == "RESOLVE"
    assert "Paid in cash" in (audit[0].details or "")


@pytest.mark.asyncio
async def test_recompute_writes_audit(db_session: AsyncSession, seeded):
    await _recompute(db_session)
    audit = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.resource_type == "risk_recompute")
        )
    ).scalars().all()
    assert audit
    assert audit[0].action == "RUN"


@pytest.mark.asyncio
async def test_config_update_writes_audit(db_session: AsyncSession, seeded):
    svc = RiskService(db_session)
    await svc.update_config(
        1, "attendance_below_threshold",
        thresholds={"min_percentage": 90.0},
        actor_user_id=5,
    )
    audit = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.resource_type == "risk_rule_config")
        )
    ).scalars().all()
    assert audit
    assert audit[0].action == "UPDATE"


@pytest.mark.asyncio
async def test_resolve_requires_reason(db_session: AsyncSession, seeded):
    s = seeded["students"][0]
    await _seed_fee(db_session, 1, seeded["structure"], s, paid=0, due_date=PAST_30)
    await _recompute(db_session)

    f = (
        await db_session.execute(
            select(RiskFinding).where(
                RiskFinding.rule_code == "fees_overdue",
                RiskFinding.student_id == s.id,
            )
        )
    ).scalar_one()

    svc = RiskService(db_session)
    from app.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        await svc.resolve_finding(f.id, 1, actor_user_id=1, reason="   ")


# ---------------------------------------------------------------------------
# M. Teacher dashboard findings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_teacher_sees_own_students_risks(db_session: AsyncSession, seeded):
    """Teacher with an active assignment sees findings for their students."""
    s = seeded["students"][0]
    await _seed_attendance(db_session, 1, seeded["structure"], s, present_ratio=0.4)
    await _seed_enrollment(db_session, seeded["structure"], s)
    teacher = await _seed_teacher(db_session)
    await _assign_teacher(db_session, teacher, seeded["structure"])

    await _recompute(db_session)

    svc = RiskService(db_session)
    summary = await svc.get_teacher_risk_summary(teacher.id, 1, role="teacher")
    assert summary["total"] > 0
    names = {f["student_id"] for f in summary["findings"]}
    assert s.id in names
    # Enriched with display info for the dashboard.
    assert all(f["student_name"] for f in summary["findings"])
    assert summary["by_severity"].get("high", 0) + summary["by_severity"].get("critical", 0) >= 0


@pytest.mark.asyncio
async def test_teacher_ignores_students_outside_their_classes(db_session: AsyncSession, seeded):
    """Findings only cover students enrolled in the teacher's assigned classes."""
    my_student = seeded["students"][0]
    other_student = seeded["students"][1]
    await _seed_attendance(db_session, 1, seeded["structure"], my_student, present_ratio=0.4)
    await _seed_attendance(db_session, 1, seeded["structure"], other_student, present_ratio=0.4)
    # Only my_student is enrolled in this class; other_student has no enrollment.
    await _seed_enrollment(db_session, seeded["structure"], my_student)
    teacher = await _seed_teacher(db_session)
    await _assign_teacher(db_session, teacher, seeded["structure"])

    await _recompute(db_session)

    svc = RiskService(db_session)
    summary = await svc.get_teacher_risk_summary(teacher.id, 1, role="teacher")
    student_ids = {f["student_id"] for f in summary["findings"]}
    assert my_student.id in student_ids
    assert other_student.id not in student_ids


@pytest.mark.asyncio
async def test_teacher_hides_finance_findings(db_session: AsyncSession, seeded):
    """Teacher role never sees finance/admissions findings (RBAC)."""
    s = seeded["students"][0]
    await _seed_fee(db_session, 1, seeded["structure"], s, paid=0, due_date=PAST_60)
    await _seed_enrollment(db_session, seeded["structure"], s)
    teacher = await _seed_teacher(db_session)
    await _assign_teacher(db_session, teacher, seeded["structure"])

    await _recompute(db_session)

    svc = RiskService(db_session)
    teacher_summary = await svc.get_teacher_risk_summary(teacher.id, 1, role="teacher")
    assert all(f["category"] != "finance" for f in teacher_summary["findings"])

    # Admin sees the finance finding for the same student/class.
    admin_summary = await svc.get_teacher_risk_summary(teacher.id, 1, role="admin")
    assert any(f["category"] == "finance" for f in admin_summary["findings"])


@pytest.mark.asyncio
async def test_teacher_no_assignments_returns_empty(db_session: AsyncSession, seeded):
    """Teacher without active assignments gets an empty, non-error summary."""
    s = seeded["students"][0]
    await _seed_attendance(db_session, 1, seeded["structure"], s, present_ratio=0.4)
    await _seed_enrollment(db_session, seeded["structure"], s)
    teacher = await _seed_teacher(db_session)
    # No assignment created.

    await _recompute(db_session)

    svc = RiskService(db_session)
    summary = await svc.get_teacher_risk_summary(teacher.id, 1, role="teacher")
    assert summary["total"] == 0
    assert summary["findings"] == []


@pytest.mark.asyncio
async def test_teacher_findings_tenant_isolation(db_session: AsyncSession):
    """Teacher in campus A never sees campus B students' findings."""
    structure_a = await _seed_structure(db_session, 1, "A")
    sa = await _seed_student(db_session, 1, "A", n=1)
    await _seed_attendance(db_session, 1, structure_a, sa[0], present_ratio=0.4)
    await _seed_enrollment(db_session, structure_a, sa[0], campus_id=1)
    teacher_a = await _seed_teacher(db_session, campus_id=1, prefix="A")
    await _assign_teacher(db_session, teacher_a, structure_a, campus_id=1)

    structure_b = await _seed_structure(db_session, 2, "B")
    sb = await _seed_student(db_session, 2, "B", n=1)
    await _seed_attendance(db_session, 2, structure_b, sb[0], present_ratio=0.4)
    await _seed_enrollment(db_session, structure_b, sb[0], campus_id=2)

    await _recompute(db_session, campus_id=1)
    await _recompute(db_session, campus_id=2)

    svc = RiskService(db_session)
    summary = await svc.get_teacher_risk_summary(teacher_a.id, 1, role="teacher")
    student_ids = {f["student_id"] for f in summary["findings"]}
    assert sa[0].id in student_ids
    assert sb[0].id not in student_ids


# ---------------------------------------------------------------------------
# L. P11 — closed loop: findings expose their linked operational case
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_linked_cases_for_findings(db_session: AsyncSession, seeded):
    """A finding promoted into a case exposes the case (id/number/status)
    back to the Risk Center, scoped to the campus."""
    s = seeded["students"][0]
    await _seed_attendance(db_session, 1, seeded["structure"], s, present_ratio=0.4)
    await _recompute(db_session)

    f = (
        await db_session.execute(
            select(RiskFinding).where(
                RiskFinding.rule_code == "attendance_below_threshold",
                RiskFinding.student_id == s.id,
            )
        )
    ).scalar_one()

    case_svc = CaseService(db_session)
    case = await case_svc.create_case(
        campus_id=1, actor_user_id=1, actor_name="Ada Admin",
        title="Attendance follow-up", case_type="attendance",
        source_type="risk_finding", source_id=f.id,
    )

    risk_svc = RiskService(db_session)
    linked = await risk_svc.linked_cases_for_findings(1, [f.id])
    assert linked[f.id]["case_id"] == case.id
    assert linked[f.id]["case_number"] == case.case_number
    assert linked[f.id]["case_status"] == "open"

    # A case in another campus referencing the same finding is never
    # surfaced to campus 1 (constructed directly to bypass create-time
    # source validation, which is itself campus-scoped).
    other = Case(
        case_number="DMAS-CAMPUS2", campus_id=2, title="Cross campus",
        case_type="operational", priority="low", original_priority="low",
        status="open", source_type="risk_finding", source_id=f.id,
    )
    db_session.add(other)
    await db_session.flush()

    linked_a = await risk_svc.linked_cases_for_findings(1, [f.id])
    assert linked_a[f.id]["case_id"] == case.id  # campus 1 case only
    assert linked_a[f.id]["case_number"] != "DMAS-CAMPUS2"

    # Unknown findings and empty lists are safe.
    assert await risk_svc.linked_cases_for_findings(1, []) == {}
    assert await risk_svc.linked_cases_for_findings(1, [999999]) == {}


# ---------------------------------------------------------------------------
# L. Notifications
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recompute_notifies_leadership(db_session: AsyncSession, seeded):
    from app.domains.auth.models import User

    principal = User(
        username="principal", email="principal@test.local",
        password_hash="x", display_name="P", role="principal",
        campus_id=1, is_active=True,
    )
    db_session.add(principal)
    await db_session.flush()

    s = seeded["students"][0]
    await _seed_fee(db_session, 1, seeded["structure"], s, paid=0, due_date=PAST_60)

    # Actor is a different user than the principal being notified.
    await _recompute(db_session, actor_user_id=999)

    notifications = (
        await db_session.execute(
            select(Notification).where(
                Notification.type == "risk_alert",
                Notification.user_id == principal.id,
            )
        )
    ).scalars().all()
    assert notifications
    assert any("risk finding" in n.message.lower() for n in notifications)


# ---------------------------------------------------------------------------
# P11 — single-finding deep-link (case → finding context)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_finding_rbac_and_campus_scope(db_session: AsyncSession):
    """P11 — ``get_finding`` (case → Risk Center deep-link) behaves like the
    list: campus-scoped and RBAC-category-filtered, never leaking."""
    from app.core.exceptions import NotFoundError

    f_finance = RiskFinding(
        campus_id=1, entity_type="student", entity_id=1,
        rule_code="fee_overdue", category="finance", severity="high",
        score=0.8, reason="Overdue balance", recommended_action="Review",
        status="open",
    )
    f_att = RiskFinding(
        campus_id=1, entity_type="student", entity_id=2,
        rule_code="attendance_below_threshold", category="attendance",
        severity="high", score=0.7, reason="Low attendance",
        recommended_action="Review", status="open",
    )
    f_b = RiskFinding(
        campus_id=2, entity_type="student", entity_id=3,
        rule_code="attendance_below_threshold", category="attendance",
        severity="medium", score=0.5, reason="Other campus",
        recommended_action="Review", status="open",
    )
    db_session.add_all([f_finance, f_att, f_b])
    await db_session.flush()

    svc = RiskService(db_session)

    # Admin may read finance findings.
    assert (await svc.get_finding(f_finance.id, 1, role="admin")).id == f_finance.id
    # Staff cannot see finance-category findings → treated as missing.
    with pytest.raises(NotFoundError):
        await svc.get_finding(f_finance.id, 1, role="staff")
    # Campus isolation: campus 1 cannot read a campus 2 finding.
    with pytest.raises(NotFoundError):
        await svc.get_finding(f_b.id, 1, role="admin")
    # Staff CAN read attendance findings.
    assert (await svc.get_finding(f_att.id, 1, role="staff")).id == f_att.id
    # Unknown id → 404.
    with pytest.raises(NotFoundError):
        await svc.get_finding(999999, 1, role="admin")
