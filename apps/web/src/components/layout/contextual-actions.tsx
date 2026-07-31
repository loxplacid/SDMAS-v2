import { useLocation, useNavigate } from 'react-router-dom'
import { Button } from '../ui/button'

interface PageAction {
  label: string
  shortcut?: string
  variant?: 'primary' | 'outline'
  to: string
}

export function ContextualPageActions() {
  const location = useLocation()
  const navigate = useNavigate()
  const path = location.pathname

  const routeActions: Record<string, PageAction[]> = {
    '/students': [
      { label: 'Add Student', shortcut: 'N', variant: 'primary', to: '/students?action=add' },
    ],
    '/attendance/records': [
      { label: 'Daily Attendance', variant: 'outline', to: '/attendance/daily' },
      { label: 'Record', shortcut: 'N', variant: 'primary', to: '/attendance/daily' },
    ],
    '/attendance/daily': [
      { label: 'View Records', variant: 'outline', to: '/attendance/records' },
    ],
    '/teachers': [
      { label: 'Add Teacher', shortcut: 'N', variant: 'primary', to: '/teachers?action=add' },
    ],
    '/academic/classes': [
      { label: 'Add Class', shortcut: 'N', variant: 'primary', to: '/academic/classes?action=add' },
    ],
    '/academic/sections': [
      { label: 'Add Section', shortcut: 'N', variant: 'primary', to: '/academic/sections?action=add' },
    ],
    '/fees/payments': [
      { label: 'Record Payment', variant: 'primary', to: '/fees/payments?action=new' },
    ],
  }

  // Find matching actions for current route (exact match first, then prefix)
  const actions = routeActions[path] || Object.entries(routeActions).find(
    ([route]) => path.startsWith(route)
  )?.[1]

  if (!actions || actions.length === 0) return null

  return (
    <div className="flex items-center gap-2">
      {actions.map((action) => (
        <Button
          key={action.label}
          variant={action.variant || 'primary'}
          size="sm"
          onClick={() => navigate(action.to)}
        >
          {action.label}
          {action.shortcut && (
            <kbd className="ml-1.5 hidden sm:inline-flex items-center px-1 py-0.5 rounded bg-white/20 text-[10px] font-medium text-white/80">
              {action.shortcut}
            </kbd>
          )}
        </Button>
      ))}
    </div>
  )
}
