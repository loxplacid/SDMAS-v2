"""Universal reconciliation engine (platform).

A generic, reusable reconciliation framework — *not* one-off per-domain
reconcilers.  It answers "do these two datasets agree?" for any future
use case:

- payment ↔ invoice
- legacy student ↔ canonical student
- attendance ↔ biometric
- transport ↔ boarding
- source ↔ migrated target
- inventory ↔ physical count

Primitives
----------
- ``reconciliation_runs``          — one reconciliation pass between two
  datasets (source side + target side) with status, summary, approval
- ``reconciliation_rule_configs``  — named, reusable matching/comparison
  rules (match keys + normalizers + tolerance fields)
- ``reconciliation_matches``       — per-record result (matched / source
  only / target only / exception) with per-field differences
- ``reconciliation_exceptions``    — out-of-tolerance or unmatched records
  requiring manual review / resolution
- ``reconciliation_approvals``     — approval trail (approve / reject /
  escalate) with comment
- ``reconciliation_evidence``      — evidence pointers (audit entries,
  files, source records, reports) — referenced, never copied

Properties
----------
- **deterministic matching** — pure normalization + key comparison, no AI,
  same input → same result
- **configurable rules** — match keys, normalizers and tolerance rules are
  data (``rule_configs``), not code
- **manual review** — exceptions carry review state and resolution notes
- **audit trail** — every run/approval/resolution is audited + evidenced
- **tenant isolation** — all tables carry ``campus_id``; every read goes
  through the tenant-scoped repository
- **idempotency** — a run is keyed by ``idempotency_key`` (unique per
  campus); re-running the same pass returns the same run instead of
  duplicating records
"""

from app.platform.reconciliation.matching import (
    build_match_key,
    classify,
    compare_records,
    match_records,
    normalize_value,
    unmatched_targets,
)
from app.platform.reconciliation.models import (
    APPROVAL_APPROVE,
    APPROVAL_DECISIONS,
    APPROVAL_ESCALATE,
    APPROVAL_REJECT,
    EXCEPTION_SEVERITIES,
    EXCEPTION_STATUSES,
    MATCH_STATUSES,
    RUN_STATUSES,
    ReconciliationApproval,
    ReconciliationEvidence,
    ReconciliationException,
    ReconciliationMatch,
    ReconciliationRuleConfig,
    ReconciliationRun,
)
from app.platform.reconciliation.repository import ReconciliationRepository
from app.platform.reconciliation.service import ReconciliationService

__all__ = [
    "build_match_key",
    "classify",
    "compare_records",
    "match_records",
    "normalize_value",
    "unmatched_targets",
    "APPROVAL_APPROVE",
    "APPROVAL_DECISIONS",
    "APPROVAL_ESCALATE",
    "APPROVAL_REJECT",
    "EXCEPTION_SEVERITIES",
    "EXCEPTION_STATUSES",
    "MATCH_STATUSES",
    "RUN_STATUSES",
    "ReconciliationApproval",
    "ReconciliationEvidence",
    "ReconciliationException",
    "ReconciliationMatch",
    "ReconciliationRuleConfig",
    "ReconciliationRun",
    "ReconciliationRepository",
    "ReconciliationService",
]
