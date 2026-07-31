import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../api/auth/auth-context'
import { ROLE_CONFIG } from '../../types/roles'
import type { UserRole } from '../../types/roles'
import { DropdownMenu } from './dropdown-menu'
import type { DropdownItem } from './dropdown-menu'
import { Tooltip } from './tooltip'
import { cn } from '../../lib/utils'

const WORKSPACES: { role: UserRole; label: string }[] = [
  { role: 'admin', label: 'Admin' },
  { role: 'teacher', label: 'Teacher' },
  { role: 'student', label: 'Student' },
  { role: 'parent', label: 'Parent' },
]

function roleBadgeBg(role: UserRole): string {
  return ROLE_CONFIG[role].color
}

export function WorkspaceSwitcher() {
  const { user } = useAuth()
  const navigate = useNavigate()

  // Only show for admin users
  if (user?.role !== 'admin') return null

  const currentRole = (user.role as UserRole) || 'admin'

  const items: DropdownItem[] = WORKSPACES.map((ws) => {
    const config = ROLE_CONFIG[ws.role]
    const isActive = ws.role === currentRole
    return {
      id: ws.role,
      label: config.label,
      icon: (
        <span className={cn(
          'flex items-center justify-center h-5 w-5 rounded-md text-[8px] font-bold text-white flex-shrink-0',
          roleBadgeBg(ws.role),
        )}>
          {ws.label.charAt(0)}
        </span>
      ),
      onClick: () => navigate(config.homeRoute),
    }
  })

  return (
    <DropdownMenu
      items={items}
      position="bottom-right"
      header={
        <div>
          <p className="text-xs font-semibold text-[var(--color-text-primary)]">Preview as</p>
          <p className="text-[10px] text-[var(--color-text-tertiary)]">See the app from different roles</p>
        </div>
      }
      trigger={
        <Tooltip content="Preview workspaces">
          <button className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-[var(--color-text-tertiary)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-secondary)] transition-colors border border-[var(--color-border)]" aria-label="Switch workspace">
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
            </svg>
            <span className="hidden sm:inline">Workspace</span>
            <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </Tooltip>
      }
    />
  )
}
