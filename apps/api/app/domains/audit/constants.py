"""Audit action and resource type constants.

These constants provide a typed vocabulary for audit logging across
all domain services.  Using them ensures consistent action/resource
naming in the audit trail.

Actions are **semantic** (what actually happened), not HTTP-method
labels.  A ``POST`` may be CREATE, LOGIN, PAYMENT_CREATED, APPROVE or
VERIFY depending on the endpoint — services must choose the meaningful
action so the trail answers "what really happened?".
"""

from __future__ import annotations

# ── Action types ──────────────────────────────────────────────────────────

LOGIN = "LOGIN"
LOGOUT = "LOGOUT"
LOGIN_FAILED = "LOGIN_FAILED"
CREATE = "CREATE"
UPDATE = "UPDATE"
DELETE = "DELETE"
PASSWORD_CHANGE = "PASSWORD_CHANGE"
EXPORT = "EXPORT"
DOWNLOAD = "DOWNLOAD"
BULK_OPERATION = "BULK_OPERATION"
APPROVE = "APPROVE"
REJECT = "REJECT"
VERIFY = "VERIFY"
RECORD_PAYMENT = "RECORD_PAYMENT"
PAYMENT_CREATED = "PAYMENT_CREATED"
PAYMENT_COMPLETED = "PAYMENT_COMPLETED"
REFUND = "REFUND"
RISK = "RISK"
PUBLISH = "PUBLISH"
ARCHIVE = "ARCHIVE"
RESTORE = "RESTORE"
SWITCH_SCHOOL = "SWITCH_SCHOOL"
WEBHOOK_RECEIVED = "WEBHOOK_RECEIVED"
WORKFLOW_STEP = "WORKFLOW_STEP"
STUDENT_TRANSITION = "STUDENT_TRANSITION"
JOB_EXECUTED = "JOB_EXECUTED"
MIGRATION_RUN = "MIGRATION_RUN"

ALL_ACTIONS = frozenset({
    LOGIN,
    LOGOUT,
    LOGIN_FAILED,
    CREATE,
    UPDATE,
    DELETE,
    PASSWORD_CHANGE,
    EXPORT,
    DOWNLOAD,
    BULK_OPERATION,
    APPROVE,
    REJECT,
    VERIFY,
    RECORD_PAYMENT,
    PAYMENT_CREATED,
    PAYMENT_COMPLETED,
    REFUND,
    RISK,
    PUBLISH,
    ARCHIVE,
    RESTORE,
    SWITCH_SCHOOL,
    WEBHOOK_RECEIVED,
    WORKFLOW_STEP,
    STUDENT_TRANSITION,
    JOB_EXECUTED,
    MIGRATION_RUN,
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
RECONCILIATION = "payment_reconciliation"
DOCUMENT = "document"
REPORT = "report"
