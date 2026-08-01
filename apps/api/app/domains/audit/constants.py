"""Audit action and resource type constants.

These constants provide a typed vocabulary for audit logging across
all domain services.  Using them ensures consistent action/resource
naming in the audit trail.
"""

from __future__ import annotations

# ── Action types ──────────────────────────────────────────────────────────

LOGIN = "LOGIN"
LOGOUT = "LOGOUT"
CREATE = "CREATE"
UPDATE = "UPDATE"
DELETE = "DELETE"
PASSWORD_CHANGE = "PASSWORD_CHANGE"
EXPORT = "EXPORT"
BULK_OPERATION = "BULK_OPERATION"
APPROVE = "APPROVE"
RECORD_PAYMENT = "RECORD_PAYMENT"
REFUND = "REFUND"
RISK = "RISK"

ALL_ACTIONS = frozenset({
    LOGIN,
    LOGOUT,
    CREATE,
    UPDATE,
    DELETE,
    PASSWORD_CHANGE,
    EXPORT,
    BULK_OPERATION,
    APPROVE,
    RECORD_PAYMENT,
    REFUND,
    RISK,
})

# ── Resource types ────────────────────────────────────────────────────────

USER = "user"
STUDENT = "student"
TEACHER = "teacher"
ATTENDANCE = "attendance"
FEE = "fee"
PAYMENT = "payment"
ACADEMIC = "academic"
SUBJECT = "subject"
ADMISSION = "admission"
LEAVE = "leave"
WORKFLOW = "workflow"
NOTIFICATION = "notification"
INSTITUTION = "institution"
ROLE = "role"
PERMISSION = "permission"
EXPORT_JOB = "export"
BULK_JOB = "bulk_operation"
