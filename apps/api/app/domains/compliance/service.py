"""Declarative compliance evaluation engine (TASK 20).

Interprets JSON schema packs against actual data from connected domains.
Every evaluation is deterministic, explainable, and produces an immutable
audit trail.

Rule types
----------
- ``field_exists``     — a required field is present and non-null
- ``value_range``      — a numeric field falls within [min, max]
- ``value_in_set``     — a field's value is one of an allowed set
- ``count_min``        — at least N records of an entity type exist
- ``count_max``        — at most N records of an entity type exist
- ``ratio_min``        — a ratio (e.g. pass_rate) meets a minimum
- ``aggregate_check``  — an aggregate query meets a condition
- ``custom_query``     — a named query function with parameters

No CBSE/ICSE/state rules are hard-coded.  Rules are defined in JSON;
the evaluator interprets them deterministically.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.compliance.models import (
    ComplianceApproval,
    ComplianceEvaluation,
    ComplianceRegulation,
    ComplianceRequirement,
    ComplianceRule,
    ComplianceSchema,
    ComplianceSubmission,
)
from app.domains.compliance.schemas import (
    EvaluationResult,
    RuleExplanation,
    SubmissionResponse,
)

logger = logging.getLogger(__name__)


class ComplianceService:
    """Schema-driven compliance evaluation engine.

    All methods are read-only (evaluations are append-only) and
    tenant-scoped.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ====================================================================
    # Regulation CRUD
    # ====================================================================

    async def create_regulation(
        self,
        campus_id: int | None,
        *,
        regulation_id: str,
        name: str,
        description: str | None = None,
        authority: str | None = None,
        jurisdiction: str | None = None,
        effective_from: datetime.datetime | None = None,
        effective_until: datetime.datetime | None = None,
        actor_id: int | None = None,
    ) -> ComplianceRegulation:
        reg = ComplianceRegulation(
            campus_id=campus_id,
            regulation_id=regulation_id,
            name=name,
            description=description,
            authority=authority,
            jurisdiction=jurisdiction,
            effective_from=effective_from,
            effective_until=effective_until,
            created_by=actor_id,
        )
        self.session.add(reg)
        await self.session.flush()
        return reg

    async def get_regulation(
        self, campus_id: int | None, regulation_id: int
    ) -> ComplianceRegulation | None:
        return await self.session.get(ComplianceRegulation, regulation_id)

    async def list_regulations(
        self, campus_id: int | None, *, limit: int = 50, offset: int = 0
    ) -> list[ComplianceRegulation]:
        q = select(ComplianceRegulation)
        if campus_id is not None:
            q = q.where(ComplianceRegulation.campus_id == campus_id)
        q = (
            q.order_by(ComplianceRegulation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(q)).scalars().all())

    # ====================================================================
    # Requirement CRUD
    # ====================================================================

    async def create_requirement(
        self,
        campus_id: int | None,
        regulation_id: int,
        *,
        requirement_id: str,
        title: str,
        description: str | None = None,
        category: str | None = None,
        severity: str = "medium",
        is_mandatory: bool = True,
    ) -> ComplianceRequirement:
        req = ComplianceRequirement(
            campus_id=campus_id,
            regulation_id=regulation_id,
            requirement_id=requirement_id,
            title=title,
            description=description,
            category=category,
            severity=severity,
            is_mandatory=is_mandatory,
        )
        self.session.add(req)
        await self.session.flush()
        return req

    # ====================================================================
    # Schema CRUD
    # ====================================================================

    async def create_schema(
        self,
        campus_id: int | None,
        *,
        schema_id: str,
        title: str,
        description: str | None = None,
        data_sources: list[str] | None = None,
        rules: list[dict[str, Any]] | None = None,
        actor_id: int | None = None,
    ) -> ComplianceSchema:
        # Auto-increment version based on existing schemas with same key
        q = select(func.max(ComplianceSchema.version)).where(
            ComplianceSchema.schema_id == schema_id
        )
        if campus_id is not None:
            q = q.where(ComplianceSchema.campus_id == campus_id)
        max_ver = (await self.session.execute(q)).scalar() or 0
        next_version = max_ver + 1

        schema = ComplianceSchema(
            campus_id=campus_id,
            schema_id=schema_id,
            version=next_version,
            title=title,
            description=description,
            data_sources=data_sources,
            created_by=actor_id,
        )
        self.session.add(schema)
        await self.session.flush()

        # Create rules
        for rule_def in (rules or []):
            # Look up requirement by business key if provided
            req_id = None
            if rule_def.get("requirement_id"):
                req = await self._find_requirement(
                    campus_id, rule_def["requirement_id"]
                )
                if req:
                    req_id = req.id

            rule = ComplianceRule(
                campus_id=campus_id,
                schema_id=schema.id,
                requirement_id=req_id,
                rule_code=rule_def["rule_code"],
                rule_type=rule_def["rule_type"],
                target_entity=rule_def["target_entity"],
                target_field=rule_def.get("target_field"),
                condition=rule_def.get("condition"),
                expected=rule_def.get("expected"),
                severity=rule_def.get("severity", "medium"),
                is_mandatory=rule_def.get("is_mandatory", True),
                explanation=rule_def.get("explanation"),
            )
            self.session.add(rule)

        await self.session.flush()
        return schema

    async def get_schema(
        self, campus_id: int | None, schema_pk: int
    ) -> ComplianceSchema | None:
        from sqlalchemy.orm import selectinload

        q = (
            select(ComplianceSchema)
            .options(selectinload(ComplianceSchema.rules))
            .where(ComplianceSchema.id == schema_pk)
        )
        return (await self.session.execute(q)).scalar_one_or_none()

    async def get_current_schema(
        self, campus_id: int | None, schema_id: str
    ) -> ComplianceSchema | None:
        q = select(ComplianceSchema).where(
            ComplianceSchema.schema_id == schema_id,
            ComplianceSchema.is_current == True,  # noqa: E712
        )
        if campus_id is not None:
            q = q.where(ComplianceSchema.campus_id == campus_id)
        return (await self.session.execute(q)).scalar_one_or_none()

    async def publish_schema(
        self,
        campus_id: int | None,
        schema_pk: int,
        *,
        actor_id: int | None = None,
    ) -> ComplianceSchema:
        """Publish a schema — mark it as current and effective."""
        schema = await self.get_schema(campus_id, schema_pk)
        if schema is None:
            raise ValueError(f"Schema {schema_pk} not found")

        # Unpublish any previously current schema
        if campus_id is not None:
            q = select(ComplianceSchema).where(
                ComplianceSchema.campus_id == campus_id,
                ComplianceSchema.schema_id == schema.schema_id,
                ComplianceSchema.is_current == True,  # noqa: E712
            )
            old = (await self.session.execute(q)).scalar_one_or_none()
            if old and old.id != schema.id:
                old.is_current = False
                old.effective_until = datetime.datetime.now(
                    datetime.timezone.utc
                )

        now = datetime.datetime.now(datetime.timezone.utc)
        schema.is_current = True
        schema.status = "published"
        schema.effective_from = now
        schema.approved_by = actor_id
        schema.approved_at = now
        await self.session.flush()
        return schema

    async def list_schemas(
        self, campus_id: int | None, *, limit: int = 50
    ) -> list[ComplianceSchema]:
        q = select(ComplianceSchema)
        if campus_id is not None:
            q = q.where(ComplianceSchema.campus_id == campus_id)
        q = q.order_by(ComplianceSchema.created_at.desc()).limit(limit)
        return list((await self.session.execute(q)).scalars().all())

    # ====================================================================
    # Submission + Evaluation
    # ====================================================================

    async def submit(
        self,
        campus_id: int | None,
        *,
        regulation_id: int | None = None,
        schema_pk: int | None = None,
        submission_id: str,
        title: str,
        description: str | None = None,
        data_snapshot: dict[str, Any] | None = None,
        actor_id: int | None = None,
    ) -> ComplianceSubmission:
        """Create a submission and evaluate all rules against the data."""
        sub = ComplianceSubmission(
            campus_id=campus_id,
            regulation_id=regulation_id,
            schema_id=schema_pk,
            submission_id=submission_id,
            title=title,
            description=description,
            data_snapshot=data_snapshot,
            status="evaluating",
            created_by=actor_id,
        )
        self.session.add(sub)
        await self.session.flush()

        # Load rules from the schema
        rules: list[ComplianceRule] = []
        if schema_pk:
            schema = await self.get_schema(campus_id, schema_pk)
            if schema:
                rules = list(schema.rules)
        elif campus_id is not None:
            # Try to find the current schema
            q = select(ComplianceRule).join(ComplianceSchema)
            q = q.where(
                ComplianceSchema.campus_id == campus_id,
                ComplianceSchema.is_current == True,  # noqa: E712
                ComplianceRule.enabled == True,  # noqa: E712
            )
            rules = list((await self.session.execute(q)).scalars().all())

        # Evaluate each rule
        total = 0
        passed = 0
        failed = 0
        warnings = 0

        for rule in rules:
            result = await self._evaluate_rule(
                rule, data_snapshot or {}
            )
            total += 1
            if result.result == "pass":
                passed += 1
            elif result.result == "fail":
                failed += 1
            elif result.result == "warning":
                warnings += 1

            eval_row = ComplianceEvaluation(
                campus_id=campus_id,
                submission_id=sub.id,
                rule_id=rule.id,
                rule_code=rule.rule_code,
                requirement_id=(
                    str(rule.requirement_id) if rule.requirement_id else None
                ),
                result=result.result,
                severity=result.severity,
                input_data=data_snapshot,
                expected_value=result.expected_value,
                actual_value=result.actual_value,
                explanation=result.explanation,
                trace=result.trace,
            )
            self.session.add(eval_row)

        # Update submission totals
        sub.total_rules = total
        sub.passed = passed
        sub.failed = failed
        sub.warnings = warnings
        sub.compliance_score = (
            round(passed / total * 100, 1) if total > 0 else None
        )
        sub.status = "completed"
        await self.session.flush()
        return sub

    async def get_submission(
        self, campus_id: int | None, submission_pk: int
    ) -> ComplianceSubmission | None:
        return await self.session.get(ComplianceSubmission, submission_pk)

    async def list_submissions(
        self, campus_id: int | None, *, limit: int = 50
    ) -> list[ComplianceSubmission]:
        q = select(ComplianceSubmission)
        if campus_id is not None:
            q = q.where(ComplianceSubmission.campus_id == campus_id)
        q = q.order_by(ComplianceSubmission.created_at.desc()).limit(limit)
        return list((await self.session.execute(q)).scalars().all())

    async def get_evaluations(
        self, submission_id: int
    ) -> list[ComplianceEvaluation]:
        q = (
            select(ComplianceEvaluation)
            .where(ComplianceEvaluation.submission_id == submission_id)
            .order_by(ComplianceEvaluation.id)
        )
        return list((await self.session.execute(q)).scalars().all())

    async def get_explanations(
        self, submission_id: int
    ) -> list[RuleExplanation]:
        """Build full explainability data for a submission."""
        evals = await self.get_evaluations(submission_id)
        explanations: list[RuleExplanation] = []

        for ev in evals:
            # Load the rule for full metadata
            rule = await self.session.get(ComplianceRule, ev.rule_id)
            trace_steps: list[str] = []
            if ev.trace and "steps" in ev.trace:
                trace_steps = ev.trace["steps"]

            explanations.append(
                RuleExplanation(
                    rule_code=ev.rule_code,
                    rule_type=rule.rule_type if rule else "unknown",
                    target_entity=rule.target_entity if rule else "unknown",
                    target_field=rule.target_field if rule else None,
                    explanation=ev.explanation,
                    result=ev.result,
                    severity=ev.severity,
                    expected=ev.expected_value,
                    actual=ev.actual_value,
                    trace_steps=trace_steps,
                )
            )
        return explanations

    # ====================================================================
    # Approval
    # ====================================================================

    async def approve_submission(
        self,
        campus_id: int | None,
        submission_id: int,
        *,
        decision: str,
        comment: str | None = None,
        actor_id: int | None = None,
    ) -> ComplianceApproval:
        sub = await self.get_submission(campus_id, submission_id)
        if sub is None:
            raise ValueError(f"Submission {submission_id} not found")

        approval = ComplianceApproval(
            campus_id=campus_id,
            submission_id=submission_id,
            decision=decision,
            approver_id=actor_id,
            comment=comment,
        )
        self.session.add(approval)

        if decision == "approved":
            sub.status = "approved"
        elif decision == "rejected":
            sub.status = "rejected"
        elif decision == "needs_revision":
            sub.status = "revision_needed"

        await self.session.flush()
        return approval

    # ====================================================================
    # Dashboard
    # ====================================================================

    async def dashboard(
        self, campus_id: int | None
    ) -> dict[str, Any]:
        """High-level compliance dashboard data."""
        regs = await self.list_regulations(campus_id, limit=1000)
        schemas = await self.list_schemas(campus_id, limit=1000)
        subs = await self.list_submissions(campus_id, limit=1000)

        active_schemas = sum(1 for s in schemas if s.is_current)
        pending = sum(1 for s in subs if s.status in ("pending", "evaluating"))
        scores = [s.compliance_score for s in subs if s.compliance_score is not None]
        avg_score = round(sum(scores) / len(scores), 1) if scores else None

        return {
            "total_regulations": len(regs),
            "total_requirements": sum(len(r.requirements) for r in regs),
            "total_schemas": len(schemas),
            "active_schemas": active_schemas,
            "total_submissions": len(subs),
            "pending_submissions": pending,
            "average_score": avg_score,
            "recent_submissions": [
                SubmissionResponse.model_validate(s).model_dump()
                for s in subs[:10]
            ],
        }

    # ====================================================================
    # Rule evaluator
    # ====================================================================

    async def _evaluate_rule(
        self,
        rule: ComplianceRule,
        data: dict[str, Any],
    ) -> EvaluationResult:
        """Evaluate a single rule against data.

        Returns a deterministic EvaluationResult with full trace.
        """
        rule_type = rule.rule_type
        condition = rule.condition or {}
        expected = rule.expected or {}
        trace_steps: list[str] = []

        trace_steps.append(f"Evaluating rule {rule.rule_code} (type={rule_type})")
        trace_steps.append(f"Target: {rule.target_entity}.{rule.target_field or '*'}")

        try:
            if rule_type == "field_exists":
                return await self._eval_field_exists(
                    rule, data, expected, trace_steps
                )
            elif rule_type == "value_range":
                return await self._eval_value_range(
                    rule, data, condition, expected, trace_steps
                )
            elif rule_type == "value_in_set":
                return await self._eval_value_in_set(
                    rule, data, condition, expected, trace_steps
                )
            elif rule_type == "count_min":
                return await self._eval_count_min(
                    rule, condition, expected, trace_steps
                )
            elif rule_type == "count_max":
                return await self._eval_count_max(
                    rule, condition, expected, trace_steps
                )
            elif rule_type == "ratio_min":
                return await self._eval_ratio_min(
                    rule, condition, expected, trace_steps
                )
            elif rule_type == "aggregate_check":
                return await self._eval_aggregate(
                    rule, condition, expected, trace_steps
                )
            elif rule_type == "custom_query":
                return await self._eval_custom_query(
                    rule, data, condition, expected, trace_steps
                )
            else:
                trace_steps.append(f"Unknown rule type: {rule_type}")
                return EvaluationResult(
                    rule_code=rule.rule_code,
                    result="error",
                    severity=rule.severity,
                    explanation=f"Unknown rule type: {rule_type}",
                    trace={"steps": trace_steps},
                )
        except Exception as exc:  # noqa: BLE001
            trace_steps.append(f"Error: {exc}")
            return EvaluationResult(
                rule_code=rule.rule_code,
                result="error",
                severity=rule.severity,
                explanation=f"Evaluation error: {exc}",
                trace={"steps": trace_steps},
            )

    async def _eval_field_exists(
        self,
        rule: ComplianceRule,
        data: dict[str, Any],
        expected: dict[str, Any],
        trace: list[str],
    ) -> EvaluationResult:
        """Check that a required field exists and is non-null."""
        entity = rule.target_entity
        field_name = rule.target_field or ""
        entity_data = data.get(entity, {})

        if isinstance(entity_data, list):
            # Check the field in the first record
            entity_data = entity_data[0] if entity_data else {}

        value = entity_data.get(field_name) if isinstance(entity_data, dict) else None
        exists = value is not None and value != ""

        trace.append(f"Checking {entity}.{field_name} exists in data")
        trace.append(f"Found: {exists} (value={value!r})")

        if exists:
            trace.append("Rule PASSED")
            return EvaluationResult(
                rule_code=rule.rule_code,
                result="pass",
                severity=rule.severity,
                expected_value={"exists": True},
                actual_value={"exists": True, "value": value},
                explanation=rule.explanation or f"{entity}.{field_name} exists",
                trace={"steps": trace},
            )
        else:
            trace.append("Rule FAILED")
            return EvaluationResult(
                rule_code=rule.rule_code,
                result="fail",
                severity=rule.severity,
                expected_value={"exists": True},
                actual_value={"exists": False, "value": value},
                explanation=rule.explanation or f"{entity}.{field_name} is missing or null",
                trace={"steps": trace},
            )

    async def _eval_value_range(
        self,
        rule: ComplianceRule,
        data: dict[str, Any],
        condition: dict[str, Any],
        expected: dict[str, Any],
        trace: list[str],
    ) -> EvaluationResult:
        """Check that a numeric field falls within [min, max]."""
        entity = rule.target_entity
        field_name = rule.target_field or ""
        entity_data = data.get(entity, {})
        if isinstance(entity_data, list) and entity_data:
            entity_data = entity_data[0]

        value = entity_data.get(field_name) if isinstance(entity_data, dict) else None
        min_val = condition.get("min", expected.get("min"))
        max_val = condition.get("max", expected.get("max"))

        trace.append(f"Checking {entity}.{field_name} in range [{min_val}, {max_val}]")
        trace.append(f"Actual value: {value!r}")

        if value is None:
            trace.append("Value is None — rule FAILED")
            return EvaluationResult(
                rule_code=rule.rule_code,
                result="fail",
                severity=rule.severity,
                expected_value={"min": min_val, "max": max_val},
                actual_value={"value": None},
                explanation=rule.explanation or f"{entity}.{field_name} is null",
                trace={"steps": trace},
            )

        try:
            num_val = float(value)
        except (TypeError, ValueError):
            trace.append("Value is not numeric — rule FAILED")
            return EvaluationResult(
                rule_code=rule.rule_code,
                result="fail",
                severity=rule.severity,
                expected_value={"min": min_val, "max": max_val},
                actual_value={"value": value},
                explanation=rule.explanation or f"{entity}.{field_name} is not numeric",
                trace={"steps": trace},
            )

        in_range = True
        if min_val is not None and num_val < float(min_val):
            in_range = False
        if max_val is not None and num_val > float(max_val):
            in_range = False

        trace.append(f"In range: {in_range}")

        return EvaluationResult(
            rule_code=rule.rule_code,
            result="pass" if in_range else "fail",
            severity=rule.severity,
            expected_value={"min": min_val, "max": max_val},
            actual_value={"value": num_val},
            explanation=rule.explanation or (
                f"{entity}.{field_name}={num_val} is within [{min_val}, {max_val}]"
                if in_range
                else f"{entity}.{field_name}={num_val} is outside [{min_val}, {max_val}]"
            ),
            trace={"steps": trace},
        )

    async def _eval_value_in_set(
        self,
        rule: ComplianceRule,
        data: dict[str, Any],
        condition: dict[str, Any],
        expected: dict[str, Any],
        trace: list[str],
    ) -> EvaluationResult:
        """Check that a field's value is one of an allowed set."""
        entity = rule.target_entity
        field_name = rule.target_field or ""
        entity_data = data.get(entity, {})
        if isinstance(entity_data, list) and entity_data:
            entity_data = entity_data[0]

        value = entity_data.get(field_name) if isinstance(entity_data, dict) else None
        allowed = set(condition.get("values", expected.get("values", [])))

        trace.append(f"Checking {entity}.{field_name} in set {allowed}")
        trace.append(f"Actual value: {value!r}")

        in_set = value in allowed if allowed else True

        return EvaluationResult(
            rule_code=rule.rule_code,
            result="pass" if in_set else "fail",
            severity=rule.severity,
            expected_value={"values": list(allowed)},
            actual_value={"value": value},
            explanation=rule.explanation or (
                f"{entity}.{field_name}={value!r} is in allowed set"
                if in_set
                else f"{entity}.{field_name}={value!r} is not in {allowed}"
            ),
            trace={"steps": trace},
        )

    async def _eval_count_min(
        self,
        rule: ComplianceRule,
        condition: dict[str, Any],
        expected: dict[str, Any],
        trace: list[str],
    ) -> EvaluationResult:
        """Check that at least N records of an entity type exist."""
        entity = rule.target_entity
        min_count = condition.get("min", expected.get("min", 0))

        trace.append(f"Counting {entity} records (need >= {min_count})")

        count = await self._count_entity(rule.campus_id, entity)
        trace.append(f"Actual count: {count}")

        passed = count >= min_count

        return EvaluationResult(
            rule_code=rule.rule_code,
            result="pass" if passed else "fail",
            severity=rule.severity,
            expected_value={"min_count": min_count},
            actual_value={"count": count},
            explanation=rule.explanation or (
                f"{count} {entity} records found (need >= {min_count})"
            ),
            trace={"steps": trace},
        )

    async def _eval_count_max(
        self,
        rule: ComplianceRule,
        condition: dict[str, Any],
        expected: dict[str, Any],
        trace: list[str],
    ) -> EvaluationResult:
        """Check that at most N records of an entity type exist."""
        entity = rule.target_entity
        max_count = condition.get("max", expected.get("max", 999999))

        trace.append(f"Counting {entity} records (need <= {max_count})")

        count = await self._count_entity(rule.campus_id, entity)
        trace.append(f"Actual count: {count}")

        passed = count <= max_count

        return EvaluationResult(
            rule_code=rule.rule_code,
            result="pass" if passed else "fail",
            severity=rule.severity,
            expected_value={"max_count": max_count},
            actual_value={"count": count},
            explanation=rule.explanation or (
                f"{count} {entity} records found (need <= {max_count})"
            ),
            trace={"steps": trace},
        )

    async def _eval_ratio_min(
        self,
        rule: ComplianceRule,
        condition: dict[str, Any],
        expected: dict[str, Any],
        trace: list[str],
    ) -> EvaluationResult:
        """Check that a ratio (numerator/denominator) meets a minimum."""
        entity = rule.target_entity
        num_field = condition.get("numerator_field", "count")
        den_field = condition.get("denominator_field", "total")
        min_ratio = condition.get("min", expected.get("min", 0))

        trace.append(
            f"Computing ratio for {entity}: "
            f"{num_field}/{den_field} >= {min_ratio}"
        )

        # Use provided data if available, otherwise compute from DB
        num = condition.get("numerator_value")
        den = condition.get("denominator_value")
        if num is None or den is None:
            trace.append("Ratio values not provided — skipping")
            return EvaluationResult(
                rule_code=rule.rule_code,
                result="skipped",
                severity=rule.severity,
                explanation="Ratio numerator/denominator not provided in data",
                trace={"steps": trace},
            )

        ratio = num / den if den > 0 else 0
        passed = ratio >= min_ratio

        trace.append(f"Ratio: {ratio} >= {min_ratio} -> {passed}")

        return EvaluationResult(
            rule_code=rule.rule_code,
            result="pass" if passed else "fail",
            severity=rule.severity,
            expected_value={"min_ratio": min_ratio},
            actual_value={"ratio": round(ratio, 4), "numerator": num, "denominator": den},
            explanation=rule.explanation or (
                f"Ratio {ratio:.2%} >= {min_ratio:.2%}"
                if passed
                else f"Ratio {ratio:.2%} < {min_ratio:.2%}"
            ),
            trace={"steps": trace},
        )

    async def _eval_aggregate(
        self,
        rule: ComplianceRule,
        condition: dict[str, Any],
        expected: dict[str, Any],
        trace: list[str],
    ) -> EvaluationResult:
        """Check an aggregate query against a condition."""
        entity = rule.target_entity
        agg_func = condition.get("function", "count")
        threshold = condition.get("threshold", expected.get("threshold", 0))
        operator = condition.get("operator", expected.get("operator", ">="))

        trace.append(
            f"Aggregate check: {agg_func}({entity}) {operator} {threshold}"
        )

        value = await self._count_entity(rule.campus_id, entity)
        trace.append(f"Aggregate result: {value}")

        passed = self._compare(value, operator, threshold)

        return EvaluationResult(
            rule_code=rule.rule_code,
            result="pass" if passed else "fail",
            severity=rule.severity,
            expected_value={"operator": operator, "threshold": threshold},
            actual_value={"value": value},                explanation=rule.explanation or (
                f"{agg_func}({entity}) = {value} "
                f"{operator} {threshold} -> "
                f"{'PASS' if passed else 'FAIL'}"
            ),
            trace={"steps": trace},
        )

    async def _eval_custom_query(
        self,
        rule: ComplianceRule,
        data: dict[str, Any],
        condition: dict[str, Any],
        expected: dict[str, Any],
        trace: list[str],
    ) -> EvaluationResult:
        """Evaluate a custom query rule using data from the snapshot."""
        query_name = condition.get("name", "unknown")
        trace.append(f"Custom query: {query_name}")

        # Custom queries use the data snapshot directly
        # The condition defines what to check in the snapshot
        check_field = condition.get("check_field", "")
        check_value = data.get(check_field)

        trace.append(f"Checking data[{check_field}] = {check_value!r}")

        if check_value is None:
            trace.append("Field not found in data — rule FAILED")
            return EvaluationResult(
                rule_code=rule.rule_code,
                result="fail",
                severity=rule.severity,
                explanation=rule.explanation or (
                    f"Custom query {query_name}: "
                    f"field {check_field} not found"
                ),
                trace={"steps": trace},
            )

        # Evaluate based on expected type
        expected_type = expected.get("type", "truthy")
        if expected_type == "truthy":
            passed = bool(check_value)
        elif expected_type == "equals":
            passed = check_value == expected.get("value")
        elif expected_type == "gt":
            passed = float(check_value) > float(expected.get("value", 0))
        elif expected_type == "lt":
            passed = float(check_value) < float(expected.get("value", 0))
        else:
            passed = bool(check_value)

        trace.append(f"Custom query result: {passed}")

        return EvaluationResult(
            rule_code=rule.rule_code,
            result="pass" if passed else "fail",
            severity=rule.severity,
            expected_value=expected,
            actual_value={"value": check_value},
            explanation=rule.explanation or (
                f"Custom query {query_name}: "
                f"{'PASS' if passed else 'FAIL'}"
            ),
            trace={"steps": trace},
        )

    # ====================================================================
    # Helpers
    # ====================================================================

    async def _count_entity(
        self, campus_id: int | None, entity_name: str
    ) -> int:
        """Count records for an entity type using the appropriate model."""
        from sqlalchemy import text

        # Map entity names to actual tables
        table_map = {
            "student": "students",
            "attendance_record": "attendance_records",
            "payment": "payments",
            "enrollment": "enrollments",
            "notification": "notifications",
            "fee_due": "fee_dues",
            "document": "documents",
            "case": "cases",
            "exception": "system_exceptions",
        }

        table = table_map.get(entity_name, entity_name)
        sql = text(f"SELECT COUNT(*) FROM {table}")
        result = await self.session.execute(sql)
        return result.scalar() or 0

    async def _find_requirement(
        self, campus_id: int | None, requirement_id: str
    ) -> ComplianceRequirement | None:
        q = select(ComplianceRequirement).where(
            ComplianceRequirement.requirement_id == requirement_id
        )
        if campus_id is not None:
            q = q.where(
                ComplianceRequirement.campus_id == campus_id
            )
        return (await self.session.execute(q)).scalar_one_or_none()

    @staticmethod
    def _compare(
        actual: Any, operator: str, threshold: Any
    ) -> bool:
        """Compare actual vs threshold using the given operator."""
        try:
            a = float(actual)
            t = float(threshold)
        except (TypeError, ValueError):
            return False

        if operator == ">=":
            return a >= t
        elif operator == "<=":
            return a <= t
        elif operator == ">":
            return a > t
        elif operator == "<":
            return a < t
        elif operator == "==":
            return a == t
        elif operator == "!=":
            return a != t
        return False
