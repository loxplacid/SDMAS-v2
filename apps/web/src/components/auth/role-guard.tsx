import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../api/auth/auth-context'
import { Loading } from '../ui/loading'
import { hasRouteAccess, getHomeRoute } from '../../types/roles'

interface RoleGuardProps {
  children: React.ReactNode
  /** Required role(s). If empty/omitted, any authenticated user can access */
  roles?: string[]
}

/**
 * Guards a route based on user role.
 * - If user doesn't have required role, redirects to their role's home page.
 * - If user role doesn't match any of the allowed `roles` array, redirects.
 * - Omitting `roles` allows any authenticated user.
 */
export function RoleGuard({ children, roles }: RoleGuardProps) {
  const { isAuthenticated, isLoading, user } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return <Loading text="Checking permissions..." />
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  const userRole = user?.role || ''

  // If specific roles are required, check against them
  if (roles && roles.length > 0) {
    if (!roles.includes(userRole)) {
      // Redirect to the user's home route for their role
      return <Navigate to={getHomeRoute(userRole)} replace />
    }
  }

  // Check general route access permissions
  if (!hasRouteAccess(userRole, location.pathname)) {
    return <Navigate to={getHomeRoute(userRole)} replace />
  }

  return <>{children}</>
}
