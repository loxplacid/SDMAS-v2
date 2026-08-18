"""Universal reconciliation engine — application service.

Owns the reconciliation lifecycle:

- create runs (idempotent on ``idempotency_key`` per campus)
- save / reuse named rule configs
- execute a pass: deterministic matching + tolerance comparison +
  classification, then write matches + exceptions + summary
- resolve exceptions (accept / reject / correct) with notes
- approve / reject / escalate a run (audit trail)
- attach evidence

Every operation is tenant-scoped through the repository and audited through
the existing audit domain.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.audit.actors import ActorType, AuditActor
from app.domains.audit.service import AuditService
from app.multi_tenant.models import TenantContext
from app.platform.reconciliation.matching import (
    classify,
    match_records,
    unmatched_targets,
)
from app.platform.reconciliation.models import (
    APPROVAL_APPROVE,
    APPROVAL_DECISIONS,
    APPROVAL_REJECT,
    EVIDENCE_TYPES,
    EXCEPTION_SEVERITY_CRITICAL,
    EXCEPTION_SEVERITY_WARNING,
    EXCEPTION_STATUS_CLOSED,
    EXCEPTION_STATUS_OPEN,
    EXCEPTION_STATUS_RESOLVED,
    EXCEPTION_STATUSES,
    MATCH_STATUS_EXCEPTION,
    MATCH_STATUS_MATCHED,
    MATCH_STATUS_SOURCE_ONLY,
    MATCH_STATUS_TARGET_ONLY,
    MATCH_STATUSES,
    RUN_STATUS_APPROVED,
    RUN_STATUS_CLOSED,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_DRAFT,
    RUN_STATUS_EXCEPTIONS_PENDING,
    RUN_STATUS_RUNNING,
    RUN_STATUSES,
    ReconciliationApproval,
    ReconciliationEvidence,
    ReconciliationException,
    ReconciliationMatch,
    ReconciliationRuleConfig,
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

logger = logging.getLogger(__name__)


class ReconciliationService:
    """Universal reconciliation operations (one tenant per instance)."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: Optional[TenantContext] = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.repo = ReconciliationRepository(session, tenant)
        self.audit = AuditService(session, tenant)

    # ------------------------------------------------------------------
    # Runs (idempotent creation)
    # ------------------------------------------------------------------

    async def create_run(
        self, data: ReconciliationRunCreate, actor: AuditActor | None = None
    ) -> ReconciliationRun:
        """Create a reconciliation run; idempotent on ``idempotency_key``
        (per campus) — re-running the same pass returns the existing run."""
        if data.run_type not in ("",) and not data.run_type.strip():
            raise ValidationError("run_type is required")
        if data.idempotency_key:
            existing = await self.repo.find_run_by_idempotency(data.idempotency_key)
            if existing is not None:
                return existing
        run = ReconciliationRun(
            campus_id=self.repo._effective_campus_id(),
            name=data.name,
            run_type=data.run_type,
            source_dataset=data.source_dataset,
            target_dataset=data.target_dataset,
            status=RUN_STATUS_DRAFT,
            match_keys=data.match_keys or None,
            comparison_fields=data.comparison_fields or None,
            idempotency_key=data.idempotency_key,
            rule_config_id=data.rule_config_id,
            created_by=data.created_by or _actor_id(actor),
        )
        run = await self.repo.create_run(run)
        await self.audit.record(
            action="CREATE",
            resource_type="reconciliation_run",
            resource_id=str(run.id),
            actor=actor,
            details={
                "name": data.name,
                "run_type": data.run_type,
                "source_dataset": data.source_dataset,
                "target_dataset": data.target_dataset,
            },
        )
        return run

    # ------------------------------------------------------------------
    # Rule configs
    # ------------------------------------------------------------------

    async def save_rule(
        self, data: RuleConfigCreate, actor: AuditActor | None = None
    ) -> ReconciliationRuleConfig:
        """Save a named, reusable rule; idempotent on ``(campus, name)``."""
        existing = await self.repo.find_rule(data.name)
        if existing is not None:
            return existing
        rule = ReconciliationRuleConfig(
            campus_id=self.repo._effective_campus_id(),
            name=data.name,
            run_type=data.run_type,
            description=data.description,
            match_keys=data.match_keys or None,
            comparison_fields=data.comparison_fields or None,
        )
        rule = await self.repo.create_rule(rule)
        await self.audit.record(
            action="CREATE",
            resource_type="reconciliation_rule_config",
            resource_id=str(rule.id),
            actor=actor,
            details={"name": data.name, "run_type": data.run_type},
        )
        return rule

    async def list_rules(
        self, *, skip: int = 0, limit: int = 100
    ) -> tuple[Sequence[ReconciliationRuleConfig], int]:
        return await self.repo.list_rules(skip=skip, limit=limit)

    async def run_from_rule(
        self, rule_id: int, *, name: str, source_dataset: str, target_dataset: str
    ) -> ReconciliationRun:
        """Create a run from a saved rule config (copy keys + comparisons)."""
        rule = await self.repo.get_rule(rule_id)
        if rule is None:
            raise NotFoundError(f"rule config {rule_id} not found")
        return await self.create_run(
            ReconciliationRunCreate(
                name=name,
                run_type=rule.run_type,
                source_dataset=source_dataset,
                target_dataset=target_dataset,
                match_keys=rule.match_keys or [],
                comparison_fields=rule.comparison_fields or [],
                rule_config_id=rule.id,
            )
        )

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(
        self,
        run_id: int,
        records: ReconcileInput,
        actor: AuditActor | None = None,
    ) -> ReconciliationRun:
        """Run the deterministic pass and persist matches + exceptions.

        The run transitions draft → running → completed (or
        exceptions_pending when any exception was produced).  Re-executing
        a completed run is a no-op (returns the run unchanged) — the run is
        the idempotency boundary, so repeated calls never duplicate
        matches.
        """
        run = await self.repo.get_run_or_404(run_id)
        if run.status in (
            RUN_STATUS_COMPLETED,
            RUN_STATUS_EXCEPTIONS_PENDING,
            RUN_STATUS_APPROVED,
            RUN_STATUS_CLOSED,
        ):
            return run

        match_keys = list(run.match_keys or [])
        comparison_fields = list(run.comparison_fields or [])
        if not match_keys:
            raise ValidationError("run has no match_keys — configure the rule first")

        run.status = RUN_STATUS_RUNNING
        await self.session.flush()

        source_records = records.source_records
        target_records = records.target_records

        matched = match_records(source_records, target_records, match_keys)
        orphan_targets = unmatched_targets(source_records, target_records, match_keys)

        # A zero-tolerance comparison (exact, or absolute with value 0) is
        # the strictest contract — any exception on such a run is critical;
        # otherwise warning.
        strict_fields = any(
            (f.get("tolerance") or "exact") == "exact"
            or (f.get("tolerance") == "absolute" and float(f.get("value", 1)) == 0.0)
            for f in comparison_fields
        )
        exception_severity = (
            EXCEPTION_SEVERITY_CRITICAL if strict_fields else EXCEPTION_SEVERITY_WARNING
        )

        counts = {
            MATCH_STATUS_MATCHED: 0,
            MATCH_STATUS_SOURCE_ONLY: 0,
            MATCH_STATUS_TARGET_ONLY: 0,
            MATCH_STATUS_EXCEPTION: 0,
        }
        # De-duplicate source_refs (idempotency within the run): if a source
        # record already has a match row, reuse it instead of inserting.
        existing_by_ref: dict[str, ReconciliationMatch] = {}
        for m in (await self.repo.list_matches(run_id, limit=100000))[0]:
            existing_by_ref[m.source_ref] = m

        for i, result in enumerate(matched):
            source = result["source"]
            target = result["target"]
            source_ref = _ref_of(source, match_keys, i)
            status, code, reason = classify(result, comparison_fields)

            existing = existing_by_ref.get(source_ref)
            if existing is not None:
                # Preserve an already-resolved exception on re-run.
                counts[existing.status] = counts.get(existing.status, 0) + 1
                continue

            match = ReconciliationMatch(
                campus_id=run.campus_id,
                run_id=run.id,
                source_ref=source_ref,
                source_payload=source,
                target_ref=_ref_of(target, match_keys, i) if target else None,
                target_payload=target if target else None,
                status=status,
                within_tolerance=status != MATCH_STATUS_EXCEPTION,
                exception_code=code,
                exception_reason=reason,
            )
            match = await self.repo.create_match(match)
            counts[status] = counts.get(status, 0) + 1

            if status == MATCH_STATUS_EXCEPTION:
                await self.repo.create_exception(
                    ReconciliationException(
                        campus_id=run.campus_id,
                        run_id=run.id,
                        match_id=match.id,
                        code=code or "EXCEPTION",
                        severity=exception_severity,
                        reason=reason,
                        status=EXCEPTION_STATUS_OPEN,
                    )
                )

        # Unmatched targets → target_only rows (informational; not a match
        # row per source, so recorded as their own rows).  The synthetic
        # source_ref carries the index so duplicate target keys (two targets
        # with the same key, both unmatched) cannot collide on the unique
        # (run_id, source_ref) constraint.
        for i, target in enumerate(orphan_targets):
            target_ref = _ref_of(target, match_keys, i)
            synthetic = f"__target_only__:{i}:{target_ref}"
            await self.repo.create_match(
                ReconciliationMatch(
                    campus_id=run.campus_id,
                    run_id=run.id,
                    source_ref=synthetic,
                    source_payload=None,
                    target_ref=target_ref,
                    target_payload=target,
                    status=MATCH_STATUS_TARGET_ONLY,
                    within_tolerance=False,
                    exception_code="UNMATCHED_TARGET",
                    exception_reason="no source record with this key",
                )
            )
            counts[MATCH_STATUS_TARGET_ONLY] = counts.get(MATCH_STATUS_TARGET_ONLY, 0) + 1

        has_exceptions = counts.get(MATCH_STATUS_EXCEPTION, 0) > 0 or (
            counts.get(MATCH_STATUS_TARGET_ONLY, 0) > 0
        )
        run.status = RUN_STATUS_EXCEPTIONS_PENDING if has_exceptions else RUN_STATUS_COMPLETED
        run.completed_at = _now()
        run.summary = {
            "source_records": len(source_records),
            "target_records": len(target_records),
            "matched": counts.get(MATCH_STATUS_MATCHED, 0),
            "source_only": counts.get(MATCH_STATUS_SOURCE_ONLY, 0),
            "target_only": counts.get(MATCH_STATUS_TARGET_ONLY, 0),
            "exceptions": counts.get(MATCH_STATUS_EXCEPTION, 0),
            "status": run.status,
        }
        await self.session.flush()
        await self.audit.record(
            action="RECONCILE",
            resource_type="reconciliation_run",
            resource_id=str(run.id),
            actor=actor,
            after_state=run.summary,
        )
        return run

    # ------------------------------------------------------------------
    # Exceptions (manual review)
    # ------------------------------------------------------------------

    async def list_exceptions(
        self,
        run_id: int,
        *,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[ReconciliationException], int]:
        if status and status not in EXCEPTION_STATUSES:
            raise ValidationError(f"status must be one of {sorted(EXCEPTION_STATUSES)}")
        return await self.repo.list_exceptions(run_id, status=status, skip=skip, limit=limit)

    async def resolve_exception(
        self,
        exception_id: int,
        data: ExceptionResolve,
        actor: AuditActor | None = None,
    ) -> ReconciliationException:
        """Resolve an exception (manual review): accept / reject / correct."""
        exception = await self.repo.get_exception_or_404(exception_id)
        if exception.status in (EXCEPTION_STATUS_RESOLVED, EXCEPTION_STATUS_CLOSED):
            raise ConflictError("Exception already resolved")
        exception.status = EXCEPTION_STATUS_RESOLVED
        exception.resolution = {
            "decision": data.decision,
            "note": data.note,
            "corrected_value": data.corrected_value,
        }
        exception.resolved_by = data.resolved_by or _actor_id(actor)
        exception.resolved_at = _now()
        await self.session.flush()
        await self.audit.record(
            action="RESOLVE",
            resource_type="reconciliation_exception",
            resource_id=str(exception.id),
            actor=actor,
            details={"decision": data.decision, "note": data.note},
        )
        return exception

    async def close_exception(
        self,
        exception_id: int,
        actor: AuditActor | None = None,
    ) -> ReconciliationException:
        """Close a resolved exception (terminal state)."""
        exception = await self.repo.get_exception_or_404(exception_id)
        exception.status = EXCEPTION_STATUS_CLOSED
        await self.session.flush()
        await self.audit.record(
            action="CLOSE",
            resource_type="reconciliation_exception",
            resource_id=str(exception.id),
            actor=actor,
        )
        return exception

    # ------------------------------------------------------------------
    # Approvals
    # ------------------------------------------------------------------

    async def approve(
        self,
        run_id: int,
        data: ApprovalCreate,
        actor: AuditActor | None = None,
    ) -> ReconciliationRun:
        """Approve / reject / escalate a run.

        Approving requires all exceptions resolved (or none open); rejecting
        returns the run to draft for a fresh pass.
        """
        if data.decision not in APPROVAL_DECISIONS:
            raise ValidationError(f"decision must be one of {sorted(APPROVAL_DECISIONS)}")
        run = await self.repo.get_run_or_404(run_id)

        if data.decision == APPROVAL_APPROVE:
            open_count = await self.repo.open_exception_count(run.id)
            if open_count > 0:
                raise ConflictError(f"Cannot approve: {open_count} exception(s) still open")
            run.status = RUN_STATUS_APPROVED
            run.approved_by = data.approver_id or _actor_id(actor)
            run.approved_at = _now()
        elif data.decision == APPROVAL_REJECT:
            run.status = RUN_STATUS_DRAFT
        # escalate leaves status unchanged (approval trail records it)

        approval = ReconciliationApproval(
            campus_id=run.campus_id,
            run_id=run.id,
            decision=data.decision,
            approver_id=data.approver_id or _actor_id(actor),
            comment=data.comment,
        )
        await self.repo.create_approval(approval)
        await self.session.flush()
        await self.audit.record(
            action="APPROVAL",
            resource_type="reconciliation_run",
            resource_id=str(run.id),
            actor=actor,
            details={"decision": data.decision, "comment": data.comment},
        )
        return run

    async def close_run(self, run_id: int, actor: AuditActor | None = None) -> ReconciliationRun:
        """Close an approved run (terminal)."""
        run = await self.repo.get_run_or_404(run_id)
        if run.status != RUN_STATUS_APPROVED:
            raise ConflictError("Only an approved run can be closed")
        run.status = RUN_STATUS_CLOSED
        await self.session.flush()
        await self.audit.record(
            action="CLOSE",
            resource_type="reconciliation_run",
            resource_id=str(run.id),
            actor=actor,
        )
        return run

    # ------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------

    async def attach_evidence(
        self,
        run_id: int,
        data: EvidenceCreate,
        actor: AuditActor | None = None,
    ) -> ReconciliationEvidence:
        if data.kind not in EVIDENCE_TYPES:
            raise ValidationError(f"kind must be one of {sorted(EVIDENCE_TYPES)}")
        run = await self.repo.get_run_or_404(run_id)
        evidence = ReconciliationEvidence(
            campus_id=run.campus_id,
            run_id=run.id,
            match_id=data.match_id,
            kind=data.kind,
            reference=data.reference,
            checksum=data.checksum,
            note=data.note,
        )
        evidence = await self.repo.create_evidence(evidence)
        await self.audit.record(
            action="ATTACH",
            resource_type="reconciliation_evidence",
            resource_id=str(evidence.id),
            actor=actor,
            details={"run_id": run.id, "kind": data.kind, "reference": data.reference},
        )
        return evidence

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def get_run(self, run_id: int) -> ReconciliationRun:
        return await self.repo.get_run_or_404(run_id)

    async def list_runs(
        self,
        *,
        run_type: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[ReconciliationRun], int]:
        if status and status not in RUN_STATUSES:
            raise ValidationError(f"status must be one of {sorted(RUN_STATUSES)}")
        return await self.repo.list_runs(run_type=run_type, status=status, skip=skip, limit=limit)

    async def list_matches(
        self,
        run_id: int,
        *,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[ReconciliationMatch], int]:
        if status and status not in MATCH_STATUSES:
            raise ValidationError(f"status must be one of {sorted(MATCH_STATUSES)}")
        return await self.repo.list_matches(run_id, status=status, skip=skip, limit=limit)

    async def approvals(self, run_id: int) -> Sequence[ReconciliationApproval]:
        return await self.repo.list_approvals(run_id)

    async def evidence(self, run_id: int) -> Sequence[ReconciliationEvidence]:
        return await self.repo.list_evidence(run_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _actor_id(actor: AuditActor | None) -> Optional[int]:
    if actor is None or actor.actor_type != ActorType.USER:
        return None
    raw = actor.actor_id
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _now():
    import datetime

    return datetime.datetime.now(datetime.timezone.utc)


def _ref_of(record: Optional[dict[str, Any]], match_keys: list[dict[str, Any]], index: int) -> str:
    """Stable reference for a record: the first match-key field value if
    present and scalar, else ``__row_{index}``."""
    if record is None:
        return f"__row_{index}"
    for spec in match_keys:
        field = spec.get("field") or spec.get("source_field") or spec.get("target_field") or ""
        value = record.get(field)
        if value is not None and not isinstance(value, (dict, list)):
            return str(value)
    return f"__row_{index}"
