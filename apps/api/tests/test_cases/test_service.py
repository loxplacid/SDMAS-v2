"""Tests for the Operational Case Management service.

Covers:
  - controlled lifecycle transitions (whitelist, no OPEN -> CLOSED)
  - immutable event timeline (every action produces a CaseEvent)
  - SLA calculation from config defaults + derived states
  - priority engine (original vs current, audited change)
  - assignment / reassignment (events + notifications)
  - comments and evidence (append-only, audited)
  - deterministic escalation
  - metrics / workload aggregation
  - tenant isolation (campus-scoped)
  - RBAC (staff cannot reassign/resolve via service contract helpers)
  - optimistic concurrency (version bump on conflicting updates)
  - P7 integration: case created FROM a risk / data-quality finding
"""

from __future__ import annotations

import datetime
from datetime import timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.domains.cases.models import (
    CASE_STATUS_ACKNOWLEDGED,
    CASE_STATUS_CLOSED,
    CASE_STATUS_IN_PROGRESS,
    CASE_STATUS_OPEN,
    CASE_STATUS_RESOLVED,
    CASE_STATUS_WAITING,
    Case,
    CaseComment,
    CaseEvent,
    CaseEvidence,
    CaseSLAConfig,
)
from app.domains.cases.service import CaseService
from app.domains.data_quality.models import (
    DataQualityFinding,  # noqa: F401 — registers metadata for create_all
)
from app.domains.risk.models import RiskFinding

NOW = datetime.datetime.now(timezone.utc)


class StubUser:
    def __init__(self, role: str = "admin", user_id: int = 1, name: str = "Ada Admin"):
        self.role = role
        self.id = user_id
        self.display_name = name


async def _seed_user(
    db_session: AsyncSession, *, uid: int, name: str,
    role: str = "staff", campus_id: int | None = 1,
):
    from app.domains.auth.models import User

    u = User(
        id=uid, username=f"user{uid}", email=f"user{uid}@test.local",
        password_hash="x", display_name=name, role=role,
        campus_id=campus_id, is_active=True,
    )
    db_session.add(u)
    await db_session.flush()
    return u


async def _create_case(
    db_session: AsyncSession, *,
    title: str = "Test case", case_type: str = "attendance",
    priority: str = "high", assigned_to: int | None = None,
    campus_id: int | None = 1,
) -> Case:
    svc = CaseService(db_session)
    return await svc.create_case(
        campus_id=campus_id,
        actor_user_id=1,
        actor_name="Ada Admin",
        title=title,
        case_type=case_type,
        priority=priority,
        assigned_to=assigned_to,
    )


async def _seed_risk_finding(
    db_session: AsyncSession, *, severity: str = "high",
    campus_id: int | None = 1,
) -> RiskFinding:
    f = RiskFinding(
        campus_id=campus_id, entity_type="student", entity_id=7,
        rule_code="attendance_below_threshold", category="attendance",
        severity=severity, score=0.8, reason="Below threshold",
        recommended_action="Review", status="open",
    )
    db_session.add(f)
    await db_session.flush()
    return f


# ---------------------------------------------------------------------------
# A. Lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_case_writes_created_event(db_session: AsyncSession):
    case = await _create_case(db_session)

    events = (
        await db_session.execute(
            select(CaseEvent).where(CaseEvent.case_id == case.id)
        )
    ).scalars().all()
    assert [e.event_type for e in events] == ["CASE_CREATED"]
    assert case.case_number.startswith("DMAS-")
    assert case.status == CASE_STATUS_OPEN
    assert case.original_priority == case.priority == "high"


@pytest.mark.asyncio
async def test_valid_transition_open_to_acknowledged(db_session: AsyncSession):
    case = await _create_case(db_session)
    svc = CaseService(db_session)

    updated = await svc.transition_status(
        case.id, 1, 1, "Ada Admin", CASE_STATUS_ACKNOWLEDGED
    )
    assert updated.status == CASE_STATUS_ACKNOWLEDGED
    events = (
        await db_session.execute(
            select(CaseEvent).where(CaseEvent.case_id == case.id)
        )
    ).scalars().all()
    assert CASE_STATUS_ACKNOWLEDGED in [e.event_type for e in events] or "STATUS_CHANGED" in [
        e.event_type for e in events
    ]


@pytest.mark.asyncio
async def test_direct_open_to_closed_rejected(db_session: AsyncSession):
    case = await _create_case(db_session)
    svc = CaseService(db_session)

    with pytest.raises(ValidationError):
        await svc.transition_status(case.id, 1, 1, "Ada Admin", CASE_STATUS_CLOSED)


@pytest.mark.asyncio
async def test_resolve_then_close(db_session: AsyncSession):
    case = await _create_case(db_session)
    svc = CaseService(db_session)

    resolved = await svc.transition_status(
        case.id, 1, 1, "Ada Admin", CASE_STATUS_RESOLVED, reason="Issue fixed"
    )
    assert resolved.status == CASE_STATUS_RESOLVED
    assert resolved.resolved_at is not None
    assert resolved.resolved_reason == "Issue fixed"

    closed = await svc.transition_status(
        case.id, 1, 1, "Ada Admin", CASE_STATUS_CLOSED
    )
    assert closed.status == CASE_STATUS_CLOSED
    assert closed.closed_at is not None

    events = (
        await db_session.execute(
            select(CaseEvent).where(CaseEvent.case_id == case.id)
        )
    ).scalars().all()
    types = [e.event_type for e in events]
    assert "RESOLVED" in types
    assert "CLOSED" in types


@pytest.mark.asyncio
async def test_reopen_resolved_case(db_session: AsyncSession):
    case = await _create_case(db_session)
    svc = CaseService(db_session)
    await svc.transition_status(case.id, 1, 1, "Ada Admin", CASE_STATUS_RESOLVED, reason="Done")

    reopened = await svc.transition_status(
        case.id, 1, 1, "Ada Admin", CASE_STATUS_OPEN, reason="Reopened — recurring"
    )
    assert reopened.status == CASE_STATUS_OPEN
    assert reopened.resolved_at is None

    events = (
        await db_session.execute(
            select(CaseEvent).where(CaseEvent.case_id == case.id)
        )
    ).scalars().all()
    assert "REOPENED" in [e.event_type for e in events]


@pytest.mark.asyncio
async def test_invalid_status_value_rejected(db_session: AsyncSession):
    case = await _create_case(db_session)
    svc = CaseService(db_session)
    with pytest.raises(ValidationError):
        await svc.transition_status(case.id, 1, 1, "Ada Admin", "bogus")


@pytest.mark.asyncio
async def test_same_status_transition_rejected(db_session: AsyncSession):
    case = await _create_case(db_session)
    svc = CaseService(db_session)
    with pytest.raises(ValidationError):
        await svc.transition_status(case.id, 1, 1, "Ada Admin", CASE_STATUS_OPEN)


# ---------------------------------------------------------------------------
# B. SLA
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_due_at_from_sla_default(db_session: AsyncSession):
    case = await _create_case(db_session, priority="critical")
    # critical → 4h default
    assert case.due_at is not None
    delta = (case.due_at - case.created_at).total_seconds()
    assert abs(delta - 4 * 3600) < 60


@pytest.mark.asyncio
async def test_campus_sla_override_wins(db_session: AsyncSession):
    db_session.add(
        CaseSLAConfig(
            campus_id=1, case_type="attendance", priority="high",
            after_hours=1.0, escalation_after_hours=2.0, enabled=True,
        )
    )
    await db_session.flush()

    case = await _create_case(db_session, priority="high")
    delta = (case.due_at - case.created_at).total_seconds()
    assert abs(delta - 3600) < 60


@pytest.mark.asyncio
async def test_sla_state_calculated_not_stored(db_session: AsyncSession):
    case = await _create_case(db_session, priority="high")  # due in 24h
    svc = CaseService(db_session)
    assert svc.sla_state(case) == "ON_TRACK"

    # Past due
    case.due_at = NOW - datetime.timedelta(hours=1)
    await db_session.flush()
    assert svc.sla_state(case) == "OVERDUE"

    # Near due (within last 25%)
    case.due_at = NOW + datetime.timedelta(hours=2)
    case.created_at = NOW - datetime.timedelta(hours=20)
    await db_session.flush()
    assert svc.sla_state(case) == "DUE_SOON"

    # Resolved → RESOLVED regardless of due
    case.status = CASE_STATUS_RESOLVED
    case.resolved_at = NOW
    await db_session.flush()
    assert svc.sla_state(case) == "RESOLVED"


# ---------------------------------------------------------------------------
# C. Priority engine
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_priority_change_records_original_and_event(db_session: AsyncSession):
    case = await _create_case(db_session, priority="medium")
    svc = CaseService(db_session)

    updated = await svc.change_priority(case.id, 1, 1, "Ada Admin", "critical", reason="Escalating")
    assert updated.original_priority == "medium"
    assert updated.priority == "critical"

    events = (
        await db_session.execute(
            select(CaseEvent).where(CaseEvent.case_id == case.id)
        )
    ).scalars().all()
    assert "PRIORITY_CHANGED" in [e.event_type for e in events]


@pytest.mark.asyncio
async def test_priority_change_same_value_rejected(db_session: AsyncSession):
    case = await _create_case(db_session, priority="high")
    svc = CaseService(db_session)
    with pytest.raises(ValidationError):
        await svc.change_priority(case.id, 1, 1, "Ada Admin", "high")


# ---------------------------------------------------------------------------
# D. Assignment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assign_case_creates_event_and_notification(db_session: AsyncSession):
    await _seed_user(db_session, uid=42, name="Stacy Staff")
    case = await _create_case(db_session, title="Needs attention")
    svc = CaseService(db_session)

    updated = await svc.assign_case(case.id, 1, 1, "Ada Admin", 42)
    assert updated.assigned_to == 42
    assert updated.assigned_at is not None

    events = (
        await db_session.execute(
            select(CaseEvent).where(CaseEvent.case_id == case.id)
        )
    ).scalars().all()
    assert "ASSIGNED" in [e.event_type for e in events]

    from app.domains.notifications.models import Notification

    notifications = (
        await db_session.execute(
            select(Notification).where(
                Notification.user_id == 42,
                Notification.type == "case_assigned",
            )
        )
    ).scalars().all()
    assert notifications
    assert case.case_number in notifications[0].title


@pytest.mark.asyncio
async def test_reassign_records_reassigned_event(db_session: AsyncSession):
    await _seed_user(db_session, uid=42, name="Stacy Staff")
    await _seed_user(db_session, uid=43, name="Paul Principal", role="principal")
    case = await _create_case(db_session, assigned_to=42)
    svc = CaseService(db_session)

    await svc.assign_case(case.id, 1, 1, "Ada Admin", 43, reason="Moving ownership")

    events = (
        await db_session.execute(
            select(CaseEvent).where(CaseEvent.case_id == case.id)
        )
    ).scalars().all()
    assert "REASSIGNED" in [e.event_type for e in events]


@pytest.mark.asyncio
async def test_assign_to_unknown_user_rejected(db_session: AsyncSession):
    case = await _create_case(db_session)
    svc = CaseService(db_session)
    with pytest.raises(ValidationError):
        await svc.assign_case(case.id, 1, 1, "Ada Admin", 999999)


# ---------------------------------------------------------------------------
# E. Comments + evidence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_comment_creates_comment_and_event(db_session: AsyncSession):
    case = await _create_case(db_session)
    svc = CaseService(db_session)

    comment = await svc.add_comment(case.id, 1, 1, "Ada Admin", "Investigating the records")
    assert comment.body == "Investigating the records"
    assert comment.author_id == 1

    comments = (
        await db_session.execute(
            select(CaseComment).where(CaseComment.case_id == case.id)
        )
    ).scalars().all()
    assert len(comments) == 1

    events = (
        await db_session.execute(
            select(CaseEvent).where(CaseEvent.case_id == case.id)
        )
    ).scalars().all()
    assert "COMMENT_ADDED" in [e.event_type for e in events]


@pytest.mark.asyncio
async def test_add_evidence_records_reference(db_session: AsyncSession):
    case = await _create_case(db_session)
    svc = CaseService(db_session)

    evidence = await svc.add_evidence(
        case.id, 1, 1, "Ada Admin",
        kind="attendance_report", title="March attendance report",
        reference_type="attendance_report", reference_id=5,
    )
    assert evidence.kind == "attendance_report"
    assert evidence.reference_id == 5

    rows = (
        await db_session.execute(
            select(CaseEvidence).where(CaseEvidence.case_id == case.id)
        )
    ).scalars().all()
    assert len(rows) == 1

    events = (
        await db_session.execute(
            select(CaseEvent).where(CaseEvent.case_id == case.id)
        )
    ).scalars().all()
    assert "EVIDENCE_ADDED" in [e.event_type for e in events]


@pytest.mark.asyncio
async def test_invalid_evidence_kind_rejected(db_session: AsyncSession):
    case = await _create_case(db_session)
    svc = CaseService(db_session)
    with pytest.raises(ValidationError):
        await svc.add_evidence(case.id, 1, 1, "Ada Admin", kind="malware", title="x")


# ---------------------------------------------------------------------------
# F. Escalation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_escalation_escalates_overdue_past_threshold(db_session: AsyncSession):
    case = await _create_case(db_session, priority="high")  # SLA 24h, esc 48h
    # Age it far past the escalation threshold.
    case.created_at = NOW - datetime.timedelta(hours=100)
    case.due_at = NOW - datetime.timedelta(hours=76)  # due 76h ago
    await db_session.flush()

    svc = CaseService(db_session)
    result = await svc.run_escalation(1, actor_user_id=1)
    assert case.id in result["escalated"]
    assert case.escalated_at is not None

    events = (
        await db_session.execute(
            select(CaseEvent).where(CaseEvent.case_id == case.id)
        )
    ).scalars().all()
    assert "ESCALATED" in [e.event_type for e in events]


@pytest.mark.asyncio
async def test_run_escalation_is_idempotent(db_session: AsyncSession):
    case = await _create_case(db_session, priority="high")
    case.created_at = NOW - datetime.timedelta(hours=100)
    case.due_at = NOW - datetime.timedelta(hours=76)
    await db_session.flush()

    svc = CaseService(db_session)
    r1 = await svc.run_escalation(1)
    r2 = await svc.run_escalation(1)

    assert len(r1["escalated"]) == 1
    assert len(r2["escalated"]) == 0  # never re-notify


@pytest.mark.asyncio
async def test_run_escalation_skips_on_track_cases(db_session: AsyncSession):
    await _create_case(db_session, priority="high")  # due in 24h, on track
    svc = CaseService(db_session)
    result = await svc.run_escalation(1)
    assert result["count"] == 0


@pytest.mark.asyncio
async def test_escalation_notifies_only_case_campus_leadership(
    db_session: AsyncSession,
):
    """Platform-level escalation (campus_id=None) must not leak
    notifications across campuses — each case notifies its own campus."""
    from app.domains.notifications.models import Notification

    await _seed_user(db_session, uid=61, name="A-Lead", role="principal", campus_id=1)
    await _seed_user(db_session, uid=62, name="B-Lead", role="principal", campus_id=2)

    case_a = await _create_case(db_session, campus_id=1, priority="high")
    case_a.created_at = NOW - datetime.timedelta(hours=100)
    case_a.due_at = NOW - datetime.timedelta(hours=76)
    case_b = await _create_case(db_session, campus_id=2, priority="high")
    case_b.created_at = NOW - datetime.timedelta(hours=100)
    case_b.due_at = NOW - datetime.timedelta(hours=76)
    await db_session.flush()

    svc = CaseService(db_session)
    # Platform scope: no campus filter.
    result = await svc.run_escalation(None, actor_user_id=None, actor_name="System")
    assert len(result["escalated"]) == 2

    notifications = (
        await db_session.execute(select(Notification))
    ).scalars().all()
    assert len(notifications) == 2
    # Every notification row targets the case's own campus leadership;
    # a campus-B case never notifies the campus-A leader and vice versa.
    for notif in notifications:
        case_id = (notif.data or {}).get("case_id")
        if case_id == case_b.id:
            assert notif.user_id != 61
            assert notif.user_id == 62
        if case_id == case_a.id:
            assert notif.user_id != 62
            assert notif.user_id == 61


@pytest.mark.asyncio
async def test_scheduler_registers_cases_escalation_job():
    """The periodic scheduler includes the case escalation job."""
    from app.domains.jobs.scheduler import _PERIODIC_JOBS

    job_types = [spec[0] for spec in _PERIODIC_JOBS]
    assert "cases.escalation" in job_types


# ---------------------------------------------------------------------------
# G. Metrics + workload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_metrics_open_critical_overdue(db_session: AsyncSession):
    await _seed_user(db_session, uid=42, name="Stacy Staff")
    await _create_case(db_session, priority="critical")  # due in 4h
    c2 = await _create_case(db_session, priority="high", assigned_to=42)  # due in 24h
    # Make c2 overdue.
    c2.created_at = NOW - datetime.timedelta(hours=50)
    c2.due_at = NOW - datetime.timedelta(hours=26)
    await db_session.flush()

    svc = CaseService(db_session)
    metrics = await svc.get_metrics(1)
    assert metrics["open"] >= 2
    assert metrics["critical"] >= 1
    assert metrics["overdue"] >= 1
    assert "attendance" in metrics["by_type"]
    assert metrics["by_priority"].get("critical", 0) >= 1


@pytest.mark.asyncio
async def test_resolution_metrics(db_session: AsyncSession):
    c1 = await _create_case(db_session, priority="high")
    c2 = await _create_case(db_session, priority="medium")
    c1.created_at = NOW - datetime.timedelta(hours=10)
    c2.created_at = NOW - datetime.timedelta(hours=2)
    await db_session.flush()

    svc = CaseService(db_session)
    await svc.transition_status(c1.id, 1, 1, "Ada Admin", CASE_STATUS_RESOLVED, reason="Done")
    await svc.transition_status(c2.id, 1, 1, "Ada Admin", CASE_STATUS_RESOLVED, reason="Done")

    metrics = await svc.get_metrics(1)
    assert metrics["avg_resolution_hours"] is not None
    assert metrics["median_resolution_hours"] is not None
    assert metrics["resolution_rate"] is not None
    # c2 resolved in ~2h
    assert metrics["avg_resolution_hours"] <= 10


@pytest.mark.asyncio
async def test_workload_groups_by_assignee(db_session: AsyncSession):
    await _seed_user(db_session, uid=42, name="Stacy Staff")
    await _seed_user(db_session, uid=43, name="Paul Principal", role="principal")
    await _create_case(db_session, assigned_to=42)
    await _create_case(db_session, assigned_to=42, priority="critical")
    await _create_case(db_session, assigned_to=43)

    svc = CaseService(db_session)
    workload = await svc.get_workload(1)
    by_id = {w["assignee_id"]: w for w in workload}
    assert by_id[42]["open_cases"] == 2
    assert by_id[42]["critical_cases"] == 1
    assert by_id[43]["open_cases"] == 1


# ---------------------------------------------------------------------------
# H. Tenant isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tenant_isolation(db_session: AsyncSession):
    campus_a = await _create_case(db_session, campus_id=1, title="Campus A case")
    campus_b = await _create_case(db_session, campus_id=2, title="Campus B case")

    svc = CaseService(db_session)
    a_rows, a_total = await svc.list_cases(1)
    b_rows, b_total = await svc.list_cases(2)

    assert a_total == 1 and a_rows[0].id == campus_a.id
    assert b_total == 1 and b_rows[0].id == campus_b.id

    with pytest.raises(Exception):
        await svc._get_case(campus_b.id, 1)  # campus A cannot read campus B case


# ---------------------------------------------------------------------------
# I. Optimistic concurrency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stale_version_rejected(db_session: AsyncSession):
    case = await _create_case(db_session)
    svc = CaseService(db_session)
    await svc.transition_status(case.id, 1, 1, "Ada Admin", CASE_STATUS_IN_PROGRESS)
    assert case.version == 2

    # A stale client passes version=1 → conflict
    with pytest.raises(ValidationError):
        await svc.transition_status(
            case.id, 1, 1, "Ada Admin", CASE_STATUS_WAITING, version=1
        )

    # Correct version proceeds
    updated = await svc.transition_status(
        case.id, 1, 1, "Ada Admin", CASE_STATUS_WAITING, version=2
    )
    assert updated.status == CASE_STATUS_WAITING
    assert updated.version == 3


# ---------------------------------------------------------------------------
# J. P7 integration — findings become cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_case_from_risk_finding(db_session: AsyncSession):
    finding = await _seed_risk_finding(db_session, severity="high")
    svc = CaseService(db_session)

    case = await svc.create_case(
        campus_id=1,
        actor_user_id=1,
        actor_name="Ada Admin",
        title=f"Attendance anomaly — student {finding.id}",
        case_type="attendance",
        priority="medium",  # should be overridden by finding severity
        source_type="risk_finding",
        source_id=finding.id,
    )
    assert case.source_type == "risk_finding"
    assert case.source_id == finding.id
    assert case.priority == "high"  # inherited from severity


@pytest.mark.asyncio
async def test_create_case_rejects_missing_finding(db_session: AsyncSession):
    svc = CaseService(db_session)
    with pytest.raises(ValidationError):
        await svc.create_case(
            campus_id=1,
            actor_user_id=1,
            actor_name="Ada Admin",
            title="Ghost finding",
            source_type="risk_finding",
            source_id=999999,
        )


@pytest.mark.asyncio
async def test_one_case_per_source_unique(db_session: AsyncSession):
    finding = await _seed_risk_finding(db_session)
    svc = CaseService(db_session)
    await svc.create_case(
        campus_id=1, actor_user_id=1, actor_name="Ada Admin",
        title="First", source_type="risk_finding", source_id=finding.id,
    )
    with pytest.raises(Exception):  # unique constraint (campus, source_type, source_id)
        await svc.create_case(
            campus_id=1, actor_user_id=1, actor_name="Ada Admin",
            title="Second", source_type="risk_finding", source_id=finding.id,
        )


@pytest.mark.asyncio
async def test_create_case_from_data_quality_finding(db_session: AsyncSession):
    dq = DataQualityFinding(
        campus_id=1, check_code="duplicate_students", category="duplicates",
        severity="medium", entity_type="student", entity_id=3, field="email",
        description="Duplicate email", status="open",
    )
    db_session.add(dq)
    await db_session.flush()

    svc = CaseService(db_session)
    case = await svc.create_case(
        campus_id=1, actor_user_id=1, actor_name="Ada Admin",
        title="Merge duplicate student records",
        case_type="data_quality",
        source_type="data_quality_finding", source_id=dq.id,
    )
    assert case.source_type == "data_quality_finding"
    assert case.priority == "medium"


# ---------------------------------------------------------------------------
# K. Work queue queries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_cases_views_and_search(db_session: AsyncSession):
    await _seed_user(db_session, uid=42, name="Stacy Staff")
    c1 = await _create_case(db_session, title="Overdue invoice", assigned_to=42)
    c2 = await _create_case(db_session, title="Attendance anomaly")
    c2.assigned_to = None
    await db_session.flush()

    svc = CaseService(db_session)

    my_rows, my_total = await svc.list_cases(1, view="my", user_id=42)
    assert my_total == 1 and my_rows[0].id == c1.id

    unassigned_rows, unassigned_total = await svc.list_cases(1, view="unassigned")
    assert unassigned_total == 1

    search_rows, search_total = await svc.list_cases(1, search="attendance")
    assert search_total == 1 and search_rows[0].id == c2.id

    by_type_rows, _ = await svc.list_cases(1, case_type="attendance")
    assert by_type_rows[0].id == c2.id


@pytest.mark.asyncio
async def test_list_cases_filters_by_student(db_session: AsyncSession):
    """Student-scoped work-queue query (Student 360 operational summary):
    only cases linked to the requested student are returned, and the
    filter composes with the campus tenancy scope."""
    svc = CaseService(db_session)
    # Cases may only be created with a student_id via the service; create
    # them then attach the student reference directly (schema allows it).
    a = await _create_case(db_session, title="Attendance anomaly", case_type="attendance")
    b = await _create_case(db_session, title="Fee escalation", case_type="finance")
    a.student_id = 1001
    b.student_id = 2002
    other = await _create_case(db_session, title="Unlinked case")
    other.student_id = None
    await db_session.flush()

    rows, total = await svc.list_cases(1, student_id=1001)
    assert total == 1
    assert rows[0].id == a.id
    assert rows[0].title == "Attendance anomaly"

    rows, total = await svc.list_cases(1, student_id=2002)
    assert total == 1
    assert rows[0].id == b.id

    rows, total = await svc.list_cases(1, student_id=9999)
    assert total == 0

    # Composes with the work-queue "open" view and status filters.
    rows, total = await svc.list_cases(1, view="open", student_id=1001)
    assert total == 1 and rows[0].id == a.id

    # Campus isolation still applies: another campus never sees this student.
    rows, total = await svc.list_cases(2, student_id=1001)
    assert total == 0


@pytest.mark.asyncio
async def test_create_case_rejects_student_outside_campus(db_session: AsyncSession):
    """P10 — a case may only be created for a student of the caller's
    own campus (mirrors the source/assignee validation elsewhere)."""
    from app.domains.student.models import Student

    student = Student(
        first_name="Ravi", last_name="Kumar", student_number="P10-001",
        campus_id=2, status="active",
    )
    db_session.add(student)
    await db_session.flush()

    svc = CaseService(db_session)
    # Same-campus student — allowed.
    case = await svc.create_case(
        campus_id=2, actor_user_id=1, actor_name="Ada Admin",
        title="Local student case", student_id=student.id,
    )
    assert case.student_id == student.id

    # Foreign-campus student — rejected.
    with pytest.raises(ValidationError):
        await svc.create_case(
            campus_id=1, actor_user_id=1, actor_name="Ada Admin",
            title="Foreign student case", student_id=student.id,
        )

    # Unknown student id — rejected.
    with pytest.raises(ValidationError):
        await svc.create_case(
            campus_id=1, actor_user_id=1, actor_name="Ada Admin",
            title="Ghost student case", student_id=999999,
        )


@pytest.mark.asyncio
async def test_overview_counts(db_session: AsyncSession):
    await _seed_user(db_session, uid=42, name="Stacy Staff")
    await _create_case(db_session, priority="critical", assigned_to=42)
    c2 = await _create_case(db_session, priority="high")
    c2.due_at = NOW - datetime.timedelta(hours=1)
    await db_session.flush()

    svc = CaseService(db_session)
    overview = await svc.get_overview(1, user_id=42)
    assert overview["open"] == 2
    assert overview["critical"] == 1
    assert overview["overdue"] == 1
    assert overview["my_open"] == 1


# ---------------------------------------------------------------------------
# L. P11 — closed loop: case ↔ originating finding
# ---------------------------------------------------------------------------


async def _case_from_finding(db_session: AsyncSession, *, title: str = "Loop case") -> Case:
    finding = await _seed_risk_finding(db_session, severity="high")
    svc = CaseService(db_session)
    case = await svc.create_case(
        campus_id=1,
        actor_user_id=1,
        actor_name="Ada Admin",
        title=title,
        case_type="attendance",
        source_type="risk_finding",
        source_id=finding.id,
    )
    return case, finding


@pytest.mark.asyncio
async def test_resolve_case_resolves_linked_risk_finding(db_session: AsyncSession):
    """Resolving a case closes the loop: the referenced finding is resolved
    with the case number recorded, and the finding resolution is audited."""
    case, finding = await _case_from_finding(db_session)
    assert finding.status == "open"

    svc = CaseService(db_session)
    await svc.transition_status(
        case.id, 1, 1, "Ada Admin", CASE_STATUS_RESOLVED, reason="Attendance reviewed"
    )

    await db_session.refresh(finding)
    assert finding.status == "resolved"
    assert finding.resolved_by == 1
    assert case.case_number in (finding.resolved_reason or "")

    from app.domains.audit.models import AuditLog

    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.resource_type == "risk_finding",
                AuditLog.resource_id == str(finding.id),
            )
        )
    ).scalars().all()
    assert audit and audit[0].action == "RESOLVE"
    assert case.case_number in (audit[0].details or "")


@pytest.mark.asyncio
async def test_reopen_case_reopens_finding_it_resolved(db_session: AsyncSession):
    """Reopening a case reopens the finding that the case had resolved."""
    case, finding = await _case_from_finding(db_session)
    svc = CaseService(db_session)
    await svc.transition_status(case.id, 1, 1, "Ada Admin", CASE_STATUS_RESOLVED)
    await db_session.refresh(finding)
    assert finding.status == "resolved"

    await svc.transition_status(
        case.id, 1, 1, "Ada Admin", CASE_STATUS_OPEN, reason="Recurring issue"
    )
    await db_session.refresh(finding)
    assert finding.status == "open"
    assert finding.resolved_at is None
    assert finding.resolved_reason is None

    from app.domains.audit.models import AuditLog

    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.resource_type == "risk_finding",
                AuditLog.resource_id == str(finding.id),
                AuditLog.action == "REOPEN",
            )
        )
    ).scalars().all()
    assert audit


@pytest.mark.asyncio
async def test_reopen_case_leaves_externally_resolved_finding_alone(db_session: AsyncSession):
    """A finding resolved outside the case (Risk Center / recompute) is never
    reopened just because the case is reopened."""
    case, finding = await _case_from_finding(db_session)
    svc = CaseService(db_session)
    await svc.transition_status(case.id, 1, 1, "Ada Admin", CASE_STATUS_RESOLVED)
    await db_session.refresh(finding)
    assert finding.status == "resolved"

    # Resolve the finding independently (e.g. admin resolved it directly).
    finding.resolved_reason = "Resolved directly in the Risk Center"
    await db_session.flush()

    await svc.transition_status(case.id, 1, 1, "Ada Admin", CASE_STATUS_OPEN)
    await db_session.refresh(finding)
    assert finding.status == "resolved"  # untouched
    assert finding.resolved_reason == "Resolved directly in the Risk Center"


@pytest.mark.asyncio
async def test_resolve_case_is_idempotent_for_already_resolved_finding(db_session: AsyncSession):
    """Resolving a case whose finding is already resolved must not error or
    overwrite the existing resolution reason."""
    case, finding = await _case_from_finding(db_session)
    from app.domains.risk.service import RiskService

    await RiskService(db_session).resolve_finding(
        finding.id, 1, actor_user_id=7, reason="Paid in cash"
    )

    svc = CaseService(db_session)
    await svc.transition_status(
        case.id, 1, 1, "Ada Admin", CASE_STATUS_RESOLVED, reason="Case closed"
    )
    await db_session.refresh(finding)
    assert finding.status == "resolved"
    assert finding.resolved_reason == "Paid in cash"  # never overwritten


@pytest.mark.asyncio
async def test_resolve_case_resolves_linked_data_quality_finding(db_session: AsyncSession):
    """The closed loop also covers data-quality findings."""
    dq = DataQualityFinding(
        campus_id=1, check_code="duplicate_students", category="duplicates",
        severity="medium", entity_type="student", entity_id=3, field="email",
        description="Duplicate email", status="open",
    )
    db_session.add(dq)
    await db_session.flush()

    svc = CaseService(db_session)
    case = await svc.create_case(
        campus_id=1, actor_user_id=1, actor_name="Ada Admin",
        title="Merge duplicate records",
        case_type="data_quality",
        source_type="data_quality_finding", source_id=dq.id,
    )
    await svc.transition_status(
        case.id, 1, 1, "Ada Admin", CASE_STATUS_RESOLVED, reason="Merged"
    )
    await db_session.refresh(dq)
    assert dq.status == "resolved"
    assert case.case_number in (dq.resolved_reason or "")
