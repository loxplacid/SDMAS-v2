import type { ReactNode } from 'react'
import { usePermission } from '../../hooks/use-permission'

interface CanProps {
  /** Permission(s) to check. If multiple, ALL must be granted. */
  permission: string | string[]
  /** Render when permission(s) are granted. */
  children: ReactNode
  /** Optional fallback rendered when permission(s) are denied. */
  fallback?: ReactNode | null
}

/**
 * Declarative permission gate for conditional rendering.
 *
 * @example
 * ```tsx
 * <Can permission="students.delete">
 *   <button onClick={handleDelete}>Delete Student</button>
 * </Can>
 *
 * <Can permission={['fees.view', 'fees.export']} fallback={<span>No access</span>}>
 *   <ExportButton />
 * </Can>
 * ```
 */
export function Can({ permission, children, fallback = null }: CanProps) {
  const { can } = usePermission()

  const permissions = Array.isArray(permission) ? permission : [permission]
  const hasAll = permissions.every((p) => can(p))

  if (!hasAll) return <>{fallback}</>
  return <>{children}</>
}
