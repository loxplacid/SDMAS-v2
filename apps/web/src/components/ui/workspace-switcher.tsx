import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../api/auth/auth-context'
import { ROLE_CONFIG } from '../../types/roles'
import type { UserRole } from '../../types/roles'
import { cn } from '../../lib/utils'

const WORKSPACES: { role: UserRole; label: string }[] = [
  { role: 'admin', label: 'Admin' },
  { role: 'teacher', label: 'Teacher' },
  { role: 'student', label: 'Student' },
  { role: 'parent', label: 'Parent' },
]

// Derive badge color from ROLE_CONFIG's color class
function roleBadgeBg(role: UserRole): string {
  return ROLE_CONFIG[role].color
}

export function WorkspaceSwitcher() {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const [closing, setClosing] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  const close = useCallback(() => {
    if (open) {
      setClosing(true)
      setTimeout(() => {
        setClosing(false)
        setOpen(false)
      }, 120)
    }
  }, [open])

  const toggle = useCallback(() => {
    if (open) {
      close()
    } else {
      setOpen(true)
      setClosing(false)
    }
  }, [open, close])

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        close()
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [close])

  // Only show for admin users
  if (user?.role !== 'admin') return null

  const show = open
  const currentRole = (user.role as UserRole) || 'admin'

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={toggle}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-[var(--color-text-tertiary)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-secondary)] transition-colors border border-[var(--color-border)]"
        aria-label="Switch workspace"
        aria-expanded={open}
        aria-haspopup="true"
        title="Preview workspaces"
      >
        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
        </svg>
        <span className="hidden sm:inline">Workspace</span>
        <svg className={cn(
          'h-3 w-3 transition-transform duration-150',
          open && 'rotate-180'
        )} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {show && (
        <div
          className={cn(
            'absolute right-0 mt-1.5 w-48 bg-[var(--color-surface)] rounded-2xl shadow-xl border border-[var(--color-border)] py-1.5 z-50 origin-top-right',
            closing ? 'animate-fade-out-scale' : 'animate-fade-in-scale'
          )}
          style={{ animationDuration: 'var(--motion-fast)', animationTimingFunction: 'var(--ease-spring)' }}
          role="menu"
        >
          <div className="px-4 py-2 border-b border-[var(--color-border)]">
            <p className="text-xs font-semibold text-[var(--color-text-primary)]">Preview as</p>
            <p className="text-[10px] text-[var(--color-text-tertiary)]">See the app from different roles</p>
          </div>
          <div className="py-1">
            {WORKSPACES.map((ws) => {
              const config = ROLE_CONFIG[ws.role]
              const isActive = ws.role === currentRole
              return (
                <button
                  key={ws.role}
                  onClick={() => {
                    close()
                    navigate(config.homeRoute)
                  }}
                  className={cn(
                    'flex items-center gap-3 w-full text-left px-4 py-2.5 text-sm transition-colors',
                    isActive
                      ? 'text-[var(--color-brand-accent)] bg-[var(--color-brand-accent-subtle)]'
                      : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]'
                  )}
                  role="menuitem"
                >
                  <span className={cn(
                    'flex items-center justify-center h-6 w-6 rounded-lg text-[10px] font-bold text-white flex-shrink-0',
                    roleBadgeBg(ws.role)
                  )}>
                    {ws.label.charAt(0)}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{config.label}</p>
                    <p className="text-[10px] text-[var(--color-text-tertiary)] truncate">{config.description}</p>
                  </div>
                  {isActive && (
                    <svg className="h-3.5 w-3.5 flex-shrink-0 text-[var(--color-brand-accent)]" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z" />
                    </svg>
                  )}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
