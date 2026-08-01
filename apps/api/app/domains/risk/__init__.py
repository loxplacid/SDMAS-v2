"""Deterministic Risk & Attention Engine.

A rule-based, explainable, auditable system that flags students and
operational entities needing attention. Explicitly not AI.
"""

from app.domains.risk.models import RiskFinding, RiskRuleConfig
from app.domains.risk.rules import DEFAULT_RULES, RULE_REGISTRY
from app.domains.risk.service import RiskService

__all__ = [
    "DEFAULT_RULES",
    "RULE_REGISTRY",
    "RiskFinding",
    "RiskRuleConfig",
    "RiskService",
]
