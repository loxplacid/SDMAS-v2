"""Tests for the Unified Operational Timeline aggregation.

Covers:
  - aggregation across sources (audit, workflow, fees, academic, risk)
  - RBAC (finance hidden for staff/teacher, leadership-only sources)
  - tenant isolation (campus scoping + entity-scope guard)
  - filters (source, event_type, actor, date range)
  - pagination (merged, reverse-chronological)
  - entity scoping (student/class/teacher)
  - graceful partial failure (a failing source degrades, rest renders)
"""

from __future__ import annotations

import datetime
from datetime import timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from app.domains.academic.models import AcademicYear, Class, Enrollment, Section, Teacher, TeacherAssignment
from app.domains.admission.models import AdmissionApplication
from app.domains.audit.models import AuditLog
from app.domains.fees.models import FeeDue, FeeStructure, FeeType, Payment
from app.domains.notifications.models import Notification
from app.domains.risk.models import RiskFinding
from app.domains.student.models import Student
from app.domains.workflow.models import (
    ApprovalHistory,
    Workflow,
    WorkflowInstance,
    WorkflowStep,
)
from app.domains.timeline.service import TimelineFilters, TimelineService

NOW = datetime.datetime.now(timezone.utc)
TODAY = datetime.date.today()
PAST_10 = (NOW - datetime.timedelta(days=10)).isoformat()
PAST_20 = (NOW - datetime.timedelta(days=20)).isoformat()


class StubUser:
    def __init__(self, role: str = "admin", user_id: int = 1):
        self.role = role
        self.id = user_id


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
    return {"year": year, "class": cls, "section": sec}


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


async def _seed_enrollment(
    db_session: AsyncSession, structure: dict, student: Student, campus_id: int = 1,
    *, days_back: int = 5, status: str = "active",
) -> Enrollment:
    e = Enrollment(
        student_id=student.id, academic_year_id=structure["year"].id,
        class_id=structure["class"].id, section_id=structure["section"].id,
        campus_id=campus_id, status=status,
        enrolled_at=NOW - datetime.timedelta(days=days_back),
    )
    db_session.add(e)
    await db_session.flush()
    return e


async def _seed_payment(
    db_session: AsyncSession, structure: dict, student: Student,
    campus_id: int = 1, amount: int = 50_000_00,
) -> Payment:
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
        amount_paid=amount, status="paid",
    )
    db_session.add(due)
    await db_session.flush()
    p = Payment(
        student_id=student.id, fee_due_id=due.id, campus_id=campus_id,
        amount=amount, payment_date=TODAY.isoformat(),
        payment_method="cash", receipt_number=f"RCP-{student.id}",
        created_at=NOW - datetime.timedelta(days=2),
    )
    db_session.add(p)
    await db_session.flush()
    return p


async def _seed_audit(db_session: AsyncSession, campus_id: int, resource_type: str, resource_id: str, action: str = "CREATE", username: str = "admin") -> AuditLog:
    log = AuditLog(
        username=username, action=action, resource_type=resource_type,
        resource_id=resource_id, campus_id=campus_id,
        created_at=NOW - datetime.timedelta(days=1),
        details='{"key": "value"}',
    )
    db_session.add(log)
    await db_session.flush()
    return log


async def _seed_workflow_action(
    db_session: AsyncSession, campus_id: int, *, action: str = "approve",
    entity_type: str = "leave", entity_id: int = 7,
) -> ApprovalHistory:
    wf = Workflow(name="Leave Request", code=f"LEAVE-{entity_id}", entity_type=entity_type, status="active")
    db_session.add(wf)
    await db_session.flush()
    step = WorkflowStep(
        workflow_id=wf.id, name="Approved", step_order=0,
        is_initial=True, is_final=True,
    )
    db_session.add(step)
    await db_session.flush()
    inst = WorkflowInstance(
        workflow_id=wf.id, current_step_id=step.id, campus_id=campus_id,
        entity_type=entity_type, entity_id=entity_id, status="active", created_by=1,
    )
    db_session.add(inst)
    await db_session.flush()
    h = ApprovalHistory(
        instance_id=inst.id, action=action, actor_id=2,
        comment="OK", created_at=NOW - datetime.timedelta(days=3),
    )
    db_session.add(h)
    await db_session.flush()
    return h


async def _seed_risk_finding(
    db_session: AsyncSession, campus_id: int, student: Student,
    *, category: str = "attendance", severity: str = "high",
) -> RiskFinding:
    # Unique (campus, entity, rule_code, status) — derive a distinct
    # rule code per category so multiple findings can coexist for one student.
    f = RiskFinding(
        campus_id=campus_id, entity_type="student", entity_id=student.id,
        student_id=student.id, rule_code=f"{category}_rule",
        category=category, severity=severity, score=74.0,
        reason=f"{category} issue for {student.first_name}",
        recommended_action="Review & act", evidence={},
        status="open", detected_at=NOW - datetime.timedelta(days=4),
        last_verified_at=NOW - datetime.timedelta(days=4),
    )
    db_session.add(f)
    await db_session.flush()
    return f


@pytest.fixture
async def seeded(db_session: AsyncSession):
    structure = await _seed_structure(db_session, 1, "A")
    students = await _seed_student(db_session, 1, "A", n=2)
    return {"structure": structure, "students": students}


async def _service(db_session: AsyncSession, role: str = "admin") -> TimelineService:
    return TimelineService(db_session)


# ---------------------------------------------------------------------------
# A. Aggregation across sources
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregates_across_sources(seeded, db_session: AsyncSession):
    s = seeded["students"][0]
    await _seed_payment(db_session, seeded["structure"], s)
    await _seed_enrollment(db_session, seeded["structure"], s)
    await _seed_audit(db_session, 1, "student", str(s.id))
    await _seed_workflow_action(db_session, 1)
    await _seed_risk_finding(db_session, 1, s)

    svc = await _service(db_session)
    resp = await svc.get_timeline(
        role="admin", user_id=1, campus_id=1,
        filters=TimelineFilters(page_size=50),
    )
    sources = {si.key: si for si in resp.sources}
    assert sources["fees"].count == 1
    assert sources["academic"].count == 1
    assert sources["audit"].count == 1
    assert sources["workflow"].count == 1
    assert sources["risk"].count == 1
    assert not resp.degraded
    # Reverse-chronological merge
    timestamps = [i.timestamp for i in resp.items]
    assert timestamps == sorted(timestamps, reverse=True)
    # Composite ids never collide across sources
    ids = [i.id for i in resp.items]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# B. RBAC
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_staff_hides_finance_and_leadership(seeded, db_session: AsyncSession):
    s = seeded["students"][0]
    await _seed_payment(db_session, seeded["structure"], s)
    await _seed_enrollment(db_session, seeded["structure"], s)
    await _seed_audit(db_session, 1, "payment", "99")
    await _seed_audit(db_session, 1, "student", str(s.id))
    await _seed_workflow_action(db_session, 1)

    svc = await _service(db_session, role="staff")
    resp = await svc.get_timeline(
        role="staff", user_id=1, campus_id=1,
        filters=TimelineFilters(page_size=50),
    )
    keys = {si.key for si in resp.sources}
    assert "fees" not in keys  # financial source hidden
    assert "workflow" not in keys  # approvals leadership-only
    # Financial audit rows must not leak into the audit source either
    audit_events = [i for i in resp.items if i.source == "audit"]
    assert all("payment" not in i.event_type for i in audit_events)
    assert any(i.source == "academic" for i in resp.items)


@pytest.mark.asyncio
async def test_accountant_sees_fees_but_not_admissions(seeded, db_session: AsyncSession):
    s = seeded["students"][0]
    await _seed_payment(db_session, seeded["structure"], s)
    app = AdmissionApplication(applicant_name="New Kid", campus_id=1, status="application_submitted")
    db_session.add(app)
    await db_session.flush()

    svc = await _service(db_session, role="accountant")
    resp = await svc.get_timeline(
        role="accountant", user_id=1, campus_id=1,
        filters=TimelineFilters(page_size=50),
    )
    keys = {si.key for si in resp.sources}
    assert "fees" in keys
    assert "admissions" not in keys  # leadership-only
    assert any(i.source == "fees" for i in resp.items)


@pytest.mark.asyncio
async def test_risk_finance_category_hidden_for_staff(seeded, db_session: AsyncSession):
    s = seeded["students"][0]
    await _seed_risk_finding(db_session, 1, s, category="attendance")
    await _seed_risk_finding(db_session, 1, s, category="finance")

    svc = await _service(db_session, role="staff")
    resp = await svc.get_timeline(
        role="staff", user_id=1, campus_id=1,
        filters=TimelineFilters(page_size=50),
    )
    risk_events = [i for i in resp.items if i.source == "risk"]
    assert all(i.metadata.get("category") != "finance" for i in risk_events)

    admin = await _service(db_session, role="admin")
    admin_resp = await admin.get_timeline(
        role="admin", user_id=1, campus_id=1,
        filters=TimelineFilters(page_size=50),
    )
    assert any(i.metadata.get("category") == "finance" for i in admin_resp.items)


# ---------------------------------------------------------------------------
# C. Tenant isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tenant_isolation(db_session: AsyncSession):
    structure_a = await _seed_structure(db_session, 1, "A")
    sa = await _seed_student(db_session, 1, "A", n=1)
    await _seed_payment(db_session, structure_a, sa[0], campus_id=1)

    structure_b = await _seed_structure(db_session, 2, "B")
    sb = await _seed_student(db_session, 2, "B", n=1)
    await _seed_payment(db_session, structure_b, sb[0], campus_id=2)

    svc = await _service(db_session)
    resp_a = await svc.get_timeline(
        role="admin", user_id=1, campus_id=1,
        filters=TimelineFilters(page_size=50),
    )
    # Campus A sees only its own student's payment.
    fee_entities = [i.entity for i in resp_a.items if i.source == "fees"]
    assert all(sa[0].first_name in e or f"#{sa[0].id}" in e for e in fee_entities)

    resp_b = await svc.get_timeline(
        role="admin", user_id=1, campus_id=2,
        filters=TimelineFilters(page_size=50),
    )
    fee_entities_b = [i.entity for i in resp_b.items if i.source == "fees"]
    assert all(sb[0].first_name in e or f"#{sb[0].id}" in e for e in fee_entities_b)


@pytest.mark.asyncio
async def test_entity_scope_cross_tenant_blocked(db_session: AsyncSession):
    structure_a = await _seed_structure(db_session, 1, "A")
    sa = await _seed_student(db_session, 1, "A", n=1)
    structure_b = await _seed_structure(db_session, 2, "B")
    sb = await _seed_student(db_session, 2, "B", n=1)
    await _seed_enrollment(db_session, structure_a, sa[0], campus_id=1)
    await _seed_enrollment(db_session, structure_b, sb[0], campus_id=2)

    svc = await _service(db_session)
    # Reading campus B's student from campus A's context must 403.
    with pytest.raises(AuthorizationError):
        await svc.get_timeline(
            role="admin", user_id=1, campus_id=1,
            filters=TimelineFilters(entity_type="student", entity_id=sb[0].id),
        )


@pytest.mark.asyncio
async def test_entity_scope_not_found(db_session: AsyncSession):
    svc = await _service(db_session)
    with pytest.raises(NotFoundError):
        await svc.get_timeline(
            role="admin", user_id=1, campus_id=1,
            filters=TimelineFilters(entity_type="student", entity_id=999_999),
        )


# ---------------------------------------------------------------------------
# D. Entity scoping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_student_scope_returns_only_that_student(seeded, db_session: AsyncSession):
    s1, s2 = seeded["students"]
    await _seed_payment(db_session, seeded["structure"], s1)
    await _seed_payment(db_session, seeded["structure"], s2)
    await _seed_enrollment(db_session, seeded["structure"], s1)
    await _seed_enrollment(db_session, seeded["structure"], s2)

    svc = await _service(db_session)
    resp = await svc.get_timeline(
        role="admin", user_id=1, campus_id=1,
        filters=TimelineFilters(entity_type="student", entity_id=s1.id, page_size=50),
    )
    fee_students = {i.metadata.get("student_id") for i in resp.items if i.source == "fees"}
    assert fee_students == {s1.id}
    enrolled = {i.metadata.get("student_id") for i in resp.items if i.source == "academic"}
    assert enrolled == {s1.id}


# ---------------------------------------------------------------------------
# E. Filters + pagination
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_source_filter(seeded, db_session: AsyncSession):
    s = seeded["students"][0]
    await _seed_payment(db_session, seeded["structure"], s)
    await _seed_enrollment(db_session, seeded["structure"], s)

    svc = await _service(db_session)
    resp = await svc.get_timeline(
        role="admin", user_id=1, campus_id=1,
        filters=TimelineFilters(source="fees", page_size=50),
    )
    assert all(i.source == "fees" for i in resp.items)
    assert resp.sources[0].key == "fees"


@pytest.mark.asyncio
async def test_event_type_filter(seeded, db_session: AsyncSession):
    s = seeded["students"][0]
    await _seed_payment(db_session, seeded["structure"], s)
    await _seed_enrollment(db_session, seeded["structure"], s)
    await _seed_audit(db_session, 1, "student", str(s.id), action="CREATE")
    await _seed_audit(db_session, 1, "student", str(s.id), action="UPDATE")

    svc = await _service(db_session)
    # Exact event-type filter narrows to a single kind.
    resp = await svc.get_timeline(
        role="admin", user_id=1, campus_id=1,
        filters=TimelineFilters(event_type="fees.payment", page_size=50),
    )
    assert all(i.event_type == "fees.payment" for i in resp.items)
    assert resp.total == 1

    # Only the CREATE audit row matches; UPDATE is excluded.
    resp = await svc.get_timeline(
        role="admin", user_id=1, campus_id=1,
        filters=TimelineFilters(event_type="audit.student.create", page_size=50),
    )
    assert len(resp.items) == 1
    assert all(i.event_type == "audit.student.create" for i in resp.items)

    svc = await _service(db_session)
    resp = await svc.get_timeline(
        role="admin", user_id=1, campus_id=1,
        filters=TimelineFilters(source="fees", page_size=50),
    )
    assert all(i.source == "fees" for i in resp.items)
    assert resp.sources[0].key == "fees"


@pytest.mark.asyncio
async def test_actor_filter(seeded, db_session: AsyncSession):
    await _seed_audit(db_session, 1, "student", "1", username="ravi.kumar")
    await _seed_audit(db_session, 1, "student", "2", username="meera.nair")

    svc = await _service(db_session)
    resp = await svc.get_timeline(
        role="admin", user_id=1, campus_id=1,
        filters=TimelineFilters(actor="ravi", page_size=50),
    )
    audit_items = [i for i in resp.items if i.source == "audit"]
    assert len(audit_items) == 1
    assert audit_items[0].actor == "ravi.kumar"


@pytest.mark.asyncio
async def test_date_range_filter(seeded, db_session: AsyncSession):
    s = seeded["students"][0]
    await _seed_enrollment(db_session, seeded["structure"], s, days_back=5)

    svc = await _service(db_session)
    cutoff = NOW - datetime.timedelta(days=3)
    resp = await svc.get_timeline(
        role="admin", user_id=1, campus_id=1,
        filters=TimelineFilters(start=cutoff, page_size=50),
    )
    # The 5-day-old enrollment is outside the window.
    assert all(i.source != "academic" for i in resp.items)


@pytest.mark.asyncio
async def test_pagination_slices_merged_results(seeded, db_session: AsyncSession):
    s = seeded["students"][0]
    for i in range(5):
        await _seed_audit(db_session, 1, "student", str(s.id), action="CREATE", username=f"user{i}")
    # 5 audit events (1 day old each, same timestamp) — paginate 2 at a time.
    svc = await _service(db_session)
    p1 = await svc.get_timeline(
        role="admin", user_id=1, campus_id=1,
        filters=TimelineFilters(page=1, page_size=2),
    )
    p2 = await svc.get_timeline(
        role="admin", user_id=1, campus_id=1,
        filters=TimelineFilters(page=2, page_size=2),
    )
    assert p1.total == 5
    assert len(p1.items) == 2
    assert len(p2.items) == 2
    ids_p1 = {i.id for i in p1.items}
    ids_p2 = {i.id for i in p2.items}
    assert ids_p1.isdisjoint(ids_p2)


# ---------------------------------------------------------------------------
# F. Graceful partial failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_partial_failure_degrades_but_renders(seeded, db_session: AsyncSession, monkeypatch):
    s = seeded["students"][0]
    await _seed_payment(db_session, seeded["structure"], s)

    svc = await _service(db_session)

    async def boom(*args, **kwargs):  # pragma: no cover
        raise RuntimeError("boom — source unavailable")

    monkeypatch.setattr(svc, "_fetch_payments", boom)

    resp = await svc.get_timeline(
        role="admin", user_id=1, campus_id=1,
        filters=TimelineFilters(page_size=50),
    )
    assert resp.degraded is True
    by_key = {si.key: si for si in resp.sources}
    assert by_key["fees"].available is False
    # Other sources still render (audit/academic present as empty available sources).
    assert by_key["audit"].available is True


# ---------------------------------------------------------------------------
# G. Notifications are own + broadcasts only
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notifications_scoped_to_user(seeded, db_session: AsyncSession):
    db_session.add(
        Notification(user_id=5, type="risk_alert", title="For user 5", message="x", campus_id=1)
    )
    db_session.add(
        Notification(user_id=None, type="system", title="Broadcast", message="y", campus_id=1)
    )
    await db_session.flush()

    svc = await _service(db_session)
    resp = await svc.get_timeline(
        role="admin", user_id=5, campus_id=1,
        filters=TimelineFilters(page_size=50),
    )
    notifications = [i for i in resp.items if i.source == "notification"]
    # User 5 sees only their own + broadcasts (not user 6's).
    titles = {i.entity for i in notifications}
    assert "For user 5" in titles
    assert "Broadcast" in titles
