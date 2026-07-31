// Frontend permission constants mirroring the backend permission system.
// These constants MUST stay in sync with app/domains/auth/permissions.py
// on the backend.  Permissions follow the <resource>.<action> convention.
//
// Use with the usePermission hook or the Can component to conditionally
// render or disable UI elements based on the current user's role.

// -- Students -----------------------------------------------------------
export const STUDENTS_VIEW = 'students.view'
export const STUDENTS_CREATE = 'students.create'
export const STUDENTS_UPDATE = 'students.update'
export const STUDENTS_DELETE = 'students.delete'
export const STUDENTS_EXPORT = 'students.export'

// -- Teachers -----------------------------------------------------------
export const TEACHERS_VIEW = 'teachers.view'
export const TEACHERS_CREATE = 'teachers.create'
export const TEACHERS_UPDATE = 'teachers.update'
export const TEACHERS_DELETE = 'teachers.delete'

// -- Attendance ---------------------------------------------------------
export const ATTENDANCE_VIEW = 'attendance.view'
export const ATTENDANCE_RECORD = 'attendance.record'
export const ATTENDANCE_UPDATE = 'attendance.update'
export const ATTENDANCE_EXPORT = 'attendance.export'
export const ATTENDANCE_APPROVE = 'attendance.approve'

// -- Fees ---------------------------------------------------------------
export const FEES_VIEW = 'fees.view'
export const FEES_CREATE = 'fees.create'
export const FEES_UPDATE = 'fees.update'
export const FEES_DELETE = 'fees.delete'
export const FEES_RECORD_PAYMENT = 'fees.record_payment'
export const FEES_REFUND = 'fees.refund'
export const FEES_EXPORT = 'fees.export'

// -- Academic -----------------------------------------------------------
export const ACADEMIC_VIEW = 'academic.view'
export const ACADEMIC_CREATE = 'academic.create'
export const ACADEMIC_UPDATE = 'academic.update'
export const ACADEMIC_DELETE = 'academic.delete'

// -- Subjects -----------------------------------------------------------
export const SUBJECTS_VIEW = 'subjects.view'
export const SUBJECTS_CREATE = 'subjects.create'
export const SUBJECTS_UPDATE = 'subjects.update'
export const SUBJECTS_DELETE = 'subjects.delete'

// -- Admissions ---------------------------------------------------------
export const ADMISSIONS_VIEW = 'admissions.view'
export const ADMISSIONS_CREATE = 'admissions.create'
export const ADMISSIONS_UPDATE = 'admissions.update'
export const ADMISSIONS_APPROVE = 'admissions.approve'

// -- Reports ------------------------------------------------------------
export const REPORTS_VIEW = 'reports.view'
export const REPORTS_CREATE = 'reports.create'
export const REPORTS_EXPORT = 'reports.export'

// -- Analytics ----------------------------------------------------------
export const ANALYTICS_VIEW = 'analytics.view'
export const ANALYTICS_EXPORT = 'analytics.export'

// -- Notifications ------------------------------------------------------
export const NOTIFICATIONS_VIEW = 'notifications.view'
export const NOTIFICATIONS_CREATE = 'notifications.create'
export const NOTIFICATIONS_DELETE = 'notifications.delete'

// -- Operations / Data Ops ----------------------------------------------
export const OPERATIONS_VIEW = 'operations.view'
export const OPERATIONS_EXECUTE = 'operations.execute'
export const OPERATIONS_EXPORT = 'operations.export'

// -- Users & Roles ------------------------------------------------------
export const USERS_VIEW = 'users.view'
export const USERS_CREATE = 'users.create'
export const USERS_UPDATE = 'users.update'
export const USERS_DELETE = 'users.delete'
export const ROLES_MANAGE = 'roles.manage'

// -- Audit --------------------------------------------------------------
export const AUDIT_VIEW = 'audit.view'
export const AUDIT_EXPORT = 'audit.export'

// -- Leave --------------------------------------------------------------
export const LEAVE_VIEW = 'leave.view'
export const LEAVE_CREATE = 'leave.create'
export const LEAVE_UPDATE = 'leave.update'
export const LEAVE_APPROVE = 'leave.approve'

// -- Institution --------------------------------------------------------
export const INSTITUTION_VIEW = 'institution.view'
export const INSTITUTION_MANAGE = 'institution.manage'

// -- Workflow -----------------------------------------------------------
export const WORKFLOW_VIEW = 'workflow.view'
export const WORKFLOW_MANAGE = 'workflow.manage'

// -- Role to permission mappings (mirrors backend ROLE_PERMISSIONS) ----
// The backend is the source of truth; this is used for fast frontend checks.

const ROLE_PERMISSIONS: Record<string, string[]> = {
  admin: [
    STUDENTS_VIEW, STUDENTS_CREATE, STUDENTS_UPDATE, STUDENTS_DELETE, STUDENTS_EXPORT,
    TEACHERS_VIEW, TEACHERS_CREATE, TEACHERS_UPDATE, TEACHERS_DELETE,
    ATTENDANCE_VIEW, ATTENDANCE_RECORD, ATTENDANCE_UPDATE, ATTENDANCE_EXPORT, ATTENDANCE_APPROVE,
    FEES_VIEW, FEES_CREATE, FEES_UPDATE, FEES_DELETE, FEES_RECORD_PAYMENT, FEES_REFUND, FEES_EXPORT,
    ACADEMIC_VIEW, ACADEMIC_CREATE, ACADEMIC_UPDATE, ACADEMIC_DELETE,
    SUBJECTS_VIEW, SUBJECTS_CREATE, SUBJECTS_UPDATE, SUBJECTS_DELETE,
    ADMISSIONS_VIEW, ADMISSIONS_CREATE, ADMISSIONS_UPDATE, ADMISSIONS_APPROVE,
    REPORTS_VIEW, REPORTS_CREATE, REPORTS_EXPORT,
    ANALYTICS_VIEW, ANALYTICS_EXPORT,
    NOTIFICATIONS_VIEW, NOTIFICATIONS_CREATE, NOTIFICATIONS_DELETE,
    OPERATIONS_VIEW, OPERATIONS_EXECUTE, OPERATIONS_EXPORT,
    USERS_VIEW, USERS_CREATE, USERS_UPDATE, USERS_DELETE, ROLES_MANAGE,
    AUDIT_VIEW, AUDIT_EXPORT,
    LEAVE_VIEW, LEAVE_CREATE, LEAVE_UPDATE, LEAVE_APPROVE,
    INSTITUTION_VIEW, INSTITUTION_MANAGE,
    WORKFLOW_VIEW, WORKFLOW_MANAGE,
  ],

  principal: [
    STUDENTS_VIEW, TEACHERS_VIEW,
    ATTENDANCE_VIEW, FEES_VIEW,
    ACADEMIC_VIEW, SUBJECTS_VIEW,
    REPORTS_VIEW, REPORTS_CREATE, REPORTS_EXPORT,
    ANALYTICS_VIEW, ANALYTICS_EXPORT,
    NOTIFICATIONS_VIEW,
    LEAVE_VIEW, LEAVE_APPROVE,
    AUDIT_VIEW,
  ],

  accountant: [
    STUDENTS_VIEW,
    FEES_VIEW, FEES_CREATE, FEES_UPDATE, FEES_RECORD_PAYMENT, FEES_REFUND, FEES_EXPORT,
    REPORTS_VIEW, REPORTS_CREATE, REPORTS_EXPORT,
    ANALYTICS_VIEW,
    NOTIFICATIONS_VIEW,
  ],

  staff: [
    STUDENTS_VIEW,
    ATTENDANCE_VIEW, ATTENDANCE_RECORD, ATTENDANCE_UPDATE, ATTENDANCE_EXPORT,
    NOTIFICATIONS_VIEW, NOTIFICATIONS_CREATE,
    LEAVE_VIEW, LEAVE_CREATE,
  ],

  teacher: [
    STUDENTS_VIEW,
    ATTENDANCE_VIEW, ATTENDANCE_RECORD, ATTENDANCE_UPDATE,
    NOTIFICATIONS_VIEW,
    LEAVE_VIEW, LEAVE_CREATE,
  ],

  student: [
    ATTENDANCE_VIEW,
    FEES_VIEW,
    NOTIFICATIONS_VIEW,
    LEAVE_VIEW,
  ],

  parent: [
    STUDENTS_VIEW,
    ATTENDANCE_VIEW,
    FEES_VIEW,
    NOTIFICATIONS_VIEW,
  ],
}

/** Check if a role has a specific permission (in-memory, sync). */
export function hasPermission(role: string | undefined | null, permission: string): boolean {
  if (!role) return false
  const perms = ROLE_PERMISSIONS[role]
  if (!perms) return false
  return perms.includes(permission)
}

/** Check if ANY of the given roles has a specific permission. */
export function hasAnyRolePermission(roles: string[] | undefined | null, permission: string): boolean {
  if (!roles || roles.length === 0) return false
  return roles.some((role) => hasPermission(role, permission))
}

/** Get all permissions for a given role. */
export function getPermissionsForRole(role: string | undefined | null): string[] {
  if (!role) return []
  return ROLE_PERMISSIONS[role] ?? []
}

/** Get the union of permissions across all given roles. */
export function getAllPermissionsForRoles(roles: string[] | undefined | null): string[] {
  if (!roles || roles.length === 0) return []
  const allPerms = new Set<string>()
  for (const role of roles) {
    const perms = getPermissionsForRole(role)
    for (const p of perms) allPerms.add(p)
  }
  return Array.from(allPerms)
}
