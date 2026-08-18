"""Policy-as-code foundation (platform).

A deterministic, explainable policy engine with versioned policies:

- ``policy_definitions``  — a named policy with a stable business key
  (``policy_id``), a scope (attendance, fees, admissions, approvals,
  compliance, security, workflow, global), and lifecycle status
- ``policy_versions``     — immutable snapshots of the policy: rules +
  exceptions + applicability, with effective dates and approval metadata
- ``policy_evaluations``  — every evaluation result, persisted and traceable
  to policy version + input data + result

The engine is **deterministic** — evaluation is a pure function of the
effective policy version and the input data (same input → same result) —
and **explainable** — every result carries per-rule outcomes, applied
exceptions, and the reason.

Rules are data (JSON), not code: a rule is ``{condition, effect, reason}``
where ``condition`` is a composable expression tree over dotted-field
paths with a fixed operator set (eq, neq, lt, lte, gt, gte, in, not_in,
contains, exists, not_exists, is_true, is_false, and, or, not).  No board-
specific policies are hard-coded — the registry only catalogs scopes and
their allowed effects, and policies are created per tenant.

Tenant isolation: every table carries ``campus_id`` (direct tenant
scoping — auto-classified ``TENANT_DIRECT``).
"""

from app.platform.policy.models import (
    DECISION_ALLOW,
    DECISION_DENY,
    DECISION_NOT_APPLICABLE,
    DECISION_REVIEW,
    DECISIONS,
    EFFECT_ALLOW,
    EFFECT_DENY,
    EFFECT_REVIEW,
    EFFECTS,
    POLICY_SCOPES,
    POLICY_STATUS_ACTIVE,
    POLICY_STATUS_DRAFT,
    POLICY_STATUS_RETIRED,
    POLICY_STATUSES,
    VERSION_STATUS_PUBLISHED,
    VERSION_STATUSES,
    PolicyDefinition,
    PolicyEvaluation,
    PolicyVersion,
)
from app.platform.policy.registry import POLICY_SCOPE_CATALOG, PolicyRegistry
from app.platform.policy.repository import PolicyRepository
from app.platform.policy.rules import evaluate_condition, get_path
from app.platform.policy.service import PolicyService

__all__ = [
    "DECISION_ALLOW",
    "DECISION_DENY",
    "DECISION_NOT_APPLICABLE",
    "DECISION_REVIEW",
    "DECISIONS",
    "EFFECT_ALLOW",
    "EFFECT_DENY",
    "EFFECT_REVIEW",
    "EFFECTS",
    "POLICY_SCOPES",
    "POLICY_STATUS_ACTIVE",
    "POLICY_STATUS_DRAFT",
    "POLICY_STATUS_RETIRED",
    "POLICY_STATUSES",
    "VERSION_STATUS_PUBLISHED",
    "VERSION_STATUSES",
    "PolicyDefinition",
    "PolicyEvaluation",
    "PolicyVersion",
    "POLICY_SCOPE_CATALOG",
    "PolicyRegistry",
    "PolicyRepository",
    "evaluate_condition",
    "get_path",
    "PolicyService",
]
