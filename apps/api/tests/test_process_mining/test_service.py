"""Tests for the Process Mining Service (TASK 19).

Uses synthetic workflow data to verify all eight analysis capabilities:
  1. Process discovery (graph)
  2. Case identification
  3. Process variants
  4. Cycle time
  5. Bottlenecks
  6. Rework detection
  7. SLA violations
  8. Transition frequency
"""

from __future__ import annotations

import datetime
from datetime import timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.cases.models import Case, CaseEvent
from app.domains.exceptions.models import SystemException, SystemExceptionEvent
from app.domains.process_mining.service import ProcessMiningService
from app.domains.student.models import Student  # noqa: F401 — register table
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


async def _seed_workflow_with_history(
    db_session: AsyncSession,
    campus_id: int,
    wf_code: str,
    entity_type: str,
    entity_id: int,
    actions: list[str],
    *,
    time_gap_minutes: int = 60,
    start_offset_hours: int = 10,
) -> WorkflowInstance:
    """Seed a workflow instance with a sequence of approval history entries."""
    wf = Workflow(
        name=f"WF {wf_code}", code=wf_code,
        entity_type=entity_type, status="active",
    )
    db_session.add(wf)
    await db_session.flush()

    step = WorkflowStep(
        workflow_id=wf.id, name="Step1",
        step_order=0, is_initial=True, is_final=True,
    )
    db_session.add(step)
    await db_session.flush()

    wi = WorkflowInstance(
        workflow_id=wf.id, current_step_id=step.id,
        campus_id=campus_id, entity_type=entity_type,
        entity_id=entity_id, status="active", created_by=1,
    )
    db_session.add(wi)
    await db_session.flush()

    base_time = NOW - datetime.timedelta(hours=start_offset_hours)
    for i, action in enumerate(actions):
        ah = ApprovalHistory(
            instance_id=wi.id, action=action, actor_id=1,
            created_at=base_time + datetime.timedelta(
                minutes=time_gap_minutes * i
            ),
        )
        db_session.add(ah)

    await db_session.flush()
    return wi


async def _seed_case_with_events(
    db_session: AsyncSession,
    campus_id: int,
    case_number: str,
    events: list[tuple[str, int]],
    *,
    start_offset_hours: int = 10,
    gap_minutes: int = 30,
) -> Case:
    """Seed a case with a sequence of events.

    ``events`` is a list of (event_type, minutes_offset_from_start).
    """
    case = Case(
        case_number=case_number, campus_id=campus_id,
        title=f"Case {case_number}", case_type="attendance",
        priority="medium", status="open", created_by=1,
    )
    db_session.add(case)
    await db_session.flush()

    base_time = NOW - datetime.timedelta(hours=start_offset_hours)
    for i, (event_type, offset_min) in enumerate(events):
        ce = CaseEvent(
            case_id=case.id, event_seq=i + 1,
            event_type=event_type, actor_id=1,
            actor_name="admin",
            created_at=base_time + datetime.timedelta(minutes=offset_min),
        )
        db_session.add(ce)

    await db_session.flush()
    return case


async def _seed_exception_with_events(
    db_session: AsyncSession,
    campus_id: int,
    events: list[tuple[str, int]],
    *,
    start_offset_hours: int = 10,
    severity: str = "high",
) -> SystemException:
    """Seed a system exception with lifecycle events."""
    exc = SystemException(
        campus_id=campus_id, source_domain="data_quality",
        source_type="finding", source_id=1,
        exception_type="data_quality", severity=severity,
        title="Test Exception", status="open",
        detected_at=NOW - datetime.timedelta(hours=start_offset_hours),
    )
    db_session.add(exc)
    await db_session.flush()

    base_time = NOW - datetime.timedelta(hours=start_offset_hours)
    for i, (event_type, offset_min) in enumerate(events):
        see = SystemExceptionEvent(
            exception_id=exc.id, event_seq=i + 1,
            event_type=event_type, actor_id=1,
            actor_name="admin",
            created_at=base_time + datetime.timedelta(minutes=offset_min),
        )
        db_session.add(see)

    await db_session.flush()
    return exc


# ---------------------------------------------------------------------------
# 1. Process discovery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_discovery(db_session: AsyncSession):
    """Verify that the process graph correctly discovers activities and transitions."""
    # Three workflow instances with the same path: submit -> approve
    for i in range(3):
        await _seed_workflow_with_history(
            db_session, 1, f"WF{i}", "leave", i + 1,
            ["submit", "approve"],
            start_offset_hours=10 + i,
        )

    svc = ProcessMiningService(db_session)
    result = await svc.analyze(campus_id=1, source="workflow")

    graph = result.graph
    assert graph.total_cases == 3
    assert graph.total_events == 6  # 3 * 2

    activity_names = {n.name for n in graph.nodes}
    assert "submit" in activity_names
    assert "approve" in activity_names

    # Check the submit -> approve edge exists
    edges = {(e.from_activity, e.to_activity) for e in graph.edges}
    assert ("submit", "approve") in edges


# ---------------------------------------------------------------------------
# 2. Case identification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_case_identification(db_session: AsyncSession):
    """Verify that events are correctly grouped into distinct cases."""
    await _seed_workflow_with_history(
        db_session, 1, "WF-A", "leave", 1,
        ["submit", "approve", "complete"],
    )
    await _seed_workflow_with_history(
        db_session, 1, "WF-B", "leave", 2,
        ["submit", "reject"],
    )

    svc = ProcessMiningService(db_session)
    result = await svc.analyze(campus_id=1, source="workflow")

    assert result.summary.total_cases == 2
    case_ids = {c.case_id for c in result.cases}
    assert "wf:1" in case_ids
    assert "wf:2" in case_ids


# ---------------------------------------------------------------------------
# 3. Process variants
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_variants(db_session: AsyncSession):
    """Verify that distinct execution paths are identified."""
    # Variant 1: submit -> approve (2 cases)
    for i in range(2):
        await _seed_workflow_with_history(
            db_session, 1, f"WF-V1-{i}", "leave", i + 1,
            ["submit", "approve"],
            start_offset_hours=10 + i,
        )

    # Variant 2: submit -> reject (1 case)
    await _seed_workflow_with_history(
        db_session, 1, "WF-V2", "leave", 3,
        ["submit", "reject"],
        start_offset_hours=20,
    )

    svc = ProcessMiningService(db_session)
    result = await svc.analyze(campus_id=1, source="workflow")

    assert len(result.variants) == 2
    # Most common variant first
    assert result.variants[0].count == 2
    assert "submit" in result.variants[0].path
    assert "approve" in result.variants[0].path
    assert result.variants[1].count == 1


# ---------------------------------------------------------------------------
# 4. Cycle time
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cycle_time(db_session: AsyncSession):
    """Verify that cycle times are correctly computed."""
    # Case with 2 hours between submit and approve
    await _seed_workflow_with_history(
        db_session, 1, "WF-CT", "leave", 1,
        ["submit", "approve"],
        time_gap_minutes=120,  # 2 hours
    )

    svc = ProcessMiningService(db_session)
    result = await svc.analyze(campus_id=1, source="workflow")

    assert result.summary.avg_cycle_time_seconds is not None
    assert result.summary.avg_cycle_time_seconds > 0
    assert result.summary.median_cycle_time_seconds is not None


# ---------------------------------------------------------------------------
# 5. Bottlenecks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bottlenecks(db_session: AsyncSession):
    """Verify that steps with long waits are identified as bottlenecks."""
    # Create cases with long waits at the "review" step
    for i in range(3):
        await _seed_case_with_events(
            db_session, 1, f"BTL-{i}",
            [
                ("CASE_CREATED", 0),
                ("STATUS_CHANGED", 5),  # 5 min gap
                ("STATUS_CHANGED", 305),  # 5 hour wait at review
                ("RESOLVED", 365),  # 1 hour to resolve
            ],
            start_offset_hours=20 + i,
        )

    svc = ProcessMiningService(db_session)
    result = await svc.analyze(campus_id=1, source="case")

    # The "status_changed" arriving after a long wait should appear
    assert len(result.bottlenecks) >= 1
    # Bottlenecks are sorted by p90 wait descending
    assert result.bottlenecks[0].p90_wait_seconds > 0


# ---------------------------------------------------------------------------
# 6. Rework detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rework_detection(db_session: AsyncSession):
    """Verify that repeated steps in a case are detected as rework."""
    # A case where status_changed happens 3 times (rework loop)
    await _seed_case_with_events(
        db_session, 1, "REWORK-1",
        [
            ("CASE_CREATED", 0),
            ("STATUS_CHANGED", 60),
            ("STATUS_CHANGED", 120),
            ("STATUS_CHANGED", 180),
            ("RESOLVED", 240),
        ],
    )

    svc = ProcessMiningService(db_session)
    result = await svc.analyze(campus_id=1, source="case")

    rework_for_case = [
        r for r in result.rework if r.case_id == "case:1"
    ]
    assert len(rework_for_case) >= 1
    # status_changed should show 3 occurrences
    sc_rework = [
        r for r in rework_for_case
        if r.rework_activity == "status_changed"
    ]
    assert len(sc_rework) == 1
    assert sc_rework[0].occurrences == 3


# ---------------------------------------------------------------------------
# 7. SLA violations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sla_violations(db_session: AsyncSession):
    """Verify that cases exceeding SLA limits are detected."""
    # Case spans from 80h ago to now -> ~80h duration > 72h medium SLA.
    # The last event is at 0 minutes offset from base (= 80h ago + 0 = 80h ago).
    # To make it span to "now", we set the last event offset high.
    # base_time = NOW - 80h; events at 0min and 4800min (=80h).
    # That makes ended_at = NOW - 80h + 80h = NOW.
    await _seed_case_with_events(
        db_session, 1, "SLA-1",
        [
            ("CASE_CREATED", 0),
            ("STATUS_CHANGED", 4800),  # 80 hours after start = NOW
        ],
        start_offset_hours=80,
    )

    svc = ProcessMiningService(db_session)
    result = await svc.analyze(campus_id=1, source="case")

    # Case duration ~80h exceeds medium SLA (72h)
    violations_for_case = [
        v for v in result.sla_violations if v.case_id == "case:1"
    ]
    assert len(violations_for_case) == 1
    assert violations_for_case[0].overshoot_seconds > 0


# ---------------------------------------------------------------------------
# 8. Transition frequency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transition_frequency(db_session: AsyncSession):
    """Verify that transition frequencies are correctly computed."""
    # 3 cases with submit -> approve, 1 with submit -> reject
    for i in range(3):
        await _seed_workflow_with_history(
            db_session, 1, f"WF-TF-{i}", "leave", i + 1,
            ["submit", "approve"],
            start_offset_hours=10 + i,
        )
    await _seed_workflow_with_history(
        db_session, 1, "WF-TF-REJ", "leave", 4,
        ["submit", "reject"],
        start_offset_hours=14,
    )

    svc = ProcessMiningService(db_session)
    result = await svc.analyze(campus_id=1, source="workflow")

    tf_map = {t.transition: t for t in result.transitions}
    assert "submit -> approve" in tf_map
    assert "submit -> reject" in tf_map
    assert tf_map["submit -> approve"].count == 3
    assert tf_map["submit -> reject"].count == 1
    # Percentages should sum to ~100%
    total_pct = sum(t.percentage for t in result.transitions)
    assert abs(total_pct - 100.0) < 0.1


# ---------------------------------------------------------------------------
# Cross-source analysis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_source_analysis(db_session: AsyncSession):
    """Verify that analysis works across multiple sources."""
    await _seed_workflow_with_history(
        db_session, 1, "WF-CS", "leave", 1,
        ["submit", "approve"],
    )
    await _seed_case_with_events(
        db_session, 1, "CS-1",
        [("CASE_CREATED", 0), ("RESOLVED", 60)],
    )
    await _seed_exception_with_events(
        db_session, 1,
        [("EXCEPTION_CREATED", 0), ("STATUS_CHANGED", 30)],
    )

    svc = ProcessMiningService(db_session)
    result = await svc.analyze(campus_id=1)

    assert result.summary.total_cases == 3
    case_ids = {c.case_id for c in result.cases}
    assert "wf:1" in case_ids
    assert "case:1" in case_ids


# ---------------------------------------------------------------------------
# Empty / missing data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_analysis(db_session: AsyncSession):
    """Verify graceful handling of no data."""
    svc = ProcessMiningService(db_session)
    result = await svc.analyze(campus_id=999)

    assert result.summary.total_cases == 0
    assert result.summary.total_events == 0
    assert result.graph.nodes == []
    assert result.graph.edges == []
    assert result.variants == []
    assert result.bottlenecks == []
    assert result.rework == []
    assert result.sla_violations == []
    assert result.transitions == []
    assert result.cases == []


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tenant_isolation(db_session: AsyncSession):
    """Verify that analysis is scoped to the caller's campus."""
    await _seed_workflow_with_history(
        db_session, 1, "WF-TI-A", "leave", 1,
        ["submit", "approve"],
    )
    await _seed_workflow_with_history(
        db_session, 2, "WF-TI-B", "leave", 1,
        ["submit", "reject"],
    )

    svc = ProcessMiningService(db_session)
    result_a = await svc.analyze(campus_id=1)
    result_b = await svc.analyze(campus_id=2)

    assert result_a.summary.total_cases == 1
    assert result_b.summary.total_cases == 1
    # Different campuses have different variants
    assert result_a.variants[0].path != result_b.variants[0].path


# ---------------------------------------------------------------------------
# Degradation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_source_degradation(db_session: AsyncSession, monkeypatch):
    """Verify that a failing source doesn't break the analysis."""
    await _seed_case_with_events(
        db_session, 1, "DG-1",
        [("CASE_CREATED", 0), ("RESOLVED", 60)],
    )

    svc = ProcessMiningService(db_session)

    async def boom(*args, **kwargs):  # pragma: no cover
        raise RuntimeError("source down")

    monkeypatch.setattr(svc, "_workflow_events", boom)

    result = await svc.analyze(campus_id=1)
    # Case source still works
    assert result.summary.total_cases == 1
