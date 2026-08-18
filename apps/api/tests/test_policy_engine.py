"""Policy-as-code foundation tests (TASK 11).

Covers:

- deterministic rule evaluator (operators, combinators, fail-closed)
- policy lifecycle: create → add version → publish (approval) → retire
- versioning: sequential numbers, idempotent re-create by policy_id
- effective dates: version windows, ending the previous current window
- exceptions: waiving denials (allow) and downgrading denials (review)
- applicability: not_applicable decision
- determinism: same input + same version → same result
- traceability: every evaluation persisted (version + input + result)
- rule validation at add_version (unknown operator / bad effect rejected)
- tenant isolation (campus A can never see / mutate campus B policies)
"""

from __future__ import annotations

import datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.audit.actors import ActorType, AuditActor
from app.multi_tenant.models import TenantContext
from app.platform.policy.models import (
    DECISION_ALLOW,
    DECISION_DENY,
    DECISION_NOT_APPLICABLE,
    DECISION_REVIEW,
    POLICY_STATUS_ACTIVE,
    POLICY_STATUS_DRAFT,
    PolicyEvaluation,
    PolicyVersion,
)
from app.platform.policy.rules import evaluate_condition, get_path
from app.platform.policy.schemas import (
    Condition,
    EvaluateInput,
    ExceptionDef,
    PolicyCreate,
    PolicyVersionCreate,
    PublishVersion,
    RuleDef,
)
from app.platform.policy.service import PolicyService


@pytest.fixture
def tenant_a() -> TenantContext:
    return TenantContext(campus_id=1, institution_id=1, user_id=99)


@pytest.fixture
def tenant_b() -> TenantContext:
    return TenantContext(campus_id=2, institution_id=1, user_id=98)


def _actor(user_id: int = 99) -> AuditActor:
    return AuditActor(actor_type=ActorType.USER, actor_id=str(user_id))


# ---------------------------------------------------------------------------
# Pure rule evaluator
# ---------------------------------------------------------------------------

ATTENDANCE_RULE: dict[str, Any] = {
    "id": "min-attendance-85",
    "description": "Students below 85% attendance require review",
    "condition": {"op": "lt", "field": "attendance.rate", "value": 0.85},
    "effect": "review",
    "reason": "attendance below threshold",
}


class TestRuleEvaluator:
    def test_get_path_dotted(self) -> None:
        data = {"student": {"id": "S1"}, "attendance": {"rate": 0.7}}
        assert get_path(data, "attendance.rate") == 0.7
        assert get_path(data, "student.id") == "S1"
        assert get_path(data, "missing.path", "default") == "default"

    def test_comparisons(self) -> None:
        assert evaluate_condition({"op": "eq", "field": "grade", "value": 10}, {"grade": 10})
        # Numeric-aware: "45000" equals 45000.
        assert evaluate_condition(
            {"op": "eq", "field": "amount", "value": 45000}, {"amount": "45000"}
        )
        assert not evaluate_condition({"op": "eq", "field": "grade", "value": 9}, {"grade": 10})
        assert evaluate_condition({"op": "neq", "field": "grade", "value": 9}, {"grade": 10})
        assert evaluate_condition({"op": "lt", "field": "rate", "value": 0.85}, {"rate": 0.7})
        assert evaluate_condition({"op": "gte", "field": "rate", "value": 0.85}, {"rate": 0.9})
        # String numeric coercion.
        assert evaluate_condition({"op": "lt", "field": "rate", "value": 0.85}, {"rate": "0.70"})

    def test_membership_and_presence(self) -> None:
        data = {"section": "A", "tags": ["athlete", "scholar"], "email": None}
        assert evaluate_condition({"op": "in", "field": "section", "value": ["A", "B"]}, data)
        assert evaluate_condition({"op": "not_in", "field": "section", "value": ["C"]}, data)
        assert evaluate_condition({"op": "contains", "field": "tags", "value": "scholar"}, data)
        assert evaluate_condition({"op": "exists", "field": "section"}, data)
        assert not evaluate_condition({"op": "exists", "field": "email"}, data)
        assert evaluate_condition({"op": "not_exists", "field": "email"}, data)
        assert evaluate_condition({"op": "is_true", "field": "waiver"}, {"waiver": True})
        assert evaluate_condition({"op": "is_false", "field": "waiver"}, {"waiver": False})

    def test_combinators(self) -> None:
        cond = {
            "op": "and",
            "conditions": [
                {"op": "lt", "field": "attendance.rate", "value": 0.85},
                {"op": "exists", "field": "student.id"},
            ],
        }
        data = {"attendance": {"rate": 0.7}, "student": {"id": "S1"}}
        assert evaluate_condition(cond, data)
        assert not evaluate_condition(cond, {"attendance": {"rate": 0.9}, "student": {"id": "S1"}})

        or_cond = {
            "op": "or",
            "conditions": [
                {"op": "eq", "field": "a", "value": 1},
                {"op": "eq", "field": "b", "value": 2},
            ],
        }
        assert evaluate_condition(or_cond, {"a": 1, "b": 3})
        not_cond = {"op": "not", "condition": {"op": "eq", "field": "a", "value": 1}}
        assert evaluate_condition(not_cond, {"a": 2})

    def test_unknown_operator_fails_closed(self) -> None:
        assert not evaluate_condition({"op": "eval", "field": "x", "value": 1}, {"x": 1})
        assert not evaluate_condition({"op": "lt", "field": "x", "value": "not-a-number"}, {"x": 1})

    def test_deterministic(self) -> None:
        data = {"attendance": {"rate": 0.7}}
        assert evaluate_condition(ATTENDANCE_RULE["condition"], data) is True
        assert evaluate_condition(ATTENDANCE_RULE["condition"], data) is True


# ---------------------------------------------------------------------------
# Lifecycle helpers
# ---------------------------------------------------------------------------


def _policy_create(**overrides) -> PolicyCreate:
    base = {
        "policy_id": "attendance.min_attendance",
        "name": "Minimum attendance policy",
        "scope": "attendance",
        "scope_ref": "student",
    }
    base.update(overrides)
    return PolicyCreate(**base)


def _version_create(**overrides) -> PolicyVersionCreate:
    base = {
        "title": "v1 — 85% attendance",
        "rules": [
            RuleDef(
                id="min-attendance-85",
                condition=Condition(op="lt", field="attendance.rate", value=0.85),
                effect="review",
                reason="attendance below threshold",
            )
        ],
        "exceptions": [],
    }
    base.update(overrides)
    return PolicyVersionCreate(**base)


async def _published_policy(
    db_session: AsyncSession,
    tenant: TenantContext,
    *,
    policy_id: str = "attendance.min_attendance",
    scope: str = "attendance",
    effective_from: datetime.datetime | None = None,
) -> tuple[PolicyService, PolicyVersion]:
    svc = PolicyService(db_session, tenant)
    policy = await svc.create_policy(
        _policy_create(policy_id=policy_id, scope=scope), actor=_actor()
    )
    version = await svc.add_version(policy.id, _version_create(), actor=_actor())
    version = await svc.publish_version(
        version.id,
        PublishVersion(note="approved by principal", effective_from=effective_from),
        actor=_actor(),
    )
    return svc, version


# ---------------------------------------------------------------------------
# Lifecycle + versioning
# ---------------------------------------------------------------------------


class TestLifecycle:
    async def test_create_policy_idempotent(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = PolicyService(db_session, tenant_a)
        policy = await svc.create_policy(_policy_create(), actor=_actor())
        assert policy.campus_id == 1
        assert policy.scope == "attendance"
        assert policy.status == POLICY_STATUS_DRAFT

        # Same business key → same policy, no duplicate.
        again = await svc.create_policy(_policy_create(), actor=_actor())
        assert again.id == policy.id
        policies, total = await svc.list_policies()
        assert total == 1

    async def test_invalid_scope_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = PolicyService(db_session, tenant_a)
        with pytest.raises(ValidationError):
            await svc.create_policy(_policy_create(scope="sports"), actor=_actor())

    async def test_add_version_sequential(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = PolicyService(db_session, tenant_a)
        policy = await svc.create_policy(_policy_create(), actor=_actor())
        v1 = await svc.add_version(policy.id, _version_create(title="v1"), actor=_actor())
        v2 = await svc.add_version(
            policy.id,
            _version_create(title="v2 — 90% attendance", rules=[]),
            actor=_actor(),
        )
        assert (v1.version, v2.version) == (1, 2)
        versions, total = await svc.list_versions(policy.id)
        assert total == 2
        assert [v.version for v in versions] == [1, 2]

    async def test_add_version_validates_rules(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = PolicyService(db_session, tenant_a)
        policy = await svc.create_policy(_policy_create(), actor=_actor())
        # Unknown operator → rejected before persist.
        with pytest.raises(ValidationError):
            await svc.add_version(
                policy.id,
                _version_create(
                    rules=[
                        RuleDef(
                            id="bad-op",
                            condition=Condition(op="eval", field="x", value=1),
                            effect="deny",
                        )
                    ]
                ),
                actor=_actor(),
            )
        # Effect not allowed in scope → rejected.
        with pytest.raises(ValidationError):
            await svc.add_version(
                policy.id,
                _version_create(
                    rules=[
                        RuleDef(
                            id="bad-effect",
                            condition=Condition(op="eq", field="x", value=1),
                            effect="explode",
                        )
                    ]
                ),
                actor=_actor(),
            )
        # Bad exception effect → rejected.
        with pytest.raises(ValidationError):
            await svc.add_version(
                policy.id,
                _version_create(
                    exceptions=[
                        ExceptionDef(
                            id="bad-exc",
                            condition=Condition(op="eq", field="x", value=1),
                            effect="explode",
                        )
                    ]
                ),
                actor=_actor(),
            )
        # Nothing persisted.
        versions, total = await svc.list_versions(policy.id)
        assert total == 0

    async def test_publish_sets_approval_metadata(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, version = await _published_policy(db_session, tenant_a)
        assert version.status == "published"
        assert version.is_current is True
        assert version.approved_by == 99
        assert version.approved_at is not None
        assert version.approval_note == "approved by principal"
        assert version.effective_from is not None

        policy = await svc.get_policy(version.policy_def_id)
        assert policy.status == POLICY_STATUS_ACTIVE

    async def test_publish_only_draft(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, version = await _published_policy(db_session, tenant_a)
        with pytest.raises(ConflictError):
            await svc.publish_version(version.id, PublishVersion(), actor=_actor())

    async def test_publish_validation_effective_window(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = PolicyService(db_session, tenant_a)
        policy = await svc.create_policy(_policy_create(), actor=_actor())
        version = await svc.add_version(
            policy.id,
            _version_create(
                effective_until=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
            ),
            actor=_actor(),
        )
        with pytest.raises(ValidationError):
            await svc.publish_version(
                version.id,
                PublishVersion(
                    effective_from=datetime.datetime(2026, 6, 1, tzinfo=datetime.timezone.utc)
                ),
                actor=_actor(),
            )

    async def test_retire_version(self, db_session: AsyncSession, tenant_a: TenantContext) -> None:
        svc, version = await _published_policy(db_session, tenant_a)
        retired = await svc.retire_version(version.id, actor=_actor())
        assert retired.status == "retired"
        assert retired.is_current is False
        # No published version remains → policy back to draft.
        policy = await svc.get_policy(version.policy_def_id)
        assert policy.status == POLICY_STATUS_DRAFT
        with pytest.raises(ConflictError):
            await svc.retire_version(version.id, actor=_actor())


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


class TestEvaluation:
    async def test_evaluate_review_decision(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, version = await _published_policy(db_session, tenant_a)
        result = await svc.evaluate(
            "attendance.min_attendance",
            EvaluateInput(
                subject_type="student",
                subject_id="S1",
                data={"attendance": {"rate": 0.7}, "student": {"id": "S1"}},
            ),
            actor=_actor(),
        )
        assert result.decision == DECISION_REVIEW
        assert result.version == 1
        assert result.applicable is True
        assert len(result.rule_results) == 1
        assert result.rule_results[0].rule_id == "min-attendance-85"
        assert result.rule_results[0].satisfied is True
        assert "attendance below threshold" in result.reason

    async def test_evaluate_allow_when_rule_not_matched(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, version = await _published_policy(db_session, tenant_a)
        result = await svc.evaluate(
            "attendance.min_attendance",
            EvaluateInput(data={"attendance": {"rate": 0.95}}),
            actor=_actor(),
        )
        assert result.decision == DECISION_ALLOW

    async def test_deny_waived_by_allow_exception(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = PolicyService(db_session, tenant_a)
        policy = await svc.create_policy(
            _policy_create(policy_id="fees.late_fee", scope="fees"), actor=_actor()
        )
        version = await svc.add_version(
            policy.id,
            _version_create(
                title="Late fee on overdue",
                rules=[
                    RuleDef(
                        id="overdue-deny",
                        condition=Condition(op="gt", field="days_overdue", value=30),
                        effect="deny",
                        reason="overdue beyond grace",
                    )
                ],
                exceptions=[
                    ExceptionDef(
                        id="medical-waiver",
                        condition=Condition(op="is_true", field="waiver.medical"),
                        reason="medical hardship waiver",
                    )
                ],
            ),
            actor=_actor(),
        )
        await svc.publish_version(version.id, PublishVersion(note="ok"), actor=_actor())

        # Without waiver → deny.
        denied = await svc.evaluate(
            "fees.late_fee",
            EvaluateInput(data={"days_overdue": 45, "waiver": {"medical": False}}),
            actor=_actor(),
        )
        assert denied.decision == DECISION_DENY
        assert "overdue beyond grace" in denied.reason

        # With waiver → allow (exception applied).
        allowed = await svc.evaluate(
            "fees.late_fee",
            EvaluateInput(data={"days_overdue": 45, "waiver": {"medical": True}}),
            actor=_actor(),
        )
        assert allowed.decision == DECISION_ALLOW
        assert "medical-waiver" in allowed.reason
        applied = [e for e in allowed.exceptions_applied if e.satisfied]
        assert applied and applied[0].exception_id == "medical-waiver"

    async def test_deny_downgraded_by_review_exception(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = PolicyService(db_session, tenant_a)
        policy = await svc.create_policy(
            _policy_create(policy_id="admissions.age_limit", scope="admissions"), actor=_actor()
        )
        version = await svc.add_version(
            policy.id,
            _version_create(
                title="Age limit",
                rules=[
                    RuleDef(
                        id="underage-deny",
                        condition=Condition(op="lt", field="age", value=16),
                        effect="deny",
                        reason="below admission age",
                    )
                ],
                exceptions=[
                    ExceptionDef(
                        id="talent-review",
                        condition=Condition(op="is_true", field="sports.talent"),
                        effect="review",
                        reason="talent pathway under review",
                    )
                ],
            ),
            actor=_actor(),
        )
        await svc.publish_version(version.id, PublishVersion(note="ok"), actor=_actor())

        result = await svc.evaluate(
            "admissions.age_limit",
            EvaluateInput(data={"age": 15, "sports": {"talent": True}}),
            actor=_actor(),
        )
        assert result.decision == DECISION_REVIEW
        assert "talent-review" in result.reason

    async def test_applicability_not_applicable(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = PolicyService(db_session, tenant_a)
        policy = await svc.create_policy(
            _policy_create(policy_id="attendance.student_only"), actor=_actor()
        )
        version = await svc.add_version(
            policy.id,
            _version_create(
                title="Student-only attendance policy",
                applicability=Condition(op="eq", field="subject.kind", value="student"),
                rules=[
                    RuleDef(
                        id="flag-low",
                        condition=Condition(op="lt", field="attendance.rate", value=0.85),
                        effect="review",
                    )
                ],
            ),
            actor=_actor(),
        )
        await svc.publish_version(version.id, PublishVersion(note="ok"), actor=_actor())

        n_a = await svc.evaluate(
            "attendance.student_only",
            EvaluateInput(data={"subject": {"kind": "teacher"}, "attendance": {"rate": 0.5}}),
            actor=_actor(),
        )
        assert n_a.decision == DECISION_NOT_APPLICABLE
        assert n_a.applicable is False

        applies = await svc.evaluate(
            "attendance.student_only",
            EvaluateInput(data={"subject": {"kind": "student"}, "attendance": {"rate": 0.5}}),
            actor=_actor(),
        )
        assert applies.decision == DECISION_REVIEW

    async def test_evaluate_unknown_policy_not_found(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = PolicyService(db_session, tenant_a)
        with pytest.raises(NotFoundError):
            await svc.evaluate("nope.missing", EvaluateInput(data={}), actor=_actor())

    async def test_evaluate_no_effective_version(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        # Draft-only policy → nothing effective → fail closed (NotFound).
        svc = PolicyService(db_session, tenant_a)
        policy = await svc.create_policy(_policy_create(), actor=_actor())
        await svc.add_version(policy.id, _version_create(), actor=_actor())
        with pytest.raises(NotFoundError):
            await svc.evaluate("attendance.min_attendance", EvaluateInput(data={}), actor=_actor())

    async def test_future_effective_date_not_effective(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)
        svc, version = await _published_policy(db_session, tenant_a, effective_from=future)
        with pytest.raises(NotFoundError):
            await svc.evaluate("attendance.min_attendance", EvaluateInput(data={}), actor=_actor())
        # Explicit version evaluation works regardless of window.
        result = await svc.evaluate_version(
            version.id, EvaluateInput(data={"attendance": {"rate": 0.5}})
        )
        assert result.decision == DECISION_REVIEW


# ---------------------------------------------------------------------------
# Determinism + traceability
# ---------------------------------------------------------------------------


class TestDeterminismAndTraceability:
    async def test_deterministic_across_calls(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, version = await _published_policy(db_session, tenant_a)
        inp = EvaluateInput(
            subject_type="student",
            subject_id="S9",
            data={"attendance": {"rate": 0.5}},
        )
        r1 = await svc.evaluate("attendance.min_attendance", inp, actor=_actor())
        r2 = await svc.evaluate("attendance.min_attendance", inp, actor=_actor())
        assert r1.decision == r2.decision
        assert r1.reason == r2.reason
        assert [o.model_dump() for o in r1.rule_results] == [
            o.model_dump() for o in r2.rule_results
        ]

    async def test_evaluation_persisted_and_queryable(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, version = await _published_policy(db_session, tenant_a)
        await svc.evaluate(
            "attendance.min_attendance",
            EvaluateInput(
                subject_type="student",
                subject_id="S7",
                data={"attendance": {"rate": 0.6}},
            ),
            actor=_actor(),
        )
        records = (await db_session.execute(select(PolicyEvaluation))).scalars().all()
        assert len(records) == 1
        rec = records[0]
        assert rec.policy_id == "attendance.min_attendance"
        assert rec.version == 1
        assert rec.policy_version_id == version.id
        assert rec.decision == DECISION_REVIEW
        assert rec.subject_id == "S7"
        assert rec.input_snapshot == {"attendance": {"rate": 0.6}}
        assert rec.result["decision"] == DECISION_REVIEW
        assert rec.evaluated_by == 99

        history, total = await svc.history(policy_id="attendance.min_attendance")
        assert total == 1
        by_subject, total = await svc.history(subject_type="student", subject_id="S7")
        assert total == 1

    async def test_evaluate_version_also_persists(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, version = await _published_policy(db_session, tenant_a)
        await svc.evaluate_version(version.id, EvaluateInput(data={"attendance": {"rate": 0.5}}))
        records = (await db_session.execute(select(PolicyEvaluation))).scalars().all()
        assert len(records) == 1


# ---------------------------------------------------------------------------
# Effective dates / version windows
# ---------------------------------------------------------------------------


class TestEffectiveDates:
    async def test_publish_v2_ends_v1_window(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = PolicyService(db_session, tenant_a)
        policy = await svc.create_policy(_policy_create(), actor=_actor())
        v1 = await svc.add_version(
            policy.id,
            _version_create(title="v1 — 85%", rules=[]),
            actor=_actor(),
        )
        await svc.publish_version(v1.id, PublishVersion(note="v1"), actor=_actor())
        v1 = await svc.repo.get_version_or_404(v1.id)
        assert v1.is_current is True

        v2 = await svc.add_version(
            policy.id,
            _version_create(
                title="v2 — 90%",
                rules=[
                    RuleDef(
                        id="min-attendance-90",
                        condition=Condition(op="lt", field="attendance.rate", value=0.9),
                        effect="review",
                    )
                ],
            ),
            actor=_actor(),
        )
        await svc.publish_version(v2.id, PublishVersion(note="v2"), actor=_actor())

        v1 = await svc.repo.get_version_or_404(v1.id)
        v2 = await svc.repo.get_version_or_404(v2.id)
        assert v1.is_current is False
        assert v1.effective_until is not None and v1.effective_until == v2.effective_from
        assert v2.is_current is True

        # Evaluation now uses v2.
        result = await svc.evaluate(
            "attendance.min_attendance",
            EvaluateInput(data={"attendance": {"rate": 0.87}}),
            actor=_actor(),
        )
        assert result.version == 2
        assert result.decision == DECISION_REVIEW  # below 90%, above 85%


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    async def test_cross_tenant_policy_invisible(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = PolicyService(db_session, tenant_a)
        policy = await svc_a.create_policy(_policy_create(), actor=_actor())
        assert policy.campus_id == 1

        svc_b = PolicyService(db_session, tenant_b)
        with pytest.raises(NotFoundError):
            await svc_b.get_policy(policy.id)
        with pytest.raises(NotFoundError):
            await svc_b.evaluate(
                "attendance.min_attendance", EvaluateInput(data={}), actor=_actor()
            )

        # B's policy list is empty even though A created one.
        policies_b, total_b = await svc_b.list_policies()
        assert total_b == 0

    async def test_cross_tenant_add_version_denied(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = PolicyService(db_session, tenant_a)
        policy = await svc_a.create_policy(_policy_create(), actor=_actor())
        svc_b = PolicyService(db_session, tenant_b)
        with pytest.raises(NotFoundError):
            await svc_b.add_version(policy.id, _version_create(), actor=_actor())

    async def test_cross_tenant_publish_denied(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = PolicyService(db_session, tenant_a)
        policy = await svc_a.create_policy(_policy_create(), actor=_actor())
        version = await svc_a.add_version(policy.id, _version_create(), actor=_actor())
        svc_b = PolicyService(db_session, tenant_b)
        with pytest.raises(NotFoundError):
            await svc_b.publish_version(version.id, PublishVersion(note="sneaky"), actor=_actor())

    async def test_same_policy_id_different_campus_ok(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = PolicyService(db_session, tenant_a)
        svc_b = PolicyService(db_session, tenant_b)
        policy_a = await svc_a.create_policy(_policy_create(), actor=_actor())
        policy_b = await svc_b.create_policy(_policy_create(), actor=_actor())
        assert policy_a.id != policy_b.id  # per-campus uniqueness on policy_id

    async def test_cross_tenant_history_invisible(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a, _ = await _published_policy(db_session, tenant_a)
        await svc_a.evaluate(
            "attendance.min_attendance",
            EvaluateInput(
                subject_type="student", subject_id="S1", data={"attendance": {"rate": 0.5}}
            ),
            actor=_actor(),
        )
        svc_b = PolicyService(db_session, tenant_b)
        history_b, total_b = await svc_b.history(policy_id="attendance.min_attendance")
        assert total_b == 0
