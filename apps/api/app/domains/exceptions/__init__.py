"""Universal Exception Management domain.

Provides a single, canonical representation for all system-detected issues
(data quality, financial, risk, migration, compliance, operational) that
require tracking, investigation, and potentially human action.

Design principles:
- One ``SystemException`` per detected issue (never duplicated).
- Optional link to ``Case`` when human action is required.
- Optional link to ``WorkflowInstance`` for structured resolution.
- Backward-compatible: existing findings can create exceptions without
  breaking their current lifecycle.
- Deterministic: exceptions are created from real data, not heuristic scans.
"""

from app.domains.exceptions.models import (
    EXCEPTION_SEVERITY_CRITICAL,
    EXCEPTION_SEVERITY_HIGH,
    EXCEPTION_SEVERITY_INFO,
    EXCEPTION_SEVERITY_LOW,
    EXCEPTION_SEVERITY_MEDIUM,
    EXCEPTION_STATUS_ACKNOWLEDGED,
    EXCEPTION_STATUS_CLOSED,
    EXCEPTION_STATUS_IN_PROGRESS,
    EXCEPTION_STATUS_OPEN,
    EXCEPTION_STATUS_RESOLVED,
    EXCEPTION_TYPE_COMPLIANCE,
    EXCEPTION_TYPE_DATA_QUALITY,
    EXCEPTION_TYPE_FINANCIAL,
    EXCEPTION_TYPE_MIGRATION,
    EXCEPTION_TYPE_OPERATIONAL,
    EXCEPTION_TYPE_RISK,
    SystemException,
    SystemExceptionEvent,
)
from app.domains.exceptions.router import router
from app.domains.exceptions.service import ExceptionService

__all__ = [
    "SystemException",
    "SystemExceptionEvent",
    "ExceptionService",
    "router",
    "EXCEPTION_TYPE_DATA_QUALITY",
    "EXCEPTION_TYPE_FINANCIAL",
    "EXCEPTION_TYPE_MIGRATION",
    "EXCEPTION_TYPE_RISK",
    "EXCEPTION_TYPE_COMPLIANCE",
    "EXCEPTION_TYPE_OPERATIONAL",
    "EXCEPTION_SEVERITY_INFO",
    "EXCEPTION_SEVERITY_LOW",
    "EXCEPTION_SEVERITY_MEDIUM",
    "EXCEPTION_SEVERITY_HIGH",
    "EXCEPTION_SEVERITY_CRITICAL",
    "EXCEPTION_STATUS_OPEN",
    "EXCEPTION_STATUS_ACKNOWLEDGED",
    "EXCEPTION_STATUS_IN_PROGRESS",
    "EXCEPTION_STATUS_RESOLVED",
    "EXCEPTION_STATUS_CLOSED",
]
