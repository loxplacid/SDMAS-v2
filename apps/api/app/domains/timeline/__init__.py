"""Unified Operational Timeline domain.

Aggregates read-only operational events from *persisted* sources (audit
logs, workflow approval history, notifications, payments, enrollments,
admissions, risk findings) into a single normalized timeline — no new
event storage is introduced. See ``service.py`` for aggregation, RBAC
and tenant-isolation rules.
"""
