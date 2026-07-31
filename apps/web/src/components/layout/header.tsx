import { useAuth } from '../../api/auth/auth-context'
import { useCampus } from '../../hooks/use-campus'
import { NotificationBell } from '../notifications/notification-bell'
import { ThemeToggle } from '../ui/theme-toggle'
import { WorkspaceSwitcher } from '../ui/workspace-switcher'
import { Tooltip } from '../ui/tooltip'
import { DropdownMenu } from '../ui/dropdown-menu'
import type { DropdownItem } from '../ui/dropdown-menu'
import { Skeleton } from '../ui/skeleton'
import { cn, capitalize } from '../../lib/utils'

import { ROLE_BADGE_COLORS } from '../../types/roles'

function RoleBadge({ role, isPrimary = false }: { role?: string; isPrimary?: boolean }) {
  if (!role) return null
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-semibold uppercase tracking-widest',
        ROLE_BADGE_COLORS[role] || 'bg-[var(--color-surface-hover)] text-[var(--color-text-tertiary)]',
      )}
    >
      {isPrimary && (
        <span className="h-1 w-1 rounded-full bg-current opacity-60" aria-hidden="true" />
      )}
      {capitalize(role)}
    </span>
  )
}

interface HeaderProps {
  onOpenCommandPalette?: () => void
  onOpenSearch?: () => void
  onOpenShortcuts?: () => void
}

export function Header({ onOpenCommandPalette, onOpenSearch, onOpenShortcuts }: HeaderProps) {
  const { user, logout } = useAuth()
  const { campusName, isLoading: campusLoading } = useCampus()

  const userDropdownItems: DropdownItem[] = [
    {
      id: 'profile',
      label: 'Profile',
      icon: (
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
      ),
      onClick: () => { window.location.href = '/profile' },
    },
    { id: 'divider-1', label: '', divider: true },
    {
      id: 'signout',
      label: 'Sign out',
      icon: (
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
        </svg>
      ),
      danger: true,
      onClick: () => logout(),
    },
  ]

  return (
    <header className="h-[var(--header-height)] bg-[var(--color-surface)] border-b border-[var(--color-border)] flex items-center justify-between px-4 lg:px-6 flex-shrink-0 animate-fade-in-down">
      {/* Left */}
      <div className="flex items-center gap-2">
        {/* Mobile nav toggle is handled by the sidebar's FAB */}
      </div>

      {/* Center / Right */}
      <div className="flex items-center gap-1">
        {/* Command Palette Trigger */}
        <button
          onClick={onOpenCommandPalette}
          className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-[var(--color-text-tertiary)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-secondary)] transition-colors border border-[var(--color-border)]"
          aria-label="Open command palette"
        >
          <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <span className="hidden md:inline">Search or jump...</span>
          <kbd className="hidden lg:inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-[var(--color-bg)] text-[10px] font-medium text-[var(--color-text-muted)] border border-[var(--color-border)]">
            <span>⌘K</span>
          </kbd>
        </button>

        {/* Keyboard Shortcuts Hint */}
        <Tooltip content="Keyboard shortcuts (⌘?)">
          <button
            onClick={onOpenShortcuts}
            className="hidden sm:flex items-center justify-center h-7 w-7 rounded-lg text-xs font-semibold text-[var(--color-text-tertiary)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-secondary)] transition-colors border border-[var(--color-border)]"
            aria-label="Keyboard shortcuts"
          >
            ?
          </button>
        </Tooltip>

        <ThemeToggle />

        {/* Workspace Switcher (admin only) */}
        <WorkspaceSwitcher />

        <div className="w-px h-5 bg-[var(--color-border)] mx-1 hidden sm:block" />

        <NotificationBell />

        {/* User Menu via DropdownMenu */}
        <DropdownMenu
          items={userDropdownItems}
          position="bottom-right"
          header={
            <div className="flex items-start gap-3">
              <span className="flex items-center justify-center h-9 w-9 rounded-xl bg-[var(--color-brand-accent)] text-sm font-bold text-white flex-shrink-0 shadow-sm mt-0.5">
                {(user?.display_name || user?.username || '?').charAt(0).toUpperCase()}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-[var(--color-text-primary)] truncate leading-tight">
                  {user?.display_name || user?.username}
                </p>
                {/* Campus name */}
                {campusLoading ? (
                  <Skeleton className="h-3 w-24 mt-1 mb-1.5" />
                ) : campusName ? (
                  <p className="text-[10px] text-[var(--color-text-tertiary)] truncate leading-tight mt-0.5 mb-1 flex items-center gap-1">
                    <span className="h-1 w-1 rounded-full bg-current opacity-60 shrink-0" aria-hidden="true" />
                    {campusName}
                  </p>
                ) : null}
                <p className="text-[10px] text-[var(--color-text-tertiary)] truncate mb-2">
                  {user?.email}
                </p>
                {/* Role badges */}
                <div className="flex flex-wrap gap-1">
                  <RoleBadge role={user?.role} isPrimary />
                  {(user?.roles || [])
                    .filter((r) => r !== user?.role)
                    .map((r) => (
                      <RoleBadge key={r} role={r} />
                    ))}
                </div>
              </div>
            </div>
          }
          trigger={
            <button className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm transition-colors hover:bg-[var(--color-surface-hover)] focus:outline-none focus:ring-2 focus:ring-[var(--color-brand-accent)]">
              <span className="flex items-center justify-center h-7 w-7 rounded-full bg-[var(--color-brand-accent)] text-[11px] font-bold text-white flex-shrink-0">
                {(user?.display_name || user?.username || '?').charAt(0).toUpperCase()}
              </span>
              <span className="hidden sm:inline text-sm font-medium text-[var(--color-text-primary)] max-w-[120px] truncate">
                {user?.display_name || user?.username}
              </span>
              <svg className="hidden sm:block h-3.5 w-3.5 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          }
        />
      </div>
    </header>
  )
}
