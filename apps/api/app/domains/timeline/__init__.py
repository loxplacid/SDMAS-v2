"""Unified Operational Timeline domain.

Aggregates read-only operational events from *persisted* sources (audit
logs, workflow approval history, notifications, payments, enrollments,
admissions, risk findings) into a single normalized timeline — no new
event storage is introduced.

Modules
-------
- ``service.py``  — unified timeline aggregation (RBAC, tenant isolation)
- ``history.py``  — deterministic institutional-history projections (TASK 18)
- ``schemas.py``  — Pydantic models for timeline and history queries
- ``router.py``   — FastAPI endpoints for timeline and institutional memory

Institutional History (TASK 18)
--------------------------------
Reads from canonical event sources (outbox_events, audit_logs, case_events,
system_exception_events, approval_history) to provide:

- Entity history ("What happened to this student?")
- Campus history ("What changed in this campus?")
- Pre-exception timeline ("What happened before this exception?")
- Causal chain ("Which events caused this workflow?")
- Date range diff ("What changed between two dates?")

All projections are deterministic — no AI narratives, no LLM calls.
"""
