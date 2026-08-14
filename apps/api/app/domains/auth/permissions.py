"""Enterprise permission constants and registry for SDMAS.

Every permission follows the convention ``<resource>.<action>``.

Resources
---------
- students, teachers, attendance, fees, academic, subjects
- admissions, notifications, reports, analytics, operations
- users, audit, leave, institution, workflow, roles

Actions
-------
- view          — read / list / get
- create        — add new records
- update        — modify existing records
- delete        — remove records
- approve       — approve workflows or requests
- export        — export data to files
- manage        — administrative management (roles, settings, etc.)
"""

from __future__ import annotations

from typing import Final

# =====================================================================
# Permission string constants
# =====================================================================

# ── Students ──────────────────────────────────────────────────────────
STUDENTS_VIEW: Final[str] = "students.view"
STUDENTS_CREATE: Final[str] = "students.create"
STUDENTS_UPDATE: Final[str] = "students.update"
STUDENTS_DELETE: Final[str] = "students.delete"
STUDENTS_EXPORT: Final[str] = "students.export"

# ── Teachers ──────────────────────────────────────────────────────────
TEACHERS_VIEW: Final[str] = "teachers.view"
TEACHERS_CREATE: Final[str] = "teachers.create"
TEACHERS_UPDATE: Final[str] = "teachers.update"
TEACHERS_DELETE: Final[str] = "teachers.delete"

# ── Attendance ────────────────────────────────────────────────────────
ATTENDANCE_VIEW: Final[str] = "attendance.view"
ATTENDANCE_RECORD: Final[str] = "attendance.record"
ATTENDANCE_UPDATE: Final[str] = "attendance.update"
ATTENDANCE_EXPORT: Final[str] = "attendance.export"
ATTENDANCE_APPROVE: Final[str] = "attendance.approve"

# ── Fees ──────────────────────────────────────────────────────────────
FEES_VIEW: Final[str] = "fees.view"
FEES_CREATE: Final[str] = "fees.create"
FEES_UPDATE: Final[str] = "fees.update"
FEES_DELETE: Final[str] = "fees.delete"
FEES_RECORD_PAYMENT: Final[str] = "fees.record_payment"
FEES_REFUND: Final[str] = "fees.refund"
FEES_EXPORT: Final[str] = "fees.export"

# ── Academic ──────────────────────────────────────────────────────────
ACADEMIC_VIEW: Final[str] = "academic.view"
ACADEMIC_CREATE: Final[str] = "academic.create"
ACADEMIC_UPDATE: Final[str] = "academic.update"
ACADEMIC_DELETE: Final[str] = "academic.delete"

# ── Subjects ──────────────────────────────────────────────────────────
SUBJECTS_VIEW: Final[str] = "subjects.view"
SUBJECTS_CREATE: Final[str] = "subjects.create"
SUBJECTS_UPDATE: Final[str] = "subjects.update"
SUBJECTS_DELETE: Final[str] = "subjects.delete"

# ── Admissions ────────────────────────────────────────────────────────
ADMISSIONS_VIEW: Final[str] = "admissions.view"
ADMISSIONS_CREATE: Final[str] = "admissions.create"
ADMISSIONS_UPDATE: Final[str] = "admissions.update"
ADMISSIONS_APPROVE: Final[str] = "admissions.approve"

# ── Reports ───────────────────────────────────────────────────────────
REPORTS_VIEW: Final[str] = "reports.view"
REPORTS_CREATE: Final[str] = "reports.create"
REPORTS_EXPORT: Final[str] = "reports.export"

# ── Analytics ─────────────────────────────────────────────────────────
ANALYTICS_VIEW: Final[str] = "analytics.view"
ANALYTICS_EXPORT: Final[str] = "analytics.export"

# ── Notifications ─────────────────────────────────────────────────────
NOTIFICATIONS_VIEW: Final[str] = "notifications.view"
NOTIFICATIONS_CREATE: Final[str] = "notifications.create"
NOTIFICATIONS_DELETE: Final[str] = "notifications.delete"

# ── Operations / Data Ops ─────────────────────────────────────────────
OPERATIONS_VIEW: Final[str] = "operations.view"
OPERATIONS_EXECUTE: Final[str] = "operations.execute"
OPERATIONS_EXPORT: Final[str] = "operations.export"

# ── Users & Roles ─────────────────────────────────────────────────────
USERS_VIEW: Final[str] = "users.view"
USERS_CREATE: Final[str] = "users.create"
USERS_UPDATE: Final[str] = "users.update"
USERS_DELETE: Final[str] = "users.delete"
ROLES_MANAGE: Final[str] = "roles.manage"

# ── Audit ─────────────────────────────────────────────────────────────
AUDIT_VIEW: Final[str] = "audit.view"
AUDIT_EXPORT: Final[str] = "audit.export"

# ── Leave ─────────────────────────────────────────────────────────────
LEAVE_VIEW: Final[str] = "leave.view"
LEAVE_CREATE: Final[str] = "leave.create"
LEAVE_UPDATE: Final[str] = "leave.update"
LEAVE_APPROVE: Final[str] = "leave.approve"

# ── Institution / Tenant ──────────────────────────────────────────────
INSTITUTION_VIEW: Final[str] = "institution.view"
INSTITUTION_MANAGE: Final[str] = "institution.manage"

# ── Workflow ──────────────────────────────────────────────────────────
WORKFLOW_VIEW: Final[str] = "workflow.view"
WORKFLOW_MANAGE: Final[str] = "workflow.manage"

# ── Platform (cross-tenant) ───────────────────────────────────────────
# Platform-level permissions gate CROSS-TENANT / unscoped access.  A
# tenant admin (even ``admin``) is scoped to their campus; only a user
# holding an explicit platform permission may operate outside tenant
# boundaries.  ``platform.access`` grants read+operate across campuses;
# ``platform.manage`` grants administrative cross-tenant operations.
PLATFORM_ACCESS: Final[str] = "platform.access"
PLATFORM_MANAGE: Final[str] = "platform.manage"


# =====================================================================
# Permission Registry — used for seeding and validation
# =====================================================================

ALL_PERMISSIONS: list[str] = [
    # Students
    STUDENTS_VIEW, STUDENTS_CREATE, STUDENTS_UPDATE, STUDENTS_DELETE, STUDENTS_EXPORT,
    # Teachers
    TEACHERS_VIEW, TEACHERS_CREATE, TEACHERS_UPDATE, TEACHERS_DELETE,
    # Attendance
    ATTENDANCE_VIEW, ATTENDANCE_RECORD, ATTENDANCE_UPDATE, ATTENDANCE_EXPORT, ATTENDANCE_APPROVE,
    # Fees
    FEES_VIEW, FEES_CREATE, FEES_UPDATE, FEES_DELETE, FEES_RECORD_PAYMENT, FEES_REFUND, FEES_EXPORT,
    # Academic
    ACADEMIC_VIEW, ACADEMIC_CREATE, ACADEMIC_UPDATE, ACADEMIC_DELETE,
    # Subjects
    SUBJECTS_VIEW, SUBJECTS_CREATE, SUBJECTS_UPDATE, SUBJECTS_DELETE,
    # Admissions
    ADMISSIONS_VIEW, ADMISSIONS_CREATE, ADMISSIONS_UPDATE, ADMISSIONS_APPROVE,
    # Reports
    REPORTS_VIEW, REPORTS_CREATE, REPORTS_EXPORT,
    # Analytics
    ANALYTICS_VIEW, ANALYTICS_EXPORT,
    # Notifications
    NOTIFICATIONS_VIEW, NOTIFICATIONS_CREATE, NOTIFICATIONS_DELETE,
    # Operations
    OPERATIONS_VIEW, OPERATIONS_EXECUTE, OPERATIONS_EXPORT,
    # Users
    USERS_VIEW, USERS_CREATE, USERS_UPDATE, USERS_DELETE, ROLES_MANAGE,
    # Audit
    AUDIT_VIEW, AUDIT_EXPORT,
    # Leave
    LEAVE_VIEW, LEAVE_CREATE, LEAVE_UPDATE, LEAVE_APPROVE,
    # Institution
    INSTITUTION_VIEW, INSTITUTION_MANAGE,
    # Workflow
    WORKFLOW_VIEW, WORKFLOW_MANAGE,
    # Platform
    PLATFORM_ACCESS, PLATFORM_MANAGE,
]


# =====================================================================
# Default role → permission mappings
# =====================================================================

#: The roles a tenant admin may assign to users (primary ``role`` or M2M
#: ``assigned_roles``).  Single source of truth — schemas and routers
#: that validate role input MUST reference this set so a new role cannot
#: be added in one place and forgotten in another.  Platform roles
#: (``platform_admin``) are deliberately excluded: a tenant admin must
#: never be able to mint a cross-tenant account.
TENANT_ROLES: frozenset[str] = frozenset(
    {"admin", "principal", "accountant", "staff", "teacher", "student", "parent"}
)

# Every permission EXCEPT the platform-gating ones.  ``admin`` is a
# TENANT role: it gets full control inside its own campus but must NEVER
# satisfy a platform check — "unscoped" must not imply platform admin.
TENANT_ALL_PERMISSIONS: list[str] = [
    p for p in ALL_PERMISSIONS if p not in (PLATFORM_ACCESS, PLATFORM_MANAGE)
]


ROLE_PERMISSIONS: dict[str, list[str]] = {
    # Platform operator: explicit cross-tenant access.  ``admin`` is a
    # TENANT role and is deliberately NOT granted platform permissions,
    # so a tenant admin can never see another campus without an explicit
    # platform grant (see multi_tenant.dependencies.resolve_tenant_context).
    "platform_admin": [PLATFORM_ACCESS, PLATFORM_MANAGE, *TENANT_ALL_PERMISSIONS],

    "admin": TENANT_ALL_PERMISSIONS,  # tenant-level admin: everything within their campus

    "principal": [
        STUDENTS_VIEW, STUDENTS_UPDATE,
        TEACHERS_VIEW,
        ATTENDANCE_VIEW,
        FEES_VIEW,
        ACADEMIC_VIEW, SUBJECTS_VIEW, ACADEMIC_CREATE, ACADEMIC_UPDATE,
        ADMISSIONS_VIEW, ADMISSIONS_CREATE, ADMISSIONS_UPDATE, ADMISSIONS_APPROVE,
        REPORTS_VIEW, REPORTS_CREATE, REPORTS_EXPORT,
        ANALYTICS_VIEW, ANALYTICS_EXPORT,
        NOTIFICATIONS_VIEW,
        LEAVE_VIEW, LEAVE_APPROVE,
        AUDIT_VIEW,
        WORKFLOW_VIEW, WORKFLOW_MANAGE,
    ],

    "accountant": [
        STUDENTS_VIEW,
        FEES_VIEW, FEES_CREATE, FEES_UPDATE, FEES_RECORD_PAYMENT, FEES_REFUND, FEES_EXPORT,
        REPORTS_VIEW, REPORTS_CREATE, REPORTS_EXPORT,
        ANALYTICS_VIEW,
        NOTIFICATIONS_VIEW,
    ],

    "staff": [
        STUDENTS_VIEW, STUDENTS_CREATE, STUDENTS_UPDATE,
        ACADEMIC_VIEW, SUBJECTS_VIEW,
        ATTENDANCE_VIEW, ATTENDANCE_RECORD, ATTENDANCE_UPDATE, ATTENDANCE_EXPORT,
        NOTIFICATIONS_VIEW, NOTIFICATIONS_CREATE,
        LEAVE_VIEW, LEAVE_CREATE, LEAVE_UPDATE,
    ],

    "teacher": [
        STUDENTS_VIEW,
        ATTENDANCE_VIEW, ATTENDANCE_RECORD, ATTENDANCE_UPDATE,
        NOTIFICATIONS_VIEW,
        LEAVE_VIEW, LEAVE_CREATE,
    ],

    "student": [
        ATTENDANCE_VIEW,
        FEES_VIEW,
        NOTIFICATIONS_VIEW,
        LEAVE_VIEW,
    ],

    "parent": [
        STUDENTS_VIEW,
        ATTENDANCE_VIEW,
        FEES_VIEW,
        NOTIFICATIONS_VIEW,
    ],
}


def get_permissions_for_role(role: str) -> list[str]:
    """Return the list of permissions granted to a given role name.

    Falls back to an empty list for unknown roles so that new roles
    are locked down by default.
    """
    return ROLE_PERMISSIONS.get(role, [])


def has_permission(role: str, permission: str) -> bool:
    """Check if a role is granted a specific permission."""
    return permission in get_permissions_for_role(role)
