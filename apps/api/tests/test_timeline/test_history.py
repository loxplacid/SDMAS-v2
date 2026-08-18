"""Tests for the Institutional History Service (TASK 18).

Covers all five query types:
  1. Entity history — "What happened to this student?"
  2. Campus history — "What changed in this campus?"
  3. Pre-exception timeline — "What happened before this exception?"
  4. Causal chain — "Which events caused this workflow?"
  5. Date range diff — "What changed between two dates?"

Also covers:
  - Deterministic summary statistics
  - Lifecycle milestone extraction
  - Tenant isolation (campus scoping)
  - Graceful degradation when sources fail
  - Empty / missing entity handling
"""

from __future__ import annotations

import datetime
import json
import uuid
from datetime import timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.audit.models import AuditLog
from app.domains.cases.models import Case, CaseEvent
from app.domains.events.outbox import OutboxEvent
from app.domains.exceptions.models import SystemException, SystemExceptionEvent
from app.domains.student.models import Student
from app.domains.timeline.history import InstitutionalHistoryService
from app.domains.workflow.models import (
    ApprovalHistory,
    Workflow,
    WorkflowInstance,
    WorkflowStep,
)

NOW = datetime.datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------


async def _seed_student(db_session: AsyncSession, campus_id: int, prefix: str) -> Student:
    s = Student(
        first_name=f"{prefix}S", last_name="Hist",
        student_number=f"{prefix.upper()}HIST001", campus_id=campus_id, status="active",
    )
    db_session.add(s)
    await db_session.flush()
    return s


async def _seed_audit_log(
    db_session: AsyncSession,
    campus_id: int,
    resource_type: str,
    resource_id: str,
    action: str = "CREATE",
    username: str = "admin",
    *,
    created_at: datetime.datetime | None = None,
) -> AuditLog:
    log = AuditLog(
        username=username, action=action, resource_type=resource_type,
        resource_id=resource_id, campus_id=campus_id,
        created_at=created_at or NOW - datetime.timedelta(hours=1),
        details=json.dumps({"key": "value"}),
    )
    db_session.add(log)
    await db_session.flush()
    return log


async def _seed_outbox_event(
    db_session: AsyncSession,
    event_type: str,
    *,
    entity_type: str = "student",
    entity_id: int | None = None,
    school_id: int | None = 1,
    actor_user_id: int | None = 1,
    occurred_at: datetime.datetime | None = None,
    causation_id: str = "",
    payload: dict | None = None,
    event_id: str | None = None,
) -> OutboxEvent:
    ev = OutboxEvent(
        event_id=event_id or f"evt_{entity_type}_{entity_id}_{uuid.uuid4().hex[:8]}",
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        school_id=school_id,
        actor_user_id=actor_user_id,
        correlation_id=None,
        event_version=1,
        causation_id=causation_id or None,
        source=None,
        occurred_at=occurred_at or NOW - datetime.timedelta(hours=2),
        payload=payload or {},
        status="completed",
        attempts=1,
        max_attempts=10,
        created_at=occurred_at or NOW - datetime.timedelta(hours=2),
        updated_at=occurred_at or NOW - datetime.timedelta(hours=2),
    )
    db_session.add(ev)
    await db_session.flush()
    return ev


async def _seed_case_with_event(
    db_session: AsyncSession,
    campus_id: int,
    student_id: int,
    *,
    event_type: str = "STATUS_CHANGED",
    created_at: datetime.datetime | None = None,
) -> tuple[Case, CaseEvent]:
    case = Case(
        case_number=f"CAS-{student_id}",
        campus_id=campus_id,
        title="Test Case",
        case_type="attendance",
        priority="medium",
        status="open",
        student_id=student_id,
        created_by=1,
    )
    db_session.add(case)
    await db_session.flush()

    ce = CaseEvent(
        case_id=case.id,
        event_seq=1,
        event_type=event_type,
        actor_id=1,
        actor_name="admin",
        message="Status changed",
        created_at=created_at or NOW - datetime.timedelta(hours=3),
    )
    db_session.add(ce)
    await db_session.flush()
    return case, ce


async def _seed_exception_with_event(
    db_session: AsyncSession,
    campus_id: int,
    student_id: int,
    *,
    severity: str = "high",
    created_at: datetime.datetime | None = None,
) -> tuple[SystemException, SystemExceptionEvent]:
    exc = SystemException(
        campus_id=campus_id,
        source_domain="data_quality",
        source_type="finding",
        source_id=1,
        exception_type="data_quality",
        severity=severity,
        title="Test Exception",
        status="open",
        student_id=student_id,
        detected_at=created_at or NOW - datetime.timedelta(hours=4),
    )
    db_session.add(exc)
    await db_session.flush()

    see = SystemExceptionEvent(
        exception_id=exc.id,
        event_seq=1,
        event_type="EXCEPTION_CREATED",
        actor_id=1,
        actor_name="admin",
        message="Exception created",
        created_at=created_at or NOW - datetime.timedelta(hours=4),
    )
    db_session.add(see)
    await db_session.flush()
    return exc, see


async def _seed_workflow(
    db_session: AsyncSession,
    campus_id: int,
    entity_type: str,
    entity_id: int,
    *,
    action: str = "approve",
    created_at: datetime.datetime | None = None,
) -> ApprovalHistory:
    wf = Workflow(name="Test WF", code=f"WF-{entity_id}", entity_type=entity_type, status="active")
    db_session.add(wf)
    await db_session.flush()
    step = WorkflowStep(
        workflow_id=wf.id, name="Step1",
        step_order=0, is_initial=True, is_final=True,
    )
    db_session.add(step)
    await db_session.flush()
    inst = WorkflowInstance(
        workflow_id=wf.id, current_step_id=step.id, campus_id=campus_id,
        entity_type=entity_type, entity_id=entity_id, status="active", created_by=1,
    )
    db_session.add(inst)
    await db_session.flush()
    ah = ApprovalHistory(
        instance_id=inst.id, action=action, actor_id=2,
        comment="Looks good", created_at=created_at or NOW - datetime.timedelta(hours=5),
    )
    db_session.add(ah)
    await db_session.flush()
    return ah


# ---------------------------------------------------------------------------
# 1. Entity History — "What happened to this student?"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_entity_history_aggregates_sources(db_session: AsyncSession):
    student = await _seed_student(db_session, 1, "E1")
    await _seed_audit_log(db_session, 1, "student", str(student.id), action="CREATE")
    await _seed_outbox_event(
        db_session, "student.created",
        entity_type="student", entity_id=student.id, school_id=1,
    )
    await _seed_case_with_event(db_session, 1, student.id)
    await _seed_exception_with_event(db_session, 1, student.id)
    await _seed_workflow(db_session, 1, "student", student.id)

    svc = InstitutionalHistoryService(db_session)
    result = await svc.entity_history(campus_id=1, entity_type="student", entity_id=student.id)

    assert result.entity_type == "student"
    assert result.entity_id == student.id
    assert result.total >= 5  # at least one from each source
    assert len(result.events) >= 5

    sources = {e.source for e in result.events}
    assert "audit" in sources
    assert "outbox" in sources
    assert "case" in sources
    assert "exception" in sources
    assert "workflow" in sources


@pytest.mark.asyncio
async def test_entity_history_chronological_order(db_session: AsyncSession):
    student = await _seed_student(db_session, 1, "E2")
    d5 = NOW - datetime.timedelta(days=5)
    d1 = NOW - datetime.timedelta(days=1)
    d3 = NOW - datetime.timedelta(days=3)
    await _seed_audit_log(db_session, 1, "student", str(student.id), created_at=d5)
    await _seed_audit_log(db_session, 1, "student", str(student.id), created_at=d1)
    await _seed_audit_log(db_session, 1, "student", str(student.id), created_at=d3)

    svc = InstitutionalHistoryService(db_session)
    result = await svc.entity_history(campus_id=1, entity_type="student", entity_id=student.id)

    timestamps = [e.timestamp for e in result.events]
    assert timestamps == sorted(timestamps)


@pytest.mark.asyncio
async def test_entity_history_lifecycle_milestones(db_session: AsyncSession):
    student = await _seed_student(db_session, 1, "E3")
    # Seed a student.created outbox event — it's a lifecycle milestone
    await _seed_outbox_event(
        db_session, "student.created",
        entity_type="student", entity_id=student.id, school_id=1,
        payload={"student_id": student.id, "full_name": "E3 Hist"},
    )
    # And a student.status_changed
    await _seed_outbox_event(
        db_session, "student.status_changed",
        entity_type="student", entity_id=student.id, school_id=1,
        payload={"student_id": student.id, "from_status": "active", "to_status": "inactive"},
    )

    svc = InstitutionalHistoryService(db_session)
    result = await svc.entity_history(campus_id=1, entity_type="student", entity_id=student.id)

    assert len(result.lifecycle) >= 2
    milestone_types = {m.event_type for m in result.lifecycle}
    assert "student.created" in milestone_types
    assert "student.status_changed" in milestone_types


@pytest.mark.asyncio
async def test_entity_history_empty(db_session: AsyncSession):
    svc = InstitutionalHistoryService(db_session)
    result = await svc.entity_history(campus_id=999, entity_type="student", entity_id=999_999)

    assert result.total == 0
    assert result.events == []
    assert result.lifecycle == []
    assert result.summary.total_events == 0


@pytest.mark.asyncio
async def test_entity_history_summary_statistics(db_session: AsyncSession):
    student = await _seed_student(db_session, 1, "E4")
    await _seed_audit_log(db_session, 1, "student", str(student.id), username="alice")
    await _seed_audit_log(db_session, 1, "student", str(student.id), username="bob")
    await _seed_outbox_event(
        db_session, "student.created",
        entity_type="student", entity_id=student.id, school_id=1,
    )

    svc = InstitutionalHistoryService(db_session)
    result = await svc.entity_history(campus_id=1, entity_type="student", entity_id=student.id)

    summary = result.summary
    assert summary.total_events >= 3
    assert "audit" in summary.sources
    assert "outbox" in summary.sources
    assert summary.first_event_at is not None
    assert summary.last_event_at is not None
    assert summary.date_range_days is not None
    assert summary.date_range_days >= 0


# ---------------------------------------------------------------------------
# 2. Campus History — "What changed in this campus?"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_campus_history_all_sources(db_session: AsyncSession):
    student = await _seed_student(db_session, 1, "C1")
    await _seed_audit_log(db_session, 1, "student", str(student.id))
    await _seed_outbox_event(
        db_session, "student.created",
        entity_type="student", entity_id=student.id, school_id=1,
    )
    await _seed_case_with_event(db_session, 1, student.id)
    await _seed_exception_with_event(db_session, 1, student.id)
    await _seed_workflow(db_session, 1, "student", student.id)

    svc = InstitutionalHistoryService(db_session)
    result = await svc.campus_history(campus_id=1)

    assert result.query_type == "campus_history"
    assert result.total >= 5
    assert result.summary.total_events >= 5


@pytest.mark.asyncio
async def test_campus_history_source_filter(db_session: AsyncSession):
    student = await _seed_student(db_session, 1, "C2")
    await _seed_audit_log(db_session, 1, "student", str(student.id))
    await _seed_outbox_event(
        db_session, "student.created",
        entity_type="student", entity_id=student.id, school_id=1,
    )

    svc = InstitutionalHistoryService(db_session)
    result = await svc.campus_history(campus_id=1, source="audit")

    assert all(e.source == "audit" for e in result.events)


@pytest.mark.asyncio
async def test_campus_history_tenant_isolation(db_session: AsyncSession):
    s1 = await _seed_student(db_session, 1, "CA")
    s2 = await _seed_student(db_session, 2, "CB")
    await _seed_audit_log(db_session, 1, "student", str(s1.id))
    await _seed_audit_log(db_session, 2, "student", str(s2.id))

    svc = InstitutionalHistoryService(db_session)
    result_a = await svc.campus_history(campus_id=1)
    result_b = await svc.campus_history(campus_id=2)

    assert result_a.total == 1
    assert result_b.total == 1
    # Cross-tenant isolation: campus A events don't leak into B
    assert all(e.source != "audit" or "CA" not in e.entity for e in result_b.events)


# ---------------------------------------------------------------------------
# 3. Pre-Exception Timeline — "What happened before this exception?"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pre_exception_timeline(db_session: AsyncSession):
    student = await _seed_student(db_session, 1, "PE")
    exc_time = NOW - datetime.timedelta(hours=4)

    # Events before the exception
    d2 = NOW - datetime.timedelta(days=2)
    await _seed_audit_log(db_session, 1, "student", str(student.id), created_at=d2)
    await _seed_outbox_event(
        db_session, "student.created",
        entity_type="student", entity_id=student.id, school_id=1,
        occurred_at=NOW - datetime.timedelta(days=1),
    )

    # The exception itself
    exc, _ = await _seed_exception_with_event(
        db_session, 1, student.id, created_at=exc_time,
    )

    # An event after the exception (should NOT appear)
    await _seed_audit_log(db_session, 1, "student", str(student.id), created_at=NOW)

    svc = InstitutionalHistoryService(db_session)
    result = await svc.pre_exception_timeline(campus_id=1, exception_id=exc.id)

    assert result.query_type == "pre_exception"
    assert result.total >= 2
    # All events should be before the exception time (strip tz for naive comparison)
    exc_naive = exc_time.replace(tzinfo=None)
    for evt in result.events:
        ts = evt.timestamp.replace(tzinfo=None) if evt.timestamp.tzinfo else evt.timestamp
        assert ts <= exc_naive


@pytest.mark.asyncio
async def test_pre_exception_nonexistent(db_session: AsyncSession):
    svc = InstitutionalHistoryService(db_session)
    result = await svc.pre_exception_timeline(campus_id=1, exception_id=999_999)

    assert result.total == 0
    assert result.events == []


# ---------------------------------------------------------------------------
# 4. Causal Chain — "Which events caused this workflow?"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_causal_chain_linear(db_session: AsyncSession):
    # Build a chain: root -> mid -> target
    await _seed_outbox_event(
        db_session, "student.created",
        entity_type="student", entity_id=1, school_id=1,
        event_id="root_001",
        occurred_at=NOW - datetime.timedelta(hours=6),
    )
    await _seed_outbox_event(
        db_session, "admission.submitted",
        entity_type="admission", entity_id=1, school_id=1,
        event_id="mid_001",
        causation_id="root_001",
        occurred_at=NOW - datetime.timedelta(hours=4),
    )
    await _seed_outbox_event(
        db_session, "workflow.submitted",
        entity_type="workflow", entity_id=1, school_id=1,
        event_id="target_001",
        causation_id="mid_001",
        occurred_at=NOW - datetime.timedelta(hours=2),
    )

    svc = InstitutionalHistoryService(db_session)
    result = await svc.causal_chain(campus_id=1, event_id="target_001")

    assert result is not None
    assert result.depth == 2
    assert result.root_event.id == "outbox:root_001"
    assert result.target_event.id == "outbox:target_001"
    assert len(result.chain) == 3


@pytest.mark.asyncio
async def test_causal_chain_no_parent(db_session: AsyncSession):
    await _seed_outbox_event(
        db_session, "student.created",
        entity_type="student", entity_id=1, school_id=1,
        event_id="solo_001",
    )

    svc = InstitutionalHistoryService(db_session)
    result = await svc.causal_chain(campus_id=1, event_id="solo_001")

    assert result is not None
    assert result.depth == 0
    assert len(result.chain) == 1
    assert result.root_event.id == result.target_event.id


@pytest.mark.asyncio
async def test_causal_chain_nonexistent_event(db_session: AsyncSession):
    svc = InstitutionalHistoryService(db_session)
    result = await svc.causal_chain(campus_id=1, event_id="nonexistent")

    assert result is None


@pytest.mark.asyncio
async def test_causal_chain_circular_protection(db_session: AsyncSession):
    # Create a circular chain: A -> B -> A
    await _seed_outbox_event(
        db_session, "student.created",
        entity_type="student", entity_id=1, school_id=1,
        event_id="circ_a", causation_id="circ_b",
    )
    await _seed_outbox_event(
        db_session, "student.updated",
        entity_type="student", entity_id=1, school_id=1,
        event_id="circ_b", causation_id="circ_a",
    )

    svc = InstitutionalHistoryService(db_session)
    result = await svc.causal_chain(campus_id=1, event_id="circ_a")

    assert result is not None
    # Should not loop infinitely — max depth limits + visited set
    assert result.depth <= 20


# ---------------------------------------------------------------------------
# 5. Date Range Diff — "What changed between two dates?"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_date_range_diff(db_session: AsyncSession):
    student = await _seed_student(db_session, 1, "DR")
    start = NOW - datetime.timedelta(days=7)
    end = NOW

    d5 = NOW - datetime.timedelta(days=5)
    d3 = NOW - datetime.timedelta(days=3)
    await _seed_audit_log(db_session, 1, "student", str(student.id), created_at=d5)
    await _seed_audit_log(db_session, 1, "student", str(student.id), created_at=d3)
    await _seed_outbox_event(
        db_session, "student.created",
        entity_type="student", entity_id=student.id, school_id=1,
        occurred_at=NOW - datetime.timedelta(days=4),
    )

    svc = InstitutionalHistoryService(db_session)
    result = await svc.date_range_diff(campus_id=1, start=start, end=end)

    assert result.total >= 3
    assert result.start == start
    assert result.end == end
    assert "audit" in result.by_source
    assert "outbox" in result.by_source


@pytest.mark.asyncio
async def test_date_range_diff_source_filter(db_session: AsyncSession):
    student = await _seed_student(db_session, 1, "DR2")
    start = NOW - datetime.timedelta(days=7)
    end = NOW

    await _seed_audit_log(db_session, 1, "student", str(student.id))
    await _seed_outbox_event(
        db_session, "student.created",
        entity_type="student", entity_id=student.id, school_id=1,
    )

    svc = InstitutionalHistoryService(db_session)
    result = await svc.date_range_diff(campus_id=1, start=start, end=end, source="audit")

    assert all(e.source == "audit" for e in result.events)


@pytest.mark.asyncio
async def test_date_range_diff_empty_range(db_session: AsyncSession):
    start = NOW - datetime.timedelta(days=1)
    end = NOW - datetime.timedelta(hours=12)

    svc = InstitutionalHistoryService(db_session)
    result = await svc.date_range_diff(campus_id=999, start=start, end=end)

    assert result.total == 0
    assert result.most_active_actor is None
    assert result.most_changed_entity is None


@pytest.mark.asyncio
async def test_date_range_diff_most_active_actor(db_session: AsyncSession):
    student = await _seed_student(db_session, 1, "DR3")
    start = NOW - datetime.timedelta(days=7)
    end = NOW

    # 3 events from alice, 1 from bob
    for _ in range(3):
        await _seed_audit_log(db_session, 1, "student", str(student.id), username="alice")
    await _seed_audit_log(db_session, 1, "student", str(student.id), username="bob")

    svc = InstitutionalHistoryService(db_session)
    result = await svc.date_range_diff(campus_id=1, start=start, end=end, source="audit")

    assert result.most_active_actor == "alice"


# ---------------------------------------------------------------------------
# Degradation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_campus_history_degrades_on_source_failure(db_session: AsyncSession, monkeypatch):
    student = await _seed_student(db_session, 1, "DG")
    await _seed_audit_log(db_session, 1, "student", str(student.id))

    svc = InstitutionalHistoryService(db_session)

    async def boom(*args, **kwargs):  # pragma: no cover
        raise RuntimeError("source down")

    monkeypatch.setattr(svc, "_fetch_campus_outbox", boom)

    result = await svc.campus_history(campus_id=1)
    # Audit source still renders even if outbox failed
    assert any(e.source == "audit" for e in result.events)


@pytest.mark.asyncio
async def test_date_range_diff_degrades_on_source_failure(db_session: AsyncSession, monkeypatch):
    student = await _seed_student(db_session, 1, "DG2")
    start = NOW - datetime.timedelta(days=7)
    end = NOW
    await _seed_audit_log(db_session, 1, "student", str(student.id))

    svc = InstitutionalHistoryService(db_session)

    async def boom(*args, **kwargs):  # pragma: no cover
        raise RuntimeError("down")

    monkeypatch.setattr(svc, "_fetch_outbox_range", boom)

    result = await svc.date_range_diff(campus_id=1, start=start, end=end)
    assert any(e.source == "audit" for e in result.events)
