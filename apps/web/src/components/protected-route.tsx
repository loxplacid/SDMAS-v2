import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../api/auth/auth-context'
import { Loading } from './ui/loading'

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return <Loading text="Checking authentication..." />
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}