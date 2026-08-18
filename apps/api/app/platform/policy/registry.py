"""Policy-as-code — policy registry.

The registry is a *catalogue*, not a policy store:

- ``POLICY_SCOPE_CATALOG`` — every supported scope with a description and
  its allowed rule effects (what a policy in that scope may decide)
- ``POLICY_OPERATORS`` — the closed condition-operator set (from rules.py)
- ``PolicyRegistry`` — runtime lookup of scope metadata and a seed helper
  that creates an empty draft policy for a scope (scaffolding; no
  board-specific rules are hard-coded — tenants author their own)

Future domains (attendance, fees, admissions, approvals, compliance,
security, workflows) register their scope here so policy authors get
validation and discoverability, without the engine knowing anything
about those domains.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.platform.policy.models import (
    EFFECT_ALLOW,
    EFFECT_DENY,
    EFFECT_REVIEW,
    POLICY_SCOPE_ADMISSIONS,
    POLICY_SCOPE_APPROVALS,
    POLICY_SCOPE_ATTENDANCE,
    POLICY_SCOPE_COMPLIANCE,
    POLICY_SCOPE_FEES,
    POLICY_SCOPE_GLOBAL,
    POLICY_SCOPE_SECURITY,
    POLICY_SCOPE_WORKFLOW,
)
from app.platform.policy.rules import evaluate_condition

#: Closed operator set exposed by the rule evaluator.
POLICY_OPERATORS: frozenset[str] = frozenset(
    {
        "eq",
        "neq",
        "lt",
        "lte",
        "gt",
        "gte",
        "in",
        "not_in",
        "contains",
        "exists",
        "not_exists",
        "is_true",
        "is_false",
        "and",
        "or",
        "not",
    }
)


@dataclass(frozen=True)
class PolicyScopeInfo:
    """Metadata for one supported policy scope."""

    key: str
    description: str
    #: Effects policies in this scope may produce (default: allow/deny/review).
    allowed_effects: frozenset[str] = field(
        default_factory=lambda: frozenset({EFFECT_ALLOW, EFFECT_DENY, EFFECT_REVIEW})
    )


#: Catalogue of supported scopes — the registry's source of truth.
POLICY_SCOPE_CATALOG: dict[str, PolicyScopeInfo] = {
    POLICY_SCOPE_ATTENDANCE: PolicyScopeInfo(
        key=POLICY_SCOPE_ATTENDANCE,
        description="Attendance rules (thresholds, excused absence, review triggers).",
    ),
    POLICY_SCOPE_FEES: PolicyScopeInfo(
        key=POLICY_SCOPE_FEES,
        description=(
            "Fee/finance rules (discount eligibility, due-date grace, approval thresholds)."
        ),
    ),
    POLICY_SCOPE_ADMISSIONS: PolicyScopeInfo(
        key=POLICY_SCOPE_ADMISSIONS,
        description="Admission rules (eligibility, document requirements, review gates).",
    ),
    POLICY_SCOPE_APPROVALS: PolicyScopeInfo(
        key=POLICY_SCOPE_APPROVALS,
        description="Approval workflow rules (who/what requires approval, escalations).",
    ),
    POLICY_SCOPE_COMPLIANCE: PolicyScopeInfo(
        key=POLICY_SCOPE_COMPLIANCE,
        description="Compliance rules (retention, consent, mandatory evidence).",
    ),
    POLICY_SCOPE_SECURITY: PolicyScopeInfo(
        key=POLICY_SCOPE_SECURITY,
        description="Security rules (session, device, access-pattern gates).",
    ),
    POLICY_SCOPE_WORKFLOW: PolicyScopeInfo(
        key=POLICY_SCOPE_WORKFLOW,
        description="Workflow rules (routing, time limits, automatic transitions).",
    ),
    POLICY_SCOPE_GLOBAL: PolicyScopeInfo(
        key=POLICY_SCOPE_GLOBAL,
        description="Cross-cutting rules that apply to any subject.",
    ),
}


class PolicyRegistry:
    """Runtime registry: scope metadata lookup + scope validation."""

    def __init__(self) -> None:
        self._scopes: dict[str, PolicyScopeInfo] = dict(POLICY_SCOPE_CATALOG)

    def has_scope(self, scope: str) -> bool:
        return scope in self._scopes

    def get_scope(self, scope: str) -> PolicyScopeInfo | None:
        return self._scopes.get(scope)

    def scopes(self) -> list[PolicyScopeInfo]:
        return sorted(self._scopes.values(), key=lambda s: s.key)

    def validate_effect(self, scope: str, effect: str) -> bool:
        """Whether ``effect`` is allowed for a policy in ``scope``."""
        info = self._scopes.get(scope)
        if info is None:
            return False
        return effect in info.allowed_effects

    def validate_rule(self, scope: str, rule: dict[str, Any]) -> list[str]:
        """Validate a rule dict against the closed operator set.

        Returns a list of problems (empty = valid).  Conditions are walked
        recursively so a bad nested operator is caught.
        """
        problems: list[str] = []
        rule_id = rule.get("id") or "<unnamed>"
        info = self._scopes.get(scope)
        if info is None:
            problems.append(f"rule {rule_id}: unknown scope {scope!r}")
        else:
            effect = rule.get("effect")
            if effect not in info.allowed_effects:
                problems.append(f"rule {rule_id}: effect {effect!r} not allowed in scope {scope!r}")
        condition = rule.get("condition")
        if not isinstance(condition, dict):
            problems.append(f"rule {rule_id}: missing condition object")
        else:
            problems.extend(_validate_condition(condition, rule_id))
        return problems

    def default_policy_id(self, scope: str) -> str:
        """A deterministic default policy key for a scope (seeding)."""
        return f"{scope}.default"


def _validate_condition(condition: dict[str, Any], rule_id: str) -> list[str]:
    problems: list[str] = []
    op = condition.get("op")
    if op not in POLICY_OPERATORS:
        problems.append(f"rule {rule_id}: unknown operator {op!r}")
        return problems
    if op in ("and", "or"):
        subs = condition.get("conditions")
        if not isinstance(subs, list) or not subs:
            problems.append(f"rule {rule_id}: {op} requires a non-empty conditions list")
        else:
            for sub in subs:
                if isinstance(sub, dict):
                    problems.extend(_validate_condition(sub, rule_id))
                else:
                    problems.append(f"rule {rule_id}: {op} child is not a condition object")
    elif op == "not":
        inner = condition.get("condition")
        if not isinstance(inner, dict):
            problems.append(f"rule {rule_id}: not requires a condition object")
        else:
            problems.extend(_validate_condition(inner, rule_id))
    elif op in ("eq", "neq", "lt", "lte", "gt", "gte", "in", "not_in", "contains"):
        if "value" not in condition:
            problems.append(f"rule {rule_id}: operator {op} requires a value")
    # field is optional for boolean/constant operators; presence ops carry
    # their own semantics — no extra checks.
    return problems


#: Module-level singleton (deterministic, stateless).
policy_registry = PolicyRegistry()

__all__ = [
    "POLICY_OPERATORS",
    "POLICY_SCOPE_CATALOG",
    "PolicyRegistry",
    "PolicyScopeInfo",
    "policy_registry",
    "evaluate_condition",
]
