import { useCallback, useMemo } from 'react'
import { useAuth } from '../api/auth/auth-context'
import { hasAnyRolePermission, getAllPermissionsForRoles } from '../types/permissions'

interface UsePermissionReturn {
  /**
   * Check if the current user has a specific permission.
   * Checks across ALL assigned roles (primary role + M2M roles).
   */
  can: (permission: string) => boolean
  /**
   * All permission codes granted to the current user across all roles.
   * This is the union of all permissions from the primary role and any
   * additional roles assigned via the M2M user_roles table.
   */
  permissions: string[]
  /** The current user's primary role string. */
  role: string | undefined
  /** All role codes assigned to the current user (primary + M2M). */
  roles: string[]
}

/**
 * Hook for permission-checking in React components.
 *
 * Mirrors the backend's role-permission mappings on the frontend so that
 * UI elements can be conditionally shown, hidden, or disabled based on
 * the current user's permissions.
 *
 * Supports multi-role users: checks permissions across ALL of the user's
 * assigned roles (primary ``role`` field + ``roles`` list from M2M).
 *
 * @example
 * ```tsx
 * const { can } = usePermission()
 *
 * {can('students.delete') && <DeleteButton />}
 * <Button disabled={!can('fees.export')}>Export</Button>
 * ```
 */
export function usePermission(): UsePermissionReturn {
  const { user } = useAuth()
  const role = user?.role
  const roles = user?.roles ?? []
  const allRoles = useMemo(
    () => {
      const codes = new Set<string>()
      if (role) codes.add(role)
      for (const r of roles) codes.add(r)
      return Array.from(codes)
    },
    [role, roles],
  )

  const permissions = useMemo(
    () => getAllPermissionsForRoles(allRoles),
    [allRoles],
  )

  const can = useCallback(
    (permission: string): boolean => {
      return hasAnyRolePermission(allRoles, permission)
    },
    [allRoles],
  )

  return { can, permissions, role, roles: allRoles }
}
