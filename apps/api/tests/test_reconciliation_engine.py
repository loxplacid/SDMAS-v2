"""Universal reconciliation engine tests (TASK 10).

Covers:

- deterministic matching primitives (normalizers, match keys, one-to-one)
- tolerance comparison (exact / absolute / percent / days)
- run creation idempotency (idempotency_key per campus)
- execution: matched / source_only / target_only / exception classification
- exception manual review (resolve / close)
- approval workflow (approve blocks on open exceptions, reject returns to draft)
- evidence attachment
- rule configs (save + run_from_rule)
- tenant isolation (campus A can never see / mutate campus B runs)
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.audit.actors import ActorType, AuditActor
from app.domains.audit.models import AuditLog
from app.multi_tenant.models import TenantContext
from app.platform.reconciliation.matching import (
    build_match_key,
    classify,
    compare_records,
    match_records,
    normalize_value,
    unmatched_targets,
)
from app.platform.reconciliation.models import (
    MATCH_STATUS_EXCEPTION,
    MATCH_STATUS_MATCHED,
    MATCH_STATUS_SOURCE_ONLY,
    MATCH_STATUS_TARGET_ONLY,
    RUN_STATUS_APPROVED,
    RUN_STATUS_CLOSED,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_DRAFT,
    RUN_STATUS_EXCEPTIONS_PENDING,
    ReconciliationRun,
)
from app.platform.reconciliation.repository import ReconciliationRepository
from app.platform.reconciliation.schemas import (
    ApprovalCreate,
    EvidenceCreate,
    ExceptionResolve,
    ReconcileInput,
    ReconciliationRunCreate,
    RuleConfigCreate,
)
from app.platform.reconciliation.service import ReconciliationService


@pytest.fixture
def tenant_a() -> TenantContext:
    return TenantContext(campus_id=1, institution_id=1, user_id=99)


@pytest.fixture
def tenant_b() -> TenantContext:
    return TenantContext(campus_id=2, institution_id=1, user_id=98)


def _actor(user_id: int = 99) -> AuditActor:
    return AuditActor(actor_type=ActorType.USER, actor_id=str(user_id))


# match key: legacy_id; comparison: amount (absolute tolerance 0)
PAYMENT_MATCH_KEYS = [
    {"source_field": "legacy_id", "target_field": "payment_ref", "normalizer": "exact"}
]
PAYMENT_COMPARISON = [
    {"source_field": "amount", "target_field": "amount", "tolerance": "absolute", "value": 0}
]

SOURCE_PAYMENTS = [
    {"legacy_id": "P-001", "amount": 45000},
    {"legacy_id": "P-002", "amount": 12000},
    {"legacy_id": "P-003", "amount": 8000},
    {"legacy_id": "P-004", "amount": 30000},
]
TARGET_PAYMENTS = [
    {"payment_ref": "P-001", "amount": 45000},
    {"payment_ref": "P-002", "amount": 12000},
    {"payment_ref": "P-003", "amount": 8001},  # off by 1 → exception (abs tol 0)
    # P-004 absent from target → source_only
    # P-999 exists only in target → target_only
    {"payment_ref": "P-999", "amount": 555},
]


def _run_create(**overrides) -> ReconciliationRunCreate:
    base = {
        "name": "Payments vs invoices Aug 2026",
        "run_type": "payment_invoice",
        "source_dataset": "payments.export",
        "target_dataset": "invoices",
        "match_keys": PAYMENT_MATCH_KEYS,
        "comparison_fields": PAYMENT_COMPARISON,
        "idempotency_key": "payments-vs-invoices-2026-08",
    }
    base.update(overrides)
    return ReconciliationRunCreate(**base)


# ---------------------------------------------------------------------------
# Pure matching primitives
# ---------------------------------------------------------------------------


class TestMatchingPrimitives:
    def test_normalizers(self) -> None:
        assert normalize_value("  ABC ", "lower") == "abc"
        assert normalize_value("+254 700 123 456", "digits") == "254700123456"
        assert normalize_value("2010-05-04", "iso_date") == "2010-05-04"
        assert normalize_value("45,000", "numeric") == 45000.0
        assert normalize_value(None, "lower") is None
        with pytest.raises(ValueError):
            normalize_value("x", "mystery")

    def test_build_match_key(self) -> None:
        key = build_match_key(
            {"legacy_id": "ADM-001", "name": "X"},
            [{"field": "legacy_id", "normalizer": "lower"}],
        )
        assert key == ("adm-001",)

    def test_match_records_one_to_one_and_deterministic(self) -> None:
        results = match_records(SOURCE_PAYMENTS, TARGET_PAYMENTS, PAYMENT_MATCH_KEYS)
        by_ref = {r["source"]["legacy_id"]: r for r in results}
        assert by_ref["P-001"]["status"] == MATCH_STATUS_MATCHED
        assert by_ref["P-002"]["status"] == MATCH_STATUS_MATCHED
        assert by_ref["P-003"]["status"] == MATCH_STATUS_MATCHED  # matched by key
        assert by_ref["P-004"]["status"] == MATCH_STATUS_SOURCE_ONLY

        # Deterministic: same input, same output.
        again = match_records(SOURCE_PAYMENTS, TARGET_PAYMENTS, PAYMENT_MATCH_KEYS)
        assert [r["source"]["legacy_id"] for r in again] == [
            r["source"]["legacy_id"] for r in results
        ]

    def test_match_one_target_never_matched_twice(self) -> None:
        # Two sources with the same key — only the first claims the target.
        sources = [
            {"legacy_id": "X-1", "amount": 10},
            {"legacy_id": "X-1", "amount": 10},
        ]
        targets = [{"payment_ref": "X-1", "amount": 10}]
        results = match_records(sources, targets, PAYMENT_MATCH_KEYS)
        assert [r["status"] for r in results] == [MATCH_STATUS_MATCHED, MATCH_STATUS_SOURCE_ONLY]

    def test_unmatched_targets(self) -> None:
        orphans = unmatched_targets(SOURCE_PAYMENTS, TARGET_PAYMENTS, PAYMENT_MATCH_KEYS)
        assert [t["payment_ref"] for t in orphans] == ["P-999"]

    def test_compare_records_tolerances(self) -> None:
        fields = [
            {
                "source_field": "amount",
                "target_field": "amount",
                "tolerance": "absolute",
                "value": 100,
            },
        ]
        ok = compare_records({"amount": 45000}, {"amount": 45050}, fields)
        assert ok["within_tolerance"] is True
        bad = compare_records({"amount": 45000}, {"amount": 45200}, fields)
        assert bad["within_tolerance"] is False
        assert bad["exceeded"] == ["amount"]

        pct = [
            {
                "source_field": "amount",
                "target_field": "amount",
                "tolerance": "percent",
                "value": 0.01,
            },
        ]
        assert (
            compare_records({"amount": 10000}, {"amount": 10050}, pct)["within_tolerance"] is True
        )
        assert (
            compare_records({"amount": 10000}, {"amount": 10200}, pct)["within_tolerance"] is False
        )

        days = [
            {"source_field": "date", "target_field": "date", "tolerance": "days", "value": 2},
        ]
        assert (
            compare_records({"date": "2026-08-01"}, {"date": "2026-08-02"}, days)[
                "within_tolerance"
            ]
            is True
        )
        assert (
            compare_records({"date": "2026-08-01"}, {"date": "2026-08-10"}, days)[
                "within_tolerance"
            ]
            is False
        )

        exact = [
            {"source_field": "code", "target_field": "code", "tolerance": "exact"},
        ]
        assert compare_records({"code": "A"}, {"code": "A"}, exact)["within_tolerance"] is True
        assert compare_records({"code": "A"}, {"code": "B"}, exact)["within_tolerance"] is False

    def test_classify(self) -> None:
        from app.platform.reconciliation.matching import CODE_TOLERANCE_EXCEEDED

        matched = {
            "source": {"amount": 100},
            "target": {"amount": 101},
            "status": MATCH_STATUS_MATCHED,
        }
        status, code, reason = classify(matched, PAYMENT_COMPARISON)
        assert status == MATCH_STATUS_EXCEPTION
        assert code == CODE_TOLERANCE_EXCEEDED
        assert reason is not None and "amount" in reason

        ok = {"source": {"amount": 100}, "target": {"amount": 100}, "status": MATCH_STATUS_MATCHED}
        assert classify(ok, PAYMENT_COMPARISON)[0] == MATCH_STATUS_MATCHED


# ---------------------------------------------------------------------------
# Run lifecycle + execution
# ---------------------------------------------------------------------------


class TestRunExecution:
    async def test_create_run_idempotent(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ReconciliationService(db_session, tenant_a)
        run = await svc.create_run(_run_create(), actor=_actor())
        assert run.campus_id == 1
        assert run.status == RUN_STATUS_DRAFT

        # Same idempotency key → same run, no duplicate.
        again = await svc.create_run(_run_create(), actor=_actor())
        assert again.id == run.id
        runs, total = await ReconciliationRepository(db_session, tenant_a).list_runs()
        assert total == 1

    async def test_execute_classifies_matched_source_target_exception(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ReconciliationService(db_session, tenant_a)
        run = await svc.create_run(_run_create(), actor=_actor())
        run = await svc.execute(
            run.id,
            ReconcileInput(source_records=SOURCE_PAYMENTS, target_records=TARGET_PAYMENTS),
            actor=_actor(),
        )
        assert run.status == RUN_STATUS_EXCEPTIONS_PENDING

        matches, total = await svc.list_matches(run.id)
        # 4 source rows + 1 unmatched target (P-999).
        assert total == 5
        by_status: dict[str, int] = {}
        for m in matches:
            by_status[m.status] = by_status.get(m.status, 0) + 1
        assert by_status[MATCH_STATUS_MATCHED] == 2  # P-001, P-002 (amounts equal)
        assert by_status[MATCH_STATUS_EXCEPTION] == 1  # P-003 (amount off by 1)
        assert by_status[MATCH_STATUS_SOURCE_ONLY] == 1  # P-004
        assert by_status[MATCH_STATUS_TARGET_ONLY] == 1  # P-999

        # Summary reflects the counts.
        assert run.summary["matched"] == 2
        assert run.summary["exceptions"] == 1
        assert run.summary["source_only"] == 1

        # Exception row created.
        exceptions, exc_total = await svc.list_exceptions(run.id)
        assert exc_total == 1
        assert exceptions[0].code == "TOLERANCE_EXCEEDED"
        assert exceptions[0].status == "open"

        # Audit recorded.
        entries = (await db_session.execute(select(AuditLog))).scalars().all()
        assert any(e.action == "RECONCILE" for e in entries)

    async def test_execute_completed_when_no_exceptions(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ReconciliationService(db_session, tenant_a)
        run = await svc.create_run(
            _run_create(
                idempotency_key="clean-pass",
                comparison_fields=[
                    {
                        "source_field": "amount",
                        "target_field": "amount",
                        "tolerance": "absolute",
                        "value": 5,
                    }
                ],
            ),
            actor=_actor(),
        )
        run = await svc.execute(
            run.id,
            ReconcileInput(source_records=SOURCE_PAYMENTS, target_records=TARGET_PAYMENTS),
            actor=_actor(),
        )
        # P-003 (8000 vs 8001) is within tolerance 5 → no exception; P-004
        # still source_only, P-999 still target_only → exceptions_pending
        # because unmatched rows count as exceptions.
        assert run.status == RUN_STATUS_EXCEPTIONS_PENDING

    async def test_execute_with_exact_tolerance_marks_critical(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ReconciliationService(db_session, tenant_a)
        run = await svc.create_run(_run_create(), actor=_actor())
        await svc.execute(
            run.id,
            ReconcileInput(source_records=SOURCE_PAYMENTS, target_records=TARGET_PAYMENTS),
            actor=_actor(),
        )
        exceptions, _ = await svc.list_exceptions(run.id)
        assert exceptions[0].severity == "critical"  # absolute tolerance 0 == strict

    async def test_rerun_returns_run_unchanged(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ReconciliationService(db_session, tenant_a)
        run = await svc.create_run(_run_create(), actor=_actor())
        await svc.execute(
            run.id,
            ReconcileInput(source_records=SOURCE_PAYMENTS, target_records=TARGET_PAYMENTS),
            actor=_actor(),
        )
        before = run.summary
        await svc.execute(
            run.id,
            ReconcileInput(source_records=SOURCE_PAYMENTS, target_records=TARGET_PAYMENTS),
            actor=_actor(),
        )
        assert run.summary == before
        matches, total = await svc.list_matches(run.id)
        # No duplicate matches from the second execute.
        assert total == 5

    async def test_execute_requires_match_keys(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ReconciliationService(db_session, tenant_a)
        run = await svc.create_run(
            _run_create(match_keys=[], idempotency_key="no-keys"), actor=_actor()
        )
        with pytest.raises(ValidationError):
            await svc.execute(
                run.id,
                ReconcileInput(source_records=[{}], target_records=[{}]),
            )


# ---------------------------------------------------------------------------
# Exceptions: manual review
# ---------------------------------------------------------------------------


class TestExceptionReview:
    async def _run_with_exception(self, db_session, tenant_a) -> ReconciliationRun:
        svc = ReconciliationService(db_session, tenant_a)
        run = await svc.create_run(_run_create(), actor=_actor())
        return await svc.execute(
            run.id,
            ReconcileInput(source_records=SOURCE_PAYMENTS, target_records=TARGET_PAYMENTS),
            actor=_actor(),
        )

    async def test_resolve_then_close(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ReconciliationService(db_session, tenant_a)
        await self._run_with_exception(db_session, tenant_a)
        exceptions, _ = await svc.list_exceptions(1)
        assert exceptions[0].status == "open"

        resolved = await svc.resolve_exception(
            exceptions[0].id,
            ExceptionResolve(
                decision="accept",
                note="1 currency unit rounding",
                resolved_by=55,
            ),
            actor=_actor(),
        )
        assert resolved.status == "resolved"
        assert resolved.resolution["decision"] == "accept"
        assert resolved.resolved_by == 55
        assert resolved.resolved_at is not None

        closed = await svc.close_exception(resolved.id, actor=_actor())
        assert closed.status == "closed"

        # Re-resolving a resolved exception conflicts.
        with pytest.raises(ConflictError):
            await svc.resolve_exception(
                closed.id, ExceptionResolve(decision="accept"), actor=_actor()
            )

    async def test_correct_decision_records_value(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ReconciliationService(db_session, tenant_a)
        await self._run_with_exception(db_session, tenant_a)
        exceptions, _ = await svc.list_exceptions(1)
        resolved = await svc.resolve_exception(
            exceptions[0].id,
            ExceptionResolve(decision="correct", corrected_value=8001),
            actor=_actor(),
        )
        assert resolved.resolution["corrected_value"] == 8001


# ---------------------------------------------------------------------------
# Approval workflow
# ---------------------------------------------------------------------------


class TestApproval:
    async def test_approve_blocks_on_open_exceptions(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ReconciliationService(db_session, tenant_a)
        run = await svc.create_run(_run_create(), actor=_actor())
        await svc.execute(
            run.id,
            ReconcileInput(source_records=SOURCE_PAYMENTS, target_records=TARGET_PAYMENTS),
            actor=_actor(),
        )
        with pytest.raises(ConflictError):
            await svc.approve(
                run.id,
                ApprovalCreate(decision="approve", approver_id=7, comment="looks good"),
                actor=_actor(),
            )

    async def test_resolve_then_approve_then_close(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ReconciliationService(db_session, tenant_a)
        run = await svc.create_run(_run_create(), actor=_actor())
        await svc.execute(
            run.id,
            ReconcileInput(source_records=SOURCE_PAYMENTS, target_records=TARGET_PAYMENTS),
            actor=_actor(),
        )
        # Resolve all open exceptions (tolerance + source_only + target_only).
        exceptions, total = await svc.list_exceptions(run.id)
        # source_only/target_only rows become exceptions too.
        from app.platform.reconciliation.models import EXCEPTION_STATUS_OPEN

        open_exceptions = [e for e in exceptions if e.status == EXCEPTION_STATUS_OPEN]
        for exc in open_exceptions:
            await svc.resolve_exception(
                exc.id, ExceptionResolve(decision="accept", note="verified"), actor=_actor()
            )

        run = await svc.approve(
            run.id,
            ApprovalCreate(decision="approve", approver_id=7, comment="approved"),
            actor=_actor(),
        )
        assert run.status == RUN_STATUS_APPROVED
        assert run.approved_by == 7
        assert run.approved_at is not None

        approvals = await svc.approvals(run.id)
        assert len(approvals) == 1
        assert approvals[0].decision == "approve"
        assert approvals[0].approver_id == 7

        closed = await svc.close_run(run.id, actor=_actor())
        assert closed.status == RUN_STATUS_CLOSED

    async def test_reject_returns_to_draft(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ReconciliationService(db_session, tenant_a)
        run = await svc.create_run(
            _run_create(
                idempotency_key="clean-2",
                match_keys=PAYMENT_MATCH_KEYS,
                comparison_fields=[
                    {
                        "source_field": "amount",
                        "target_field": "amount",
                        "tolerance": "absolute",
                        "value": 100,
                    }
                ],
            ),
            actor=_actor(),
        )
        run = await svc.execute(
            run.id,
            ReconcileInput(
                source_records=[{"legacy_id": "A", "amount": 10}],
                target_records=[{"payment_ref": "A", "amount": 11}],
            ),
            actor=_actor(),
        )
        assert run.status == RUN_STATUS_COMPLETED  # within tolerance 100

        run = await svc.approve(
            run.id,
            ApprovalCreate(decision="reject", approver_id=3, comment="re-run needed"),
            actor=_actor(),
        )
        assert run.status == RUN_STATUS_DRAFT

    async def test_rejects_bad_decision(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ReconciliationService(db_session, tenant_a)
        run = await svc.create_run(_run_create(), actor=_actor())
        with pytest.raises(ValidationError):
            await svc.approve(run.id, ApprovalCreate(decision="maybe"), actor=_actor())


# ---------------------------------------------------------------------------
# Evidence + rule configs
# ---------------------------------------------------------------------------


class TestEvidenceAndRules:
    async def test_attach_evidence(self, db_session: AsyncSession, tenant_a: TenantContext) -> None:
        svc = ReconciliationService(db_session, tenant_a)
        run = await svc.create_run(_run_create(), actor=_actor())
        ev = await svc.attach_evidence(
            run.id,
            EvidenceCreate(
                kind="file",
                reference="s3://audit/payments-aug-2026.csv",
                checksum="sha256:abc",
                note="Source export",
            ),
            actor=_actor(),
        )
        assert ev.campus_id == 1
        listed = await svc.evidence(run.id)
        assert [e.id for e in listed] == [ev.id]

    async def test_save_rule_and_run_from_rule(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ReconciliationService(db_session, tenant_a)
        rule = await svc.save_rule(
            RuleConfigCreate(
                name="payments-vs-invoices",
                run_type="payment_invoice",
                description="Standard payments↔invoices rule",
                match_keys=PAYMENT_MATCH_KEYS,
                comparison_fields=PAYMENT_COMPARISON,
            ),
            actor=_actor(),
        )
        # Idempotent save.
        again = await svc.save_rule(
            RuleConfigCreate(
                name="payments-vs-invoices",
                run_type="payment_invoice",
                match_keys=PAYMENT_MATCH_KEYS,
                comparison_fields=PAYMENT_COMPARISON,
            ),
            actor=_actor(),
        )
        assert again.id == rule.id

        run = await svc.run_from_rule(
            rule.id,
            name="Payments pass from rule",
            source_dataset="payments.export",
            target_dataset="invoices",
        )
        assert run.rule_config_id == rule.id
        assert run.match_keys == PAYMENT_MATCH_KEYS


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    async def test_cross_tenant_run_invisible(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = ReconciliationService(db_session, tenant_a)
        svc_b = ReconciliationService(db_session, tenant_b)
        run = await svc_a.create_run(_run_create(), actor=_actor())
        assert run.campus_id == 1

        with pytest.raises(NotFoundError):
            await svc_b.get_run(run.id)
        with pytest.raises(NotFoundError):
            await svc_b.list_matches(run.id)

    async def test_cross_tenant_approve_denied(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = ReconciliationService(db_session, tenant_a)
        svc_b = ReconciliationService(db_session, tenant_b)
        run = await svc_a.create_run(_run_create(), actor=_actor())
        with pytest.raises(NotFoundError):
            await svc_b.approve(run.id, ApprovalCreate(decision="approve"), actor=_actor())

    async def test_cross_tenant_resolve_exception_denied(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = ReconciliationService(db_session, tenant_a)
        svc_b = ReconciliationService(db_session, tenant_b)
        run = await svc_a.create_run(_run_create(), actor=_actor())
        await svc_a.execute(
            run.id,
            ReconcileInput(source_records=SOURCE_PAYMENTS, target_records=TARGET_PAYMENTS),
            actor=_actor(),
        )
        exceptions, _ = await svc_a.list_exceptions(run.id)
        with pytest.raises(NotFoundError):
            await svc_b.resolve_exception(
                exceptions[0].id,
                ExceptionResolve(decision="accept"),
                actor=_actor(),
            )

    async def test_same_idempotency_key_different_campus_ok(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = ReconciliationService(db_session, tenant_a)
        svc_b = ReconciliationService(db_session, tenant_b)
        run_a = await svc_a.create_run(_run_create(), actor=_actor())
        run_b = await svc_b.create_run(_run_create(name="B payments pass"), actor=_actor())
        assert run_a.id != run_b.id  # per-campus uniqueness

    async def test_repository_denies_unscoped_access(self, db_session: AsyncSession) -> None:
        from app.core.exceptions import AuthorizationError

        repo = ReconciliationRepository(db_session)
        with pytest.raises(AuthorizationError):
            await repo.list_runs()

        platform_repo = ReconciliationRepository(
            db_session, TenantContext(user_id=1, platform=True)
        )
        runs, total = await platform_repo.list_runs()
        assert total == 0
