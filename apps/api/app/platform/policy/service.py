"""Policy-as-code foundation — application service.

Owns the policy lifecycle and evaluation:

- ``create_policy``    — create a draft policy definition (validated scope)
- ``add_version``      — append the next sequential version (validated rules)
- ``publish_version``  — open the effective window, stamp approval metadata,
  end the previous current version (publishing IS the approval action)
- ``retire_version``   — retire a published version
- ``evaluate``         — deterministic evaluation against the *effective*
  version at evaluation time; result is persisted (traceability)
- ``evaluate_version`` — evaluate against an explicit version (what-if)

Every evaluation is persisted to ``policy_evaluations`` so it is traceable
to policy version + input data + result.  Lifecycle operations (create /
publish / retire) are additionally recorded through the existing audit
domain.  All operations are tenant-scoped through the repository.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.audit.actors import ActorType, AuditActor
from app.domains.audit.service import AuditService
from app.multi_tenant.models import TenantContext
from app.platform.policy.models import (
    DECISION_ALLOW,
    DECISION_DENY,
    DECISION_NOT_APPLICABLE,
    DECISION_REVIEW,
    EFFECT_DENY,
    EFFECT_REVIEW,
    EXCEPTION_EFFECT_ALLOW,
    EXCEPTION_EFFECT_REVIEW,
    POLICY_STATUS_ACTIVE,
    POLICY_STATUS_DRAFT,
    VERSION_STATUS_PUBLISHED,
    VERSION_STATUS_RETIRED,
    PolicyDefinition,
    PolicyEvaluation,
    PolicyVersion,
)
from app.platform.policy.registry import PolicyRegistry, policy_registry
from app.platform.policy.repository import PolicyRepository
from app.platform.policy.rules import evaluate_condition
from app.platform.policy.schemas import (
    EvaluateInput,
    EvaluationResult,
    ExceptionOutcome,
    PolicyCreate,
    PolicyVersionCreate,
    PublishVersion,
    RuleOutcome,
)

logger = logging.getLogger(__name__)


class PolicyService:
    """Versioned policy operations (one tenant per instance)."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: Optional[TenantContext] = None,
        registry: Optional[PolicyRegistry] = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.repo = PolicyRepository(session, tenant)
        self.audit = AuditService(session, tenant)
        self.registry = registry or policy_registry

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def create_policy(
        self, data: PolicyCreate, actor: AuditActor | None = None
    ) -> PolicyDefinition:
        """Create a draft policy definition.  ``policy_id`` is a stable
        business key, unique per campus (idempotent re-creation returns the
        existing policy)."""
        if not self.registry.has_scope(data.scope):
            known = sorted(s.key for s in self.registry.scopes())
            raise ValidationError(f"scope must be one of {known}")
        existing = await self.repo.find_by_key(data.policy_id)
        if existing is not None:
            return existing
        policy = PolicyDefinition(
            campus_id=self.repo._effective_campus_id(),
            policy_id=data.policy_id,
            name=data.name,
            description=data.description,
            scope=data.scope,
            scope_ref=data.scope_ref,
            status=POLICY_STATUS_DRAFT,
            created_by=data.created_by or _actor_id(actor),
        )
        policy = await self.repo.create_policy(policy)
        await self.audit.record(
            action="CREATE",
            resource_type="policy",
            resource_id=str(policy.id),
            actor=actor,
            details={
                "policy_id": data.policy_id,
                "name": data.name,
                "scope": data.scope,
            },
        )
        return policy

    async def add_version(
        self,
        policy_def_id: int,
        data: PolicyVersionCreate,
        actor: AuditActor | None = None,
    ) -> PolicyVersion:
        """Append the next sequential version as a draft.

        Rules are validated against the closed operator set and the scope's
        allowed effects before persisting — a malformed rule can never be
        stored, so evaluation can never accidentally allow.
        """
        policy = await self.repo.get_policy_or_404(policy_def_id)
        problems: list[str] = []
        for rule in data.rules:
            problems.extend(
                self.registry.validate_rule(
                    policy.scope,
                    {
                        "id": rule.id,
                        "effect": rule.effect,
                        "condition": rule.condition.model_dump(exclude_none=True),
                    },
                )
            )
        for exc in data.exceptions:
            if exc.effect not in (EXCEPTION_EFFECT_ALLOW, EXCEPTION_EFFECT_REVIEW):
                problems.append(
                    f"exception {exc.id}: effect must be one of "
                    f"{{'allow', 'review'}}, got {exc.effect!r}"
                )
        if problems:
            raise ValidationError("invalid policy version: " + "; ".join(problems))

        version = PolicyVersion(
            campus_id=policy.campus_id,
            policy_def_id=policy.id,
            version=await self.repo.next_version_number(policy.id),
            title=data.title,
            description=data.description,
            rules=[r.model_dump(exclude_none=True) for r in data.rules] or None,
            exceptions=[e.model_dump(exclude_none=True) for e in data.exceptions] or None,
            applicability=(
                data.applicability.model_dump(exclude_none=True) if data.applicability else None
            ),
            status="draft",
            is_current=False,
            effective_from=data.effective_from,
            effective_until=data.effective_until,
            created_by=data.created_by or _actor_id(actor),
        )
        version = await self.repo.create_version(version)
        await self.audit.record(
            action="CREATE",
            resource_type="policy_version",
            resource_id=str(version.id),
            actor=actor,
            details={"policy_id": policy.policy_id, "version": version.version},
        )
        return version

    async def publish_version(
        self,
        version_id: int,
        data: PublishVersion,
        actor: AuditActor | None = None,
    ) -> PolicyVersion:
        """Publish a draft version.

        Publishing is the approval action: it opens the effective window
        (defaults to now), stamps ``approved_by`` / ``approved_at`` /
        ``approval_note``, marks the version current, and closes the
        previous current version's window (``effective_until`` = the new
        ``effective_from``) so the chain stays contiguous and
        deterministic.
        """
        version = await self.repo.get_version_or_404(version_id)
        if version.status != "draft":
            raise ConflictError("only a draft version can be published")

        effective_from = data.effective_from or _now()
        if data.effective_from is not None and version.effective_until is not None:
            if data.effective_from >= version.effective_until:
                raise ValidationError("effective_from must precede effective_until")

        previous = await self.repo.find_current_version(version.policy_def_id)
        if previous is not None and previous.id != version.id:
            previous.is_current = False
            previous.effective_until = effective_from

        version.status = VERSION_STATUS_PUBLISHED
        version.is_current = True
        version.effective_from = effective_from
        version.approved_by = data.approved_by or _actor_id(actor)
        version.approved_at = _now()
        version.approval_note = data.note
        version.published_at = _now()

        policy = await self.repo.get_policy_or_404(version.policy_def_id)
        policy.status = POLICY_STATUS_ACTIVE
        await self.session.flush()

        await self.audit.record(
            action="PUBLISH",
            resource_type="policy_version",
            resource_id=str(version.id),
            actor=actor,
            details={
                "policy_id": policy.policy_id,
                "version": version.version,
                "effective_from": effective_from.isoformat(),
                "note": data.note,
            },
        )
        return version

    async def retire_version(
        self, version_id: int, actor: AuditActor | None = None
    ) -> PolicyVersion:
        """Retire a published version (terminal)."""
        version = await self.repo.get_version_or_404(version_id)
        if version.status != VERSION_STATUS_PUBLISHED:
            raise ConflictError("only a published version can be retired")
        version.status = VERSION_STATUS_RETIRED
        version.is_current = False
        await self.session.flush()

        policy = await self.repo.get_policy_or_404(version.policy_def_id)
        remaining = await self.repo.find_effective_version(policy.id, _now())
        if remaining is None:
            policy.status = POLICY_STATUS_DRAFT

        await self.audit.record(
            action="RETIRE",
            resource_type="policy_version",
            resource_id=str(version.id),
            actor=actor,
            details={"policy_id": policy.policy_id, "version": version.version},
        )
        return version

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    async def evaluate(
        self,
        policy_id: str,
        data: EvaluateInput,
        actor: AuditActor | None = None,
    ) -> EvaluationResult:
        """Evaluate against the *effective* version at evaluation time.

        Raises ``NotFoundError`` when no published version is currently
        effective — the caller can decide how to surface that (there is no
        implicit "always allow" fallback; the engine fails closed).
        """
        policy = await self.repo.find_by_key(policy_id)
        if policy is None:
            raise NotFoundError(f"policy {policy_id!r} not found")
        now = _now()
        version = await self.repo.find_effective_version(policy.id, now)
        if version is None:
            raise NotFoundError(f"policy {policy_id!r} has no published version effective now")
        return await self._evaluate_and_persist(
            policy=policy,
            version=version,
            data=data,
            actor=actor,
        )

    async def evaluate_version(
        self,
        version_id: int,
        data: EvaluateInput,
        actor: AuditActor | None = None,
    ) -> EvaluationResult:
        """Evaluate against an explicit version (what-if / testing).

        The result is persisted like any other evaluation — traceability is
        the point of this engine.
        """
        version = await self.repo.get_version_or_404(version_id)
        policy = await self.repo.get_policy_or_404(version.policy_def_id)
        return await self._evaluate_and_persist(
            policy=policy,
            version=version,
            data=data,
            actor=actor,
        )

    async def _evaluate_and_persist(
        self,
        *,
        policy: PolicyDefinition,
        version: PolicyVersion,
        data: EvaluateInput,
        actor: AuditActor | None,
    ) -> EvaluationResult:
        decision, reason, applicable, rule_results, exception_outcomes = _evaluate(
            version, data.data
        )
        evaluated_at = _now()
        result = {
            "decision": decision,
            "reason": reason,
            "applicable": applicable,
            "rule_results": [r.model_dump() for r in rule_results],
            "exceptions_applied": [e.model_dump() for e in exception_outcomes],
        }
        record = PolicyEvaluation(
            campus_id=policy.campus_id,
            policy_id=policy.policy_id,
            policy_def_id=policy.id,
            policy_version_id=version.id,
            version=version.version,
            subject_type=data.subject_type,
            subject_id=data.subject_id,
            decision=decision,
            reason=reason,
            result=result,
            input_snapshot=data.data or None,
            evaluated_by=data.evaluated_by or _actor_id(actor),
            evaluated_at=evaluated_at,
        )
        await self.repo.create_evaluation(record)
        return EvaluationResult(
            decision=decision,
            reason=reason,
            policy_id=policy.policy_id,
            version=version.version,
            applicable=applicable,
            rule_results=rule_results,
            exceptions_applied=exception_outcomes,
            evaluated_at=evaluated_at,
        )

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def get_policy(self, policy_def_id: int) -> PolicyDefinition:
        return await self.repo.get_policy_or_404(policy_def_id)

    async def list_policies(
        self,
        *,
        scope: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[PolicyDefinition], int]:
        return await self.repo.list_policies(scope=scope, status=status, skip=skip, limit=limit)

    async def list_versions(
        self,
        policy_def_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[PolicyVersion], int]:
        return await self.repo.list_versions(policy_def_id, skip=skip, limit=limit)

    async def history(
        self,
        *,
        policy_id: Optional[str] = None,
        subject_type: Optional[str] = None,
        subject_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[PolicyEvaluation], int]:
        """Evaluation history (the traceability trail)."""
        return await self.repo.list_evaluations(
            policy_id=policy_id,
            subject_type=subject_type,
            subject_id=subject_id,
            skip=skip,
            limit=limit,
        )


# ---------------------------------------------------------------------------
# Pure evaluation core
# ---------------------------------------------------------------------------


def _evaluate(
    version: PolicyVersion,
    data: dict[str, Any],
) -> tuple[
    str,
    str,
    bool,
    list[RuleOutcome],
    list[ExceptionOutcome],
]:
    """Deterministic evaluation of one policy version against input data.

    Returns ``(decision, reason, applicable, rule_results,
    exceptions_applied)``.  Pure: same version + same data → same result.
    """
    applicable = True
    if version.applicability:
        applicable = bool(evaluate_condition(version.applicability, data))
    if not applicable:
        return (
            DECISION_NOT_APPLICABLE,
            "policy does not apply to this subject",
            False,
            [],
            [],
        )

    rules = list(version.rules or [])
    exceptions = list(version.exceptions or [])

    rule_results: list[RuleOutcome] = []
    denied = False
    reviewed = False
    for rule in rules:
        satisfied = bool(evaluate_condition(rule.get("condition") or {}, data))
        effect = rule.get("effect") or "allow"
        rule_results.append(
            RuleOutcome(
                rule_id=rule.get("id") or "<unnamed>",
                satisfied=satisfied,
                effect=effect,
                reason=rule.get("reason"),
            )
        )
        if satisfied and effect == EFFECT_DENY:
            denied = True
        if satisfied and effect == EFFECT_REVIEW:
            reviewed = True

    exception_outcomes: list[ExceptionOutcome] = []
    allow_applied: list[ExceptionOutcome] = []
    review_applied: list[ExceptionOutcome] = []
    for exc in exceptions:
        satisfied = bool(evaluate_condition(exc.get("condition") or {}, data))
        effect = exc.get("effect") or EXCEPTION_EFFECT_ALLOW
        outcome = ExceptionOutcome(
            exception_id=exc.get("id") or "<unnamed>",
            satisfied=satisfied,
            effect=effect,
            reason=exc.get("reason"),
        )
        exception_outcomes.append(outcome)
        if satisfied and effect == EXCEPTION_EFFECT_ALLOW:
            allow_applied.append(outcome)
        if satisfied and effect == EXCEPTION_EFFECT_REVIEW:
            review_applied.append(outcome)

    if denied and allow_applied:
        return (
            DECISION_ALLOW,
            f"denied by rule but waived by exception {allow_applied[0].exception_id}",
            True,
            rule_results,
            exception_outcomes,
        )
    if denied and review_applied:
        return (
            DECISION_REVIEW,
            f"denied by rule, downgraded to review by exception {review_applied[0].exception_id}",
            True,
            rule_results,
            exception_outcomes,
        )
    if denied:
        reasons = [
            r.reason or r.rule_id for r in rule_results if r.satisfied and r.effect == EFFECT_DENY
        ]
        return (
            DECISION_DENY,
            "denied by policy: " + "; ".join(reasons),
            True,
            rule_results,
            exception_outcomes,
        )
    if reviewed:
        reasons = [
            r.reason or r.rule_id for r in rule_results if r.satisfied and r.effect == EFFECT_REVIEW
        ]
        return (
            DECISION_REVIEW,
            "review required by policy: " + "; ".join(reasons),
            True,
            rule_results,
            exception_outcomes,
        )
    return (
        DECISION_ALLOW,
        "no rule matched",
        True,
        rule_results,
        exception_outcomes,
    )


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


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)
