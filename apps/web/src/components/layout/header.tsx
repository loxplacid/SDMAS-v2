import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../api/auth/auth-context'
import { useCampus } from '../../hooks/use-campus'
import { NotificationBell } from '../notifications/notification-bell'
import { OrganizationContext } from './organization-context'
import { ThemeToggle } from '../ui/theme-toggle'
import { WorkspaceSwitcher } from '../ui/workspace-switcher'
import { Tooltip } from '../ui/tooltip'
import { DropdownMenu } from '../ui/dropdown-menu'
import type { DropdownItem } from '../ui/dropdown-menu'
import { Skeleton } from '../ui/skeleton'
import { cn, capitalize } from '../../lib/utils'
import { BreadcrumbBar } from '../ui/breadcrumb-bar'
import { ContextualPageActions } from './contextual-actions'
import { QuickCreate } from './quick-create'
import { ROLE_BADGE_COLORS } from '../../types/roles'

/** Rendered only when VITE_DEMO_MODE=1 */
const IS_DEMO = import.meta.env.VITE_DEMO_MODE === '1'

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
  onOpenMobileNav?: () => void
}

export function Header({
  onOpenCommandPalette,
  onOpenSearch,
  onOpenShortcuts,
  onOpenMobileNav,
}: HeaderProps) {
  const { user, logout } = useAuth()
  const { campusName, isLoading: campusLoading } = useCampus()
  const navigate = useNavigate()

  const userDropdownItems: DropdownItem[] = [
    {
      id: 'profile',
      label: 'Profile',
      icon: (
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
      ),
      onClick: () => navigate('/profile'),
    },
    { id: 'divider-1', label: '', divider: true },
    {
      id: 'shortcuts',
      label: 'Keyboard shortcuts',
      icon: (
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 6h12a2 2 0 012 2v8a2 2 0 01-2 2H6a2 2 0 01-2-2V8a2 2 0 012-2zm1 4h.01M9.5 10h.01M12 10h.01M14.5 10h.01M17 10h.01M8 14h8" />
        </svg>
      ),
      onClick: () => onOpenShortcuts?.(),
    },
    { id: 'divider-2', label: '', divider: true },
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
    <header className="h-[var(--header-height)] bg-[var(--color-surface)] border-b border-[var(--color-border)] flex items-center justify-between px-3 lg:px-5 flex-shrink-0 gap-2">

      {/* ── Left ── */}
      <div className="flex items-center gap-2 min-w-0">
        {/* Mobile hamburger — only visible below lg */}
        <button
          onClick={onOpenMobileNav}
          className="lg:hidden flex items-center justify-center h-8 w-8 rounded-lg text-[var(--color-text-tertiary)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)] transition-colors flex-shrink-0"
          aria-label="Open navigation"
        >
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        {/* Demo badge */}
        {IS_DEMO && (
          <span
            className="hidden sm:inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-amber-500/15 text-amber-600 dark:text-amber-400 text-[9px] font-bold uppercase tracking-widest border border-amber-500/30 flex-shrink-0"
            title="This environment contains synthetic demonstration data"
          >
            <span className="h-1 w-1 rounded-full bg-current animate-pulse-soft" aria-hidden="true" />
            Demo
          </span>
        )}

        {/* Breadcrumbs — hidden on mobile */}
        <div className="hidden sm:flex items-center min-w-0">
          <BreadcrumbBar variant="header" />
        </div>
      </div>

      {/* ── Right ── */}
      <div className="flex items-center gap-1 flex-shrink-0">

        {/* Global search trigger — premium search bar feel */}
        <button
          onClick={onOpenCommandPalette}
          className={cn(
            'hidden sm:flex items-center gap-2 rounded-lg border border-[var(--color-border)]',
            'bg-[var(--color-bg)] hover:bg-[var(--color-surface-hover)]',
            'text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]',
            'transition-colors duration-[var(--motion-fast)]',
            'px-3 py-1.5 h-8',
          )}
          aria-label="Search or jump to..."
        >
          <svg className="h-3.5 w-3.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <span className="hidden md:inline text-xs">Search or jump...</span>
          <kbd className="hidden lg:inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-[var(--color-surface)] text-[10px] font-medium text-[var(--color-text-muted)] border border-[var(--color-border)] ml-1">
            ⌘K
          </kbd>
        </button>

        {/* Mobile search icon */}
        <button
          onClick={onOpenCommandPalette}
          className="sm:hidden flex items-center justify-center h-8 w-8 rounded-lg text-[var(--color-text-tertiary)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)] transition-colors"
          aria-label="Search"
        >
          <svg className="h-4.5 w-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </button>

        {/* Contextual page actions — desktop only */}
        <div className="hidden lg:flex items-center">
          <ContextualPageActions />
        </div>

        {/* Organization context — desktop only */}
        <div className="hidden xl:block">
          <OrganizationContext />
        </div>

        {/* Quick create */}
        <div className="hidden sm:block">
          <QuickCreate />
        </div>

        {/* Keyboard shortcuts hint */}
        <Tooltip content="Keyboard shortcuts (?)">
          <button
            onClick={onOpenShortcuts}
            className="hidden sm:flex items-center justify-center h-7 w-7 rounded-lg text-xs font-semibold text-[var(--color-text-tertiary)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-secondary)] transition-colors border border-[var(--color-border)]"
            aria-label="Keyboard shortcuts"
          >
            ?
          </button>
        </Tooltip>

        <ThemeToggle />

        {/* Workspace switcher (admin only) */}
        <WorkspaceSwitcher />

        <div className="w-px h-5 bg-[var(--color-border)] mx-0.5 hidden sm:block" />

        <NotificationBell />

        {/* User menu */}
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
              <span className="hidden sm:inline text-sm font-medium text-[var(--color-text-primary)] max-w-[100px] truncate">
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
