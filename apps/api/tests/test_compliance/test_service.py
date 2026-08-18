"""Tests for the Declarative Compliance Engine (TASK 20).

Uses synthetic schema packs to verify:
  - Regulation / requirement CRUD
  - Schema pack creation and publishing
  - Rule evaluation (all rule types)
  - Submission with deterministic scoring
  - Explainability (full evaluation traces)
  - Approval workflow
  - Dashboard aggregation
  - Tenant isolation
  - Empty data handling
"""

from __future__ import annotations

import datetime
from datetime import timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.compliance.models import (
    ComplianceRegulation,
    ComplianceRequirement,
    ComplianceSchema,
)
from app.domains.compliance.service import ComplianceService

NOW = datetime.datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------


async def _seed_regulation(
    db_session: AsyncSession,
    campus_id: int | None,
    reg_id: str = "test_regulation",
) -> ComplianceRegulation:
    svc = ComplianceService(db_session)
    return await svc.create_regulation(
        campus_id=campus_id,
        regulation_id=reg_id,
        name="Test Regulation",
        description="A test regulation for unit tests",
        authority="Test Authority",
    )


async def _seed_requirement(
    db_session: AsyncSession,
    campus_id: int | None,
    reg: ComplianceRegulation,
    req_id: str = "R1.1",
    *,
    category: str = "student_data",
    severity: str = "medium",
    is_mandatory: bool = True,
) -> ComplianceRequirement:
    svc = ComplianceService(db_session)
    return await svc.create_requirement(
        campus_id=campus_id,
        regulation_id=reg.id,
        requirement_id=req_id,
        title=f"Requirement {req_id}",
        description=f"Test requirement {req_id}",
        category=category,
        severity=severity,
        is_mandatory=is_mandatory,
    )


async def _seed_schema_with_rules(
    db_session: AsyncSession,
    campus_id: int | None,
    *,
    schema_id: str = "test_schema",
    rules: list[dict] | None = None,
) -> ComplianceSchema:
    svc = ComplianceService(db_session)
    default_rules = rules or [
        {
            "rule_code": "student.has_name",
            "rule_type": "field_exists",
            "target_entity": "student",
            "target_field": "name",
            "severity": "high",
            "explanation": "Every student must have a name",
        },
        {
            "rule_code": "student.age_range",
            "rule_type": "value_range",
            "target_entity": "student",
            "target_field": "age",
            "condition": {"min": 5, "max": 20},
            "severity": "medium",
            "explanation": "Student age must be between 5 and 20",
        },
    ]
    schema = await svc.create_schema(
        campus_id=campus_id,
        schema_id=schema_id,
        title="Test Schema Pack",
        description="A test schema for unit tests",
        data_sources=["student"],
        rules=default_rules,
        actor_id=1,
    )
    return schema


# ---------------------------------------------------------------------------
# 1. Regulation CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_regulation(db_session: AsyncSession):
    reg = await _seed_regulation(db_session, 1)
    assert reg.regulation_id == "test_regulation"
    assert reg.name == "Test Regulation"
    assert reg.authority == "Test Authority"
    assert reg.status == "draft"


@pytest.mark.asyncio
async def test_create_requirement(db_session: AsyncSession):
    reg = await _seed_regulation(db_session, 1)
    req = await _seed_requirement(db_session, 1, reg, "R1.1")
    assert req.requirement_id == "R1.1"
    assert req.category == "student_data"
    assert req.is_mandatory is True


@pytest.mark.asyncio
async def test_list_regulations(db_session: AsyncSession):
    await _seed_regulation(db_session, 1, "reg_a")
    await _seed_regulation(db_session, 1, "reg_b")
    svc = ComplianceService(db_session)
    regs = await svc.list_regulations(1)
    assert len(regs) == 2


# ---------------------------------------------------------------------------
# 2. Schema pack creation and publishing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_schema_with_rules(db_session: AsyncSession):
    schema = await _seed_schema_with_rules(db_session, 1)
    assert schema.schema_id == "test_schema"
    assert schema.version == 1
    assert schema.is_current is False
    # Reload to check rules
    svc = ComplianceService(db_session)
    loaded = await svc.get_schema(1, schema.id)
    assert loaded is not None
    assert len(loaded.rules) == 2


@pytest.mark.asyncio
async def test_publish_schema(db_session: AsyncSession):
    schema = await _seed_schema_with_rules(db_session, 1)
    svc = ComplianceService(db_session)
    published = await svc.publish_schema(1, schema.id, actor_id=1)
    assert published.is_current is True
    assert published.status == "published"
    assert published.effective_from is not None


@pytest.mark.asyncio
async def test_publish_replaces_previous_current(db_session: AsyncSession):
    schema = await _seed_schema_with_rules(db_session, 1, schema_id="v1")
    svc = ComplianceService(db_session)
    await svc.publish_schema(1, schema.id, actor_id=1)

    # Create a second version
    schema2 = await _seed_schema_with_rules(
        db_session, 1, schema_id="v1",
        rules=[{
            "rule_code": "student.has_roll",
            "rule_type": "field_exists",
            "target_entity": "student",
            "target_field": "roll_number",
        }],
    )
    await svc.publish_schema(1, schema2.id, actor_id=1)

    # v1 should no longer be current
    old = await svc.get_schema(1, schema.id)
    assert old.is_current is False


# ---------------------------------------------------------------------------
# 3. Rule evaluation — field_exists
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eval_field_exists_pass(db_session: AsyncSession):
    schema = await _seed_schema_with_rules(db_session, 1)
    svc = ComplianceService(db_session)

    sub = await svc.submit(
        1,
        schema_pk=schema.id,
        submission_id="SUB-1",
        title="Test Submission",
        data_snapshot={"student": {"name": "Alice", "age": 12}},
        actor_id=1,
    )
    assert sub.status == "completed"
    assert sub.passed == 2
    assert sub.failed == 0
    assert sub.compliance_score == 100.0


@pytest.mark.asyncio
async def test_eval_field_exists_fail(db_session: AsyncSession):
    schema = await _seed_schema_with_rules(db_session, 1)
    svc = ComplianceService(db_session)

    sub = await svc.submit(
        1,
        schema_pk=schema.id,
        submission_id="SUB-2",
        title="Test Submission",
        data_snapshot={"student": {"age": 12}},  # missing name
        actor_id=1,
    )
    assert sub.failed == 1
    assert sub.compliance_score == 50.0


# ---------------------------------------------------------------------------
# 4. Rule evaluation — value_range
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eval_value_range_pass(db_session: AsyncSession):
    schema = await _seed_schema_with_rules(db_session, 1)
    svc = ComplianceService(db_session)

    sub = await svc.submit(
        1,
        schema_pk=schema.id,
        submission_id="SUB-3",
        title="Range Test",
        data_snapshot={"student": {"name": "Bob", "age": 15}},
        actor_id=1,
    )
    assert sub.passed == 2


@pytest.mark.asyncio
async def test_eval_value_range_fail(db_session: AsyncSession):
    schema = await _seed_schema_with_rules(db_session, 1)
    svc = ComplianceService(db_session)

    sub = await svc.submit(
        1,
        schema_pk=schema.id,
        submission_id="SUB-4",
        title="Range Test",
        data_snapshot={"student": {"name": "Bob", "age": 25}},
        actor_id=1,
    )
    assert sub.failed == 1  # age out of range


# ---------------------------------------------------------------------------
# 5. Rule evaluation — count_min
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eval_count_min(db_session: AsyncSession):
    schema = await _seed_schema_with_rules(
        db_session, 1,
        rules=[{
            "rule_code": "student.count_min",
            "rule_type": "count_min",
            "target_entity": "student",
            "condition": {"min": 1},
            "severity": "high",
            "explanation": "At least 1 student must exist",
        }],
    )
    svc = ComplianceService(db_session)
    sub = await svc.submit(
        1,
        schema_pk=schema.id,
        submission_id="SUB-5",
        title="Count Test",
        actor_id=1,
    )
    # Result depends on actual student count in test DB
    assert sub.total_rules == 1


# ---------------------------------------------------------------------------
# 6. Rule evaluation — ratio_min
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eval_ratio_min(db_session: AsyncSession):
    schema = await _seed_schema_with_rules(
        db_session, 1,
        rules=[{
            "rule_code": "student.pass_rate",
            "rule_type": "ratio_min",
            "target_entity": "student",
            "condition": {
                "numerator_value": 80,
                "denominator_value": 100,
                "min": 0.75,
            },
            "severity": "medium",
            "explanation": "Pass rate must be at least 75%",
        }],
    )
    svc = ComplianceService(db_session)
    sub = await svc.submit(
        1,
        schema_pk=schema.id,
        submission_id="SUB-6",
        title="Ratio Test",
        actor_id=1,
    )
    assert sub.passed == 1  # 80% >= 75%


@pytest.mark.asyncio
async def test_eval_ratio_min_fail(db_session: AsyncSession):
    schema = await _seed_schema_with_rules(
        db_session, 1,
        rules=[{
            "rule_code": "student.pass_rate",
            "rule_type": "ratio_min",
            "target_entity": "student",
            "condition": {
                "numerator_value": 60,
                "denominator_value": 100,
                "min": 0.75,
            },
            "severity": "medium",
        }],
    )
    svc = ComplianceService(db_session)
    sub = await svc.submit(
        1,
        schema_pk=schema.id,
        submission_id="SUB-7",
        title="Ratio Fail",
        actor_id=1,
    )
    assert sub.failed == 1  # 60% < 75%


# ---------------------------------------------------------------------------
# 7. Explainability
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_explainability(db_session: AsyncSession):
    schema = await _seed_schema_with_rules(db_session, 1)
    svc = ComplianceService(db_session)

    sub = await svc.submit(
        1,
        schema_pk=schema.id,
        submission_id="SUB-8",
        title="Explain Test",
        data_snapshot={"student": {"name": "Carol", "age": 10}},
        actor_id=1,
    )

    explanations = await svc.get_explanations(sub.id)
    assert len(explanations) == 2
    for exp in explanations:
        assert exp.result == "pass"
        assert exp.explanation is not None
        assert len(exp.trace_steps) > 0  # Has trace


@pytest.mark.asyncio
async def test_explainability_failure_trace(db_session: AsyncSession):
    schema = await _seed_schema_with_rules(db_session, 1)
    svc = ComplianceService(db_session)

    sub = await svc.submit(
        1,
        schema_pk=schema.id,
        submission_id="SUB-9",
        title="Fail Trace",
        data_snapshot={"student": {"age": 10}},  # missing name
        actor_id=1,
    )

    evals = await svc.get_evaluations(sub.id)
    fail_evals = [e for e in evals if e.result == "fail"]
    assert len(fail_evals) == 1
    assert fail_evals[0].explanation is not None
    assert fail_evals[0].trace is not None
    assert "steps" in fail_evals[0].trace


# ---------------------------------------------------------------------------
# 8. Approval workflow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approval_workflow(db_session: AsyncSession):
    schema = await _seed_schema_with_rules(db_session, 1)
    svc = ComplianceService(db_session)

    sub = await svc.submit(
        1,
        schema_pk=schema.id,
        submission_id="SUB-10",
        title="Approval Test",
        data_snapshot={"student": {"name": "Dan", "age": 14}},
        actor_id=1,
    )

    approval = await svc.approve_submission(
        1, sub.id, decision="approved", comment="Looks good", actor_id=2
    )
    assert approval.decision == "approved"

    # Refresh submission
    loaded = await svc.get_submission(1, sub.id)
    assert loaded.status == "approved"


@pytest.mark.asyncio
async def test_rejection_workflow(db_session: AsyncSession):
    schema = await _seed_schema_with_rules(db_session, 1)
    svc = ComplianceService(db_session)

    sub = await svc.submit(
        1,
        schema_pk=schema.id,
        submission_id="SUB-11",
        title="Reject Test",
        data_snapshot={"student": {"name": "Eve", "age": 30}},
        actor_id=1,
    )

    await svc.approve_submission(
        1, sub.id, decision="rejected", comment="Age out of range"
    )
    loaded = await svc.get_submission(1, sub.id)
    assert loaded.status == "rejected"


# ---------------------------------------------------------------------------
# 9. Dashboard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard(db_session: AsyncSession):
    reg = await _seed_regulation(db_session, 1, "dash_reg")
    await _seed_requirement(db_session, 1, reg, "D1")
    schema = await _seed_schema_with_rules(db_session, 1, schema_id="dash_schema")
    await svc_publish(db_session, schema.id)
    svc = ComplianceService(db_session)
    await svc.submit(
        1,
        schema_pk=schema.id,
        submission_id="DASH-SUB",
        title="Dashboard Sub",
        data_snapshot={"student": {"name": "Fig", "age": 11}},
        actor_id=1,
    )

    dashboard = await svc.dashboard(1)
    assert dashboard["total_regulations"] == 1
    assert dashboard["total_schemas"] >= 1
    assert dashboard["total_submissions"] >= 1
    assert dashboard["average_score"] is not None


async def svc_publish(db_session: AsyncSession, schema_id: int):
    svc = ComplianceService(db_session)
    await svc.publish_schema(1, schema_id, actor_id=1)


# ---------------------------------------------------------------------------
# 10. Tenant isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tenant_isolation(db_session: AsyncSession):
    await _seed_regulation(db_session, 1, "iso_a")
    await _seed_regulation(db_session, 2, "iso_b")
    svc = ComplianceService(db_session)

    regs_a = await svc.list_regulations(1)
    regs_b = await svc.list_regulations(2)
    assert len(regs_a) == 1
    assert len(regs_b) == 1
    assert regs_a[0].regulation_id != regs_b[0].regulation_id


# ---------------------------------------------------------------------------
# 11. Empty / missing data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_empty_data(db_session: AsyncSession):
    schema = await _seed_schema_with_rules(db_session, 1)
    svc = ComplianceService(db_session)

    sub = await svc.submit(
        1,
        schema_pk=schema.id,
        submission_id="EMPTY",
        title="Empty Data",
        data_snapshot={},
        actor_id=1,
    )
    assert sub.total_rules == 2
    assert sub.failed == 2  # both rules fail with empty data


@pytest.mark.asyncio
async def test_submit_no_schema(db_session: AsyncSession):
    svc = ComplianceService(db_session)
    sub = await svc.submit(
        1,
        schema_pk=999,
        submission_id="NO-SCHEMA",
        title="No Schema",
        data_snapshot={"student": {"name": "Test"}},
        actor_id=1,
    )
    assert sub.total_rules == 0
    assert sub.compliance_score is None


# ---------------------------------------------------------------------------
# 12. Custom query rule
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_custom_query_rule(db_session: AsyncSession):
    schema = await _seed_schema_with_rules(
        db_session, 1,
        rules=[{
            "rule_code": "data.has_enrollment",
            "rule_type": "custom_query",
            "target_entity": "student",
            "condition": {"name": "enrollment_check", "check_field": "enrollment_count"},
            "expected": {"type": "gt", "value": 0},
            "severity": "medium",
            "explanation": "Student must have at least one enrollment",
        }],
    )
    svc = ComplianceService(db_session)
    sub = await svc.submit(
        1,
        schema_pk=schema.id,
        submission_id="CQ-1",
        title="Custom Query",
        data_snapshot={"enrollment_count": 3},
        actor_id=1,
    )
    assert sub.passed == 1


@pytest.mark.asyncio
async def test_custom_query_rule_fail(db_session: AsyncSession):
    schema = await _seed_schema_with_rules(
        db_session, 1,
        rules=[{
            "rule_code": "data.has_enrollment",
            "rule_type": "custom_query",
            "target_entity": "student",
            "condition": {"name": "enrollment_check", "check_field": "enrollment_count"},
            "expected": {"type": "gt", "value": 0},
            "severity": "medium",
        }],
    )
    svc = ComplianceService(db_session)
    sub = await svc.submit(
        1,
        schema_pk=schema.id,
        submission_id="CQ-2",
        title="Custom Query Fail",
        data_snapshot={"enrollment_count": 0},
        actor_id=1,
    )
    assert sub.failed == 1
