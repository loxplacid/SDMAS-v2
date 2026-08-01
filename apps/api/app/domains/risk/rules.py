"""Deterministic risk rule definitions.

Every rule:

- has a stable ``code`` (used as the persistence key),
- belongs to one of the six risk categories,
- declares a human-readable name/description,
- declares default thresholds that a school may override via
  ``risk_rule_configs``,
- documents a deterministic scoring model (0–100) and the recommended
  action.

The engine is explicitly NOT predictive and NOT AI: each rule is a pure
function of persisted school data, evaluated at a point in time and
snapshotted into ``risk_findings``.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# ---------------------------------------------------------------------------
# Rule metadata
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RuleDefinition:
    code: str
    category: str
    name: str
    description: str
    entity_type: str  # student | admission_application
    defaults: dict[str, Any]
    recommended_action: str


# ---------------------------------------------------------------------------
# Default rules (global, seeded into risk_rule_configs with campus_id NULL)
# ---------------------------------------------------------------------------

DEFAULT_RULES: list[RuleDefinition] = [
    # ── Attendance ──────────────────────────────────────────────────────
    RuleDefinition(
        code="attendance_below_threshold",
        category="attendance",
        name="Attendance below threshold",
        description="Attendance percentage over the current window is below the configured minimum.",
        entity_type="student",
        defaults={"min_percentage": 75.0, "window_days": 30},
        recommended_action="Review attendance with the class teacher; contact parents.",
    ),
    RuleDefinition(
        code="attendance_consecutive_absences",
        category="attendance",
        name="Repeated consecutive absences",
        description="Student was absent for N or more consecutive school days.",
        entity_type="student",
        defaults={"max_consecutive_absences": 5},
        recommended_action="Reach out to parents to investigate the absence streak.",
    ),
    RuleDefinition(
        code="attendance_declining_trend",
        category="attendance",
        name="Declining attendance trend",
        description="Attendance percentage has declined by more than the threshold over two windows.",
        entity_type="student",
        defaults={"decline_threshold": 10.0, "window_days": 14},
        recommended_action="Investigate the cause of the downward attendance trend.",
    ),
    # ── Finance ─────────────────────────────────────────────────────────
    RuleDefinition(
        code="fees_overdue",
        category="finance",
        name="Overdue fees",
        description="One or more fee dues are past their due date with an unpaid balance.",
        entity_type="student",
        defaults={"max_days_overdue": 0},
        recommended_action="Send a fee reminder and follow up with the parent/guardian.",
    ),
    RuleDefinition(
        code="fees_overdue_duration",
        category="finance",
        name="Long-overdue fees",
        description="A fee due has remained unpaid for longer than the configured overdue window.",
        entity_type="student",
        defaults={"max_overdue_days": 30},
        recommended_action="Escalate to the finance office for a payment plan or reminder.",
    ),
    RuleDefinition(
        code="fees_high_outstanding",
        category="finance",
        name="High outstanding balance",
        description="Total unpaid balance across all fee dues exceeds the configured amount.",
        entity_type="student",
        defaults={"max_outstanding": 50_000_00},  # paise (₹50,000)
        recommended_action="Schedule a meeting with the family to discuss payment options.",
    ),
    # ── Academic ────────────────────────────────────────────────────────
    RuleDefinition(
        code="academic_low_performance",
        category="academic",
        name="Low academic performance",
        description="Average marks percentage across graded subjects is below the threshold.",
        entity_type="student",
        defaults={"min_percentage": 40.0},
        recommended_action="Arrange academic support / extra help for underperforming subjects.",
    ),
    RuleDefinition(
        code="academic_declining_performance",
        category="academic",
        name="Declining academic performance",
        description="Average marks percentage declined by more than the threshold between grading periods.",
        entity_type="student",
        defaults={"decline_threshold": 10.0},
        recommended_action="Discuss performance trend with subject teachers and parents.",
    ),
    # ── Documents ───────────────────────────────────────────────────────
    RuleDefinition(
        code="documents_missing_required",
        category="documents",
        name="Missing required documents",
        description="Student is missing one or more required document categories.",
        entity_type="student",
        defaults={"required_categories": ["birth_certificate", "admission_form"]},
        recommended_action="Notify parents to submit the missing documents.",
    ),
    # ── Admissions ──────────────────────────────────────────────────────
    RuleDefinition(
        code="admissions_stalled",
        category="admissions",
        name="Admission application stalled",
        description="Application has not progressed for longer than the configured period.",
        entity_type="admission_application",
        defaults={"max_stalled_days": 14},
        recommended_action="Follow up on the stalled application and move it forward.",
    ),
    # ── Operational ─────────────────────────────────────────────────────
    RuleDefinition(
        code="operational_no_guardian",
        category="operational",
        name="Missing guardian contact",
        description="Student has no guardian or primary contact recorded.",
        entity_type="student",
        defaults={},
        recommended_action="Collect guardian / emergency contact details.",
    ),
]

RULE_REGISTRY: dict[str, RuleDefinition] = {
    rule.code: rule for rule in DEFAULT_RULES
}

# Rules that surface financial data → only shown to roles with fees.view.
FINANCIAL_RULE_CODES = {
    "fees_overdue",
    "fees_overdue_duration",
    "fees_high_outstanding",
}

# Rules that are leadership-only (admissions pipeline).
ADMISSIONS_RULE_CODES = {"admissions_stalled"}


def get_rule(code: str) -> RuleDefinition:
    if code not in RULE_REGISTRY:
        raise KeyError(f"Unknown risk rule: {code}")
    return RULE_REGISTRY[code]


# ---------------------------------------------------------------------------
# Scoring helpers (deterministic)
# ---------------------------------------------------------------------------


def severity_from_score(score: float) -> str:
    """Map a 0–100 risk score to a severity band.

    critical ≥ 80, high ≥ 60, medium ≥ 40, low ≥ 20, else no finding
    (callers only emit findings above ``min_score``).
    """
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _pct_score(current: float, good: float, floor: float = 0.0) -> float:
    """Score when a percentage is *below* ``good``.

    Linear from ``good`` (score 0) down to ``floor`` (score 100).
    """
    if current >= good:
        return 0.0
    span = max(good - floor, 1e-9)
    return round(min((good - current) / span * 100, 100.0), 1)
