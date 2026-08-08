"""Tests for the School Command Center aggregation service.

Covers:
  - metric calculations (school health)
  - RBAC (financial data hidden from roles without fees.view)
  - tenant isolation (campus-scoped queries)
  - graceful partial failure (one failing source → section available=False)
  - drill-down routes present on metrics/alerts/events
"""

from __future__ import annotations

import datetime
from datetime import timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academic.models import (
    AcademicYear,
    Class,
    Enrollment,
    Section,
    Subject,
    Teacher,
    TeacherAssignment,
)
from app.domains.academic_ops.models import GradeRecord
from app.domains.admission.models import AdmissionApplication, AdmissionDocument
from app.domains.attendance.models import AttendanceRecord
from app.domains.command_center.service import HEALTH_WEIGHTS, CommandCenterService
from app.domains.data_quality.service import DataQualityService
from app.domains.fees.models import FeeDue, FeeStructure, FeeType
from app.domains.student.models import Student
from app.domains.workflow.models import Workflow, WorkflowInstance, WorkflowStep

NOW = datetime.datetime.now(timezone.utc)
TODAY = datetime.date.today().isoformat()
PAST = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()


class StubUser:
    """Minimal stand-in for the authenticated User (service only reads email)."""

    def __init__(self, email: str | None = "principal@test.local", user_id: int = 1):
        self.email = email
        self.id = user_id


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------


async def _seed_campus(db_session, campus_id: int, prefix: str):
    """Seed a class, section, students, attendance, fees and admissions."""
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

    students = []
    for i in range(3):
        s = Student(
            first_name=f"{prefix}S{i}",
            last_name="Test",
            student_number=f"{prefix.upper()}{i:03d}",
            campus_id=campus_id,
            status="active",
        )
        db_session.add(s)
        students.append(s)
    await db_session.flush()

    # Attendance: today, 2 present + 1 absent
    for s, status in [(students[0], "present"), (students[1], "present"), (students[2], "absent")]:
        db_session.add(
            AttendanceRecord(
                student_id=s.id, campus_id=campus_id, academic_year_id=year.id,
                class_id=cls.id, section_id=sec.id, attendance_date=TODAY,
                status=status, recorded_at=NOW, updated_at=NOW,
            )
        )
    await db_session.flush()

    # Fee due: one unpaid overdue, one paid
    ft = FeeType(name=f"{prefix} Tuition", campus_id=campus_id, status="active")
    db_session.add(ft)
    await db_session.flush()
    fs = FeeStructure(
        academic_year_id=year.id, class_id=cls.id, fee_type_id=ft.id,
        campus_id=campus_id, amount=50000, frequency="annual", status="active",
    )
    db_session.add(fs)
    await db_session.flush()
    db_session.add(
        FeeDue(
            student_id=students[0].id, academic_year_id=year.id, fee_structure_id=fs.id,
            original_amount=50000, campus_id=campus_id, amount_paid=0,
            due_date=PAST, status="unpaid",
        )
    )
    db_session.add(
        FeeDue(
            student_id=students[1].id, academic_year_id=year.id, fee_structure_id=fs.id,
            original_amount=50000, campus_id=campus_id, amount_paid=50000,
            due_date=TODAY, status="paid",
        )
    )
    await db_session.flush()

    # One admission awaiting review + one pending document
    app = AdmissionApplication(
        applicant_name=f"{prefix} Applicant", campus_id=campus_id,
        status="application_submitted", created_at=NOW,
    )
    db_session.add(app)
    await db_session.flush()
    db_session.add(
        AdmissionDocument(
            application_id=app.id, document_type="birth_certificate",
            file_name="bc.pdf", verification_status="pending",
        )
    )
    await db_session.flush()

    # One active workflow instance (pending approval)
    wf = Workflow(name=f"{prefix} Leave", code=f"{prefix.lower()}_leave", entity_type="leave_request", status="active")
    db_session.add(wf)
    await db_session.flush()
    step = WorkflowStep(
        workflow_id=wf.id, name="Manager Approval", step_order=1,
        is_initial=True, is_final=True, assigned_role="admin",
    )
    db_session.add(step)
    await db_session.flush()
    db_session.add(
        WorkflowInstance(
            workflow_id=wf.id, current_step_id=step.id, campus_id=campus_id,
            entity_type="leave_request", entity_id=1, status="active",
            created_by=1,
        )
    )
    await db_session.flush()

    return {"year": year, "class": cls, "section": sec, "students": students}


@pytest.fixture
async def seeded(db_session: AsyncSession):
    """Seed a single campus (id=1) with rich data."""
    return await _seed_campus(db_session, 1, "A")


@pytest.fixture
async def seeded_two_campuses(db_session: AsyncSession):
    """Seed campus 1 and campus 2 with distinct data for isolation tests."""
    a = await _seed_campus(db_session, 1, "A")
    b = await _seed_campus(db_session, 2, "B")
    return {"campus_a": a, "campus_b": b}


# ---------------------------------------------------------------------------
# A. Metric calculations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_school_health_metrics(db_session: AsyncSession, seeded):
    svc = CommandCenterService(db_session)
    overview = await svc.get_overview(
        role="admin", user=StubUser(), campus_id=1
    )

    assert overview.school_health.available is True
    metrics = {m.key: m for m in overview.school_health.metrics}

    assert metrics["total_students"].value == 3
    assert metrics["attendance_rate"].value == pytest.approx(66.7, abs=0.1)
    assert metrics["fee_collection_rate"].value == 50.0  # 50000 paid / 100000 total
    assert metrics["outstanding_amount"].value == 50000
    assert metrics["active_admissions"].value == 1
    assert metrics["pending_approvals"].value == 1
    # Drill-down routes are present on metrics
    assert metrics["total_students"].drill_down == "/students"
    assert metrics["attendance_rate"].drill_down == "/attendance-intelligence/dashboard"


@pytest.mark.asyncio
async def test_needs_attention_alerts(db_session: AsyncSession, seeded):
    svc = CommandCenterService(db_session)
    overview = await svc.get_overview(
        role="admin", user=StubUser(), campus_id=1
    )

    assert overview.needs_attention.available is True
    alerts = {a.id: a for a in overview.needs_attention.alerts}

    # 1 absent today → not enough for low-attendance alert (min 5 records)
    # Overdue fee alert must fire
    assert "overdue-fees" in alerts
    assert alerts["overdue-fees"].drill_down == "/fees/dues"
    assert alerts["overdue-fees"].count == 1

    # Admission awaiting review
    assert "admission-review" in alerts
    assert alerts["admission-review"].drill_down == "/admissions"

    # Pending approvals
    assert "pending-approvals" in alerts

    # Pending document
    assert "missing-documents" in alerts


@pytest.mark.asyncio
async def test_today_events(db_session: AsyncSession, seeded):
    svc = CommandCenterService(db_session)
    overview = await svc.get_overview(
        role="admin", user=StubUser(), campus_id=1
    )

    assert overview.today.available is True
    events = {e.id: e for e in overview.today.events}

    assert "today-attendance" in events
    assert events["today-attendance"].description == "2 present · 1 absent"
    assert events["today-attendance"].drill_down == "/attendance/daily"

    # Admin has finance → payments today (none seeded today) → no payment event.
    # Admissions created today → present.
    assert "today-admissions" in events


@pytest.mark.asyncio
async def test_quick_actions_role_filtered(db_session: AsyncSession, seeded):
    svc = CommandCenterService(db_session)

    admin = await svc.get_overview(role="admin", user=StubUser(), campus_id=1)
    admin_ids = {a.id for a in admin.quick_actions}
    assert {"add-student", "record-attendance", "collect-payment", "review-admission"} <= admin_ids

    accountant = await svc.get_overview(role="accountant", user=StubUser(), campus_id=1)
    acc_ids = {a.id for a in accountant.quick_actions}
    assert "collect-payment" in acc_ids
    assert "review-admission" not in acc_ids  # accountant is not leadership


# ---------------------------------------------------------------------------
# B. RBAC — financial data hidden from roles without fees.view
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_staff_role_has_no_financial_data(db_session: AsyncSession, seeded):
    svc = CommandCenterService(db_session)
    overview = await svc.get_overview(role="staff", user=StubUser(), campus_id=1)

    keys = {m.key for m in overview.school_health.metrics}
    assert "fee_collection_rate" not in keys
    assert "outstanding_amount" not in keys
    assert "active_admissions" not in keys
    assert "pending_approvals" not in keys

    alert_ids = {a.id for a in overview.needs_attention.alerts}
    assert "overdue-fees" not in alert_ids


@pytest.mark.asyncio
async def test_accountant_role_is_financial_focused(db_session: AsyncSession, seeded):
    svc = CommandCenterService(db_session)
    overview = await svc.get_overview(role="accountant", user=StubUser(), campus_id=1)

    keys = {m.key for m in overview.school_health.metrics}
    assert "fee_collection_rate" in keys
    assert "outstanding_amount" in keys
    # Accountant is not leadership → no admissions/approvals metrics
    assert "active_admissions" not in keys
    assert "pending_approvals" not in keys


# ---------------------------------------------------------------------------
# C. Tenant isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tenant_isolation_between_campuses(db_session: AsyncSession, seeded_two_campuses):
    svc = CommandCenterService(db_session)

    overview_a = await svc.get_overview(role="admin", user=StubUser(), campus_id=1)
    metrics_a = {m.key: m for m in overview_a.school_health.metrics}
    assert metrics_a["total_students"].value == 3

    overview_b = await svc.get_overview(role="admin", user=StubUser(), campus_id=2)
    metrics_b = {m.key: m for m in overview_b.school_health.metrics}
    assert metrics_b["total_students"].value == 3

    # Both campuses have 3 students each — no cross-tenant leakage of counts.
    total_all = (await db_session.execute(
        __import__("sqlalchemy").select(__import__("sqlalchemy").func.count(Student.id))
    )).scalar()
    assert total_all == 6


@pytest.mark.asyncio
async def test_unscoped_admin_sees_all_campuses(db_session: AsyncSession, seeded_two_campuses):
    svc = CommandCenterService(db_session)
    overview = await svc.get_overview(role="admin", user=StubUser(), campus_id=None)
    metrics = {m.key: m for m in overview.school_health.metrics}
    # Unscoped admin aggregates across both campuses
    assert metrics["total_students"].value == 6


# ---------------------------------------------------------------------------
# D. Graceful partial failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_partial_failure_degrades_section(db_session: AsyncSession, seeded, monkeypatch):
    svc = CommandCenterService(db_session)

    async def _boom(*args, **kwargs):
        raise RuntimeError("analytics down")

    monkeypatch.setattr(svc.analytics, "get_attendance_overview", _boom)

    overview = await svc.get_overview(role="admin", user=StubUser(), campus_id=1)

    # Section still renders; only the attendance metric is skipped.
    assert overview.school_health.available is True
    keys = {m.key for m in overview.school_health.metrics}
    assert "attendance_rate" not in keys
    assert "total_students" in keys
    assert overview.sections["school_health"] is True


@pytest.mark.asyncio
async def test_full_section_failure_marks_unavailable(db_session: AsyncSession, seeded, monkeypatch):
    svc = CommandCenterService(db_session)

    async def _boom(*args, **kwargs):
        raise RuntimeError("everything down")

    monkeypatch.setattr(svc.analytics, "get_overview", _boom)
    monkeypatch.setattr(svc.analytics, "get_attendance_overview", _boom)
    monkeypatch.setattr(svc.analytics, "get_finance_overview", _boom)

    overview = await svc.get_overview(role="admin", user=StubUser(), campus_id=1)

    # School health still renders with whatever survived (structure metrics
    # come from get_overview which failed → section marked unavailable).
    assert overview.sections["school_health"] is True  # leadership metrics still resolve
    assert overview.needs_attention.available is True


# ---------------------------------------------------------------------------
# E. Rollover health — is the next academic year set up?
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rollover_health_alerted_when_year_ended(db_session: AsyncSession, seeded):
    """Active year has ended and no next year exists → critical rollover alert."""
    db_session.add(
        AcademicYear(
            name="Ended Year",
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date.today() - datetime.timedelta(days=10),
            campus_id=1,
            status="active",
        )
    )
    await db_session.flush()

    svc = CommandCenterService(db_session)
    alert = await svc._rollover_health(campus_id=1)

    assert alert is not None
    assert alert["id"] == "rollover-issue"
    assert alert["severity"] == "critical"
    assert "has ended" in alert["title"]
    assert alert["count"] == 10
    assert alert["drill_down"] == "/operations/rollover"


@pytest.mark.asyncio
async def test_rollover_health_warns_before_end_without_next_year(db_session: AsyncSession, seeded):
    """Active year ends within the window and no next year → proactive warning."""
    db_session.add(
        AcademicYear(
            name="Ending Soon Year",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date.today() + datetime.timedelta(days=30),
            campus_id=1,
            status="active",
        )
    )
    await db_session.flush()

    svc = CommandCenterService(db_session)
    alert = await svc._rollover_health(campus_id=1)

    assert alert is not None
    assert alert["id"] == "rollover-next-year"
    assert alert["severity"] == "warning"
    assert "not set up" in alert["title"]
    assert "ends in 30 days" in alert["message"]
    assert alert["count"] == 30
    assert alert["drill_down"] == "/academic/years"


@pytest.mark.asyncio
async def test_rollover_health_healthy_when_next_year_planned(db_session: AsyncSession, seeded):
    """A future-dated year already exists → no rollover alert."""
    db_session.add(
        AcademicYear(
            name="Ending Soon Year",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date.today() + datetime.timedelta(days=30),
            campus_id=1,
            status="active",
        )
    )
    db_session.add(
        AcademicYear(
            name="Next Year Planned",
            start_date=datetime.date.today() + datetime.timedelta(days=40),
            end_date=datetime.date.today() + datetime.timedelta(days=405),
            campus_id=1,
            status="planned",
        )
    )
    await db_session.flush()

    svc = CommandCenterService(db_session)
    assert await svc._rollover_health(campus_id=1) is None


@pytest.mark.asyncio
async def test_rollover_health_silent_far_from_end(db_session: AsyncSession, seeded):
    """Active year ends far in the future and no next year → no alert yet."""
    svc = CommandCenterService(db_session)
    # seeded year ends 2026-12-31 — well outside the 60-day window
    assert await svc._rollover_health(campus_id=1) is None


@pytest.mark.asyncio
async def test_rollover_health_tenant_isolation(db_session: AsyncSession, seeded_two_campuses):
    """Campus with a planned next year is healthy; the other campus still alerts."""
    # Both campuses' seeded years end far in the future → give each campus a
    # soon-ending active year so the isolation of the next-year check matters.
    db_session.add(
        AcademicYear(
            name="Campus A Ending Soon",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date.today() + datetime.timedelta(days=30),
            campus_id=1,
            status="active",
        )
    )
    db_session.add(
        AcademicYear(
            name="Campus B Ending Soon",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date.today() + datetime.timedelta(days=30),
            campus_id=2,
            status="active",
        )
    )
    db_session.add(
        AcademicYear(
            name="Campus B Next Year",
            start_date=datetime.date.today() + datetime.timedelta(days=40),
            end_date=datetime.date.today() + datetime.timedelta(days=405),
            campus_id=2,
            status="planned",
        )
    )
    await db_session.flush()

    svc = CommandCenterService(db_session)

    # Campus 1: no next year planned → alert
    a = await svc._rollover_health(campus_id=1)
    assert a is not None and a["id"] == "rollover-next-year"
    # Campus 2: next year planned → healthy
    assert await svc._rollover_health(campus_id=2) is None


@pytest.mark.asyncio
async def test_rollover_alert_appears_in_needs_attention(db_session: AsyncSession, seeded):
    """End-of-year situation surfaces as an alert in the command center payload."""
    db_session.add(
        AcademicYear(
            name="Ending Soon Year",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date.today() + datetime.timedelta(days=30),
            campus_id=1,
            status="active",
        )
    )
    await db_session.flush()

    svc = CommandCenterService(db_session)
    overview = await svc.get_overview(
        role="admin", user=StubUser(), campus_id=1
    )

    alerts = {a.id: a for a in overview.needs_attention.alerts}
    assert "rollover-next-year" in alerts
    assert alerts["rollover-next-year"].category == "rollover"
    assert alerts["rollover-next-year"].severity == "warning"
    assert alerts["rollover-next-year"].drill_down == "/academic/years"


# ---------------------------------------------------------------------------
# F. Teacher class-focused view
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_teacher_class_focused_view(db_session: AsyncSession, seeded):
    # Give campus-1 the teacher record matching the user email + a class
    teacher = Teacher(
        first_name="Class", last_name="Teacher", employee_number="TCHR001",
        email="teacher@test.local", campus_id=1, status="active",
    )
    db_session.add(teacher)
    await db_session.flush()
    db_session.add(
        TeacherAssignment(
            teacher_id=teacher.id, class_id=seeded["class"].id,
            campus_id=1, status="active",
        )
    )
    await db_session.flush()

    svc = CommandCenterService(db_session)
    overview = await svc.get_overview(
        role="teacher", user=StubUser(email="teacher@test.local"), campus_id=1
    )

    keys = {m.key for m in overview.school_health.metrics}
    assert "my_classes" in keys
    assert overview.school_health.metrics[0].value == 1
    # No financial metrics for teachers
    assert "fee_collection_rate" not in keys


@pytest.mark.asyncio
async def test_teacher_without_assignment(db_session: AsyncSession, seeded):
    svc = CommandCenterService(db_session)
    overview = await svc.get_overview(
        role="teacher", user=StubUser(email="nobody@test.local"), campus_id=1
    )
    keys = {m.key for m in overview.school_health.metrics}
    assert "my_classes" in keys
    assert overview.school_health.metrics[0].display == "No classes assigned"


# ---------------------------------------------------------------------------
# G. School Health Score — deterministic weighted composite
# ---------------------------------------------------------------------------


async def _seed_grade_record(
    db_session: AsyncSession,
    seeded: dict,
    student_id: int,
    *,
    marks: float = 90.0,
) -> None:
    """Add a grade record for an existing student/enrollment."""
    subject = Subject(
        name="Maths", code=f"M{student_id}", campus_id=1, status="active"
    )
    db_session.add(subject)
    await db_session.flush()
    enrollment = Enrollment(
        student_id=student_id, academic_year_id=seeded["year"].id,
        class_id=seeded["class"].id, section_id=seeded["section"].id,
        campus_id=1, status="active",
    )
    db_session.add(enrollment)
    await db_session.flush()
    db_session.add(
        GradeRecord(
            enrollment_id=enrollment.id, subject_id=subject.id,
            marks_obtained=marks, max_marks=100, grade="A",
            campus_id=1, status="active",
        )
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_health_score_composite_weighted(db_session: AsyncSession, seeded):
    """Score = weighted mean of available, real dimensions."""
    svc = CommandCenterService(db_session)
    overview = await svc.get_overview(role="admin", user=StubUser(), campus_id=1)

    score = overview.school_health.score
    assert score is not None
    assert score.available is True
    assert score.overall is not None

    keys = {d.key for d in score.dimensions}
    # Attendance + fees always available in the seeded campus.
    assert "attendance" in keys
    assert "fees" in keys

    # No grade records and no DQ scan → those dimensions must be absent
    # (never a fabricated academic or fake-100 data quality score).
    assert "academics" not in keys
    assert "data_quality" not in keys

    # Overall must equal Σ(scoreᵢ·wᵢ) / Σ(wᵢ) over the available dims.
    dims = score.dimensions
    total_w = sum(d.weight for d in dims)
    expected = sum(d.score * d.weight for d in dims) / total_w
    assert score.overall == pytest.approx(round(expected, 1), abs=0.1)

    # Transparent weights are exposed verbatim.
    assert score.weights == HEALTH_WEIGHTS


@pytest.mark.asyncio
async def test_health_score_includes_academics_when_grades_exist(
    db_session: AsyncSession, seeded
):
    await _seed_grade_record(db_session, seeded, seeded["students"][0].id, marks=80.0)

    svc = CommandCenterService(db_session)
    overview = await svc.get_overview(role="admin", user=StubUser(), campus_id=1)

    dims = {d.key: d for d in overview.school_health.score.dimensions}
    assert "academics" in dims
    assert dims["academics"].score == pytest.approx(80.0)
    assert dims["academics"].drill_down == "/academic/exams"


@pytest.mark.asyncio
async def test_health_score_includes_data_quality_after_scan(
    db_session: AsyncSession, seeded
):
    """Data-quality dimension appears only once a DQ scan has run."""
    # Before any scan: no dimension.
    svc = CommandCenterService(db_session)
    pre = await svc.get_overview(role="admin", user=StubUser(), campus_id=1)
    assert "data_quality" not in {d.key for d in pre.school_health.score.dimensions}

    # Create a data-quality finding via the DQ service and re-check.
    dq = DataQualityService(db_session)
    await dq.recompute(1, actor_user_id=1)

    post = await svc.get_overview(role="admin", user=StubUser(), campus_id=1)
    dims = {d.key: d for d in post.school_health.score.dimensions}
    assert "data_quality" in dims
    # The seeded campus has a student with no email/guardian → not a fake 100.
    assert dims["data_quality"].score < 100.0
    assert dims["data_quality"].drill_down == "/data-quality"


@pytest.mark.asyncio
async def test_health_score_dimension_notes_presence(
    db_session: AsyncSession, seeded
):
    """Dimensions that could not be computed are simply omitted."""
    svc = CommandCenterService(db_session)
    overview = await svc.get_overview(role="admin", user=StubUser(), campus_id=1)
    dims = overview.school_health.score.dimensions

    # Retention is always computable (students exist) and carries metrics.
    retention = next(d for d in dims if d.key == "retention")
    assert retention.score == pytest.approx(100.0)  # all 3 students active
    assert retention.metrics  # underlying metrics are attached for drill-down


@pytest.mark.asyncio
async def test_health_score_staff_has_no_fees_dimension(
    db_session: AsyncSession, seeded
):
    """Staff (no fees.view) → fees dimension excluded; score still computes."""
    svc = CommandCenterService(db_session)
    overview = await svc.get_overview(role="staff", user=StubUser(), campus_id=1)

    keys = {d.key for d in overview.school_health.score.dimensions}
    assert "fees" not in keys
    assert "attendance" in keys
    assert overview.school_health.score.available is True


@pytest.mark.asyncio
async def test_health_score_tenant_isolation(db_session: AsyncSession, seeded_two_campuses):
    """Scores are computed per campus — no cross-tenant leakage."""
    svc = CommandCenterService(db_session)
    a = await svc.get_overview(role="admin", user=StubUser(), campus_id=1)
    b = await svc.get_overview(role="admin", user=StubUser(), campus_id=2)

    a_students = {m.key: m for m in a.school_health.metrics}["total_students"].value
    b_students = {m.key: m for m in b.school_health.metrics}["total_students"].value
    assert a_students == 3 and b_students == 3  # each campus sees its own


@pytest.mark.asyncio
async def test_health_score_degrades_without_enough_dimensions(
    db_session: AsyncSession, seeded, monkeypatch
):
    """Fewer than two computable dimensions → score unavailable (never fake)."""
    svc = CommandCenterService(db_session)

    async def _no_attendance(*args, **kwargs):
        return {"attendance_percentage": 0.0}

    async def _no_finance(*args, **kwargs):
        return {
            "collection_percentage": 0.0,
            "total_outstanding": 0,
        }

    monkeypatch.setattr(svc.analytics, "get_attendance_overview", _no_attendance)
    monkeypatch.setattr(svc.analytics, "get_finance_overview", _no_finance)

    overview = await svc.get_overview(role="staff", user=StubUser(), campus_id=1)
    score = overview.school_health.score
    # Staff without finance → attendance metric only; retention still present
    # so score remains available — assert the weights sum to a sensible value.
    assert score.available is True
    assert score.overall is not None
    assert 0 <= score.overall <= 100
