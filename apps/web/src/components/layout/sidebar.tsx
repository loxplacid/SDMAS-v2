import { useState, useCallback, type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { cn, capitalize } from '../../lib/utils'
import { useMove, SharedElement } from '../../lib/motion'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'
import { useAuth } from '../../api/auth/auth-context'
import { useCampus } from '../../hooks/use-campus'
import { getNavSectionsForRole, ROLE_BADGE_COLORS } from '../../types/roles'
import type { NavItem, NavSection } from '../../types/roles'
import { Drawer } from '../ui/drawer'
import { Skeleton } from '../ui/skeleton'
import { Tooltip } from '../ui/tooltip'

/**
 * Shared identity for the active-route indicator (P8 §4, §12). One
 * indicator renders inside whichever item is active; Motion's shared-layout
 * projection morphs it between positions when the route changes — the
 * indicator *travels* rather than appearing/disappearing.
 */
const ACTIVE_INDICATOR_ID = 'sidebar-active-indicator'

function SidebarRoleBadge({ role }: { role?: string }) {
  if (!role) return null
  return (
    <span
      className={cn(
        'inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-semibold uppercase tracking-widest',
        ROLE_BADGE_COLORS[role] || 'bg-[var(--color-surface-hover)] text-[var(--color-text-tertiary)]',
      )}
    >
      {capitalize(role)}
    </span>
  )
}

/**
 * Rail label (spec §6.2): labels cross-fade + slide 4px out of the icon
 * column at `fast` (120ms) as the rail collapses.
 */
function RailLabel({ children, className }: { children: ReactNode; className?: string }) {
  const { ref, style } = useMove(
    { verb: 'slide', direction: 'W', distance: 'D2', importance: 'I1' },
    { animateOnMount: true }
  )
  return (
    <div ref={ref} style={style} className={className}>
      {children}
    </div>
  )
}

/**
 * Nav item entry (spec §6.2): items cascade in from East with a 20ms
 * stagger in reading order (§4.3) at `fast` duration.
 */
function SidebarNavItem({ idx, children }: { idx: number; children: ReactNode }) {
  const { ref, style } = useMove(
    { verb: 'slide', direction: 'E', distance: 'D2', importance: 'I1' },
    { animateOnMount: true, staggerIndex: idx }
  )
  return (
    <div ref={ref} style={style}>
      {children}
    </div>
  )
}

interface SidebarProps {
  collapsed?: boolean
  onToggle?: () => void
  mobileOpen?: boolean
  onMobileClose?: () => void
  onMobileOpen?: () => void
}

export function Sidebar({
  collapsed: controlledCollapsed,
  onToggle,
  mobileOpen: controlledMobileOpen,
  onMobileClose,
  onMobileOpen,
}: SidebarProps) {
  const { user } = useAuth()
  const { campusName, isLoading: campusLoading } = useCampus()
  const navSections = getNavSectionsForRole(user?.role || '')

  const [hovered, setHovered] = useState(false)
  const [internalMobileOpen, setInternalMobileOpen] = useState(false)
  const [mobileClosing, setMobileClosing] = useState(false)

  const collapsed = controlledCollapsed !== undefined ? controlledCollapsed : !hovered

  // Mobile open state — controlled from header or internal
  const mobileOpen = controlledMobileOpen !== undefined ? controlledMobileOpen : internalMobileOpen

  const closeMobile = useCallback(() => {
    if (mobileOpen) {
      setMobileClosing(true)
      setTimeout(() => {
        setMobileClosing(false)
        if (onMobileClose) {
          onMobileClose()
        } else {
          setInternalMobileOpen(false)
        }
      }, 200)
    }
  }, [mobileOpen, onMobileClose])

  const openMobile = useCallback(() => {
    if (onMobileOpen) {
      onMobileOpen()
    } else {
      setInternalMobileOpen(true)
      setMobileClosing(false)
    }
  }, [onMobileOpen])

  // Keyboard shortcut to toggle sidebar (⌘B / Ctrl+B)
  useKeyboardShortcut({
    'mod+b': () => {
      if (window.innerWidth >= 1024) {
        onToggle?.()
      } else {
        if (mobileOpen && !mobileClosing) closeMobile()
        else if (!mobileOpen) openMobile()
      }
    },
  }, [mobileOpen, mobileClosing, closeMobile, openMobile, onToggle])

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        className={cn(
          'hidden lg:flex flex-col h-screen flex-shrink-0 z-[var(--z-nav)] overflow-visible',
          'bg-[var(--nav-bg)]',
          'transition-[width] duration-[var(--motion-slow)]',
          collapsed
            ? 'w-[var(--nav-collapsed-width)] ease-[var(--ease-emphasized-accelerate)]'
            : 'w-[var(--nav-width)] ease-[var(--ease-emphasized-decelerate)]'
        )}
      >
        {/* Logo + wordmark */}
        <div className={cn(
          'flex items-center border-b border-[var(--nav-border)] h-[var(--header-height)] flex-shrink-0',
          'transition-[padding] duration-[var(--motion-fast)] ease-[var(--ease-standard)]',
          collapsed ? 'justify-center px-0' : 'px-4'
        )}>
          <div className="flex items-center gap-3 min-w-0">
            {collapsed ? (
              onToggle ? (
                <Tooltip content="Expand sidebar" position="right" delay={300} portal>
                  <button
                    type="button"
                    onClick={onToggle}
                    aria-label="Expand sidebar"
                    className="flex items-center justify-center h-8 w-8 rounded-xl bg-[var(--color-brand-accent)] text-white font-bold text-sm flex-shrink-0 shadow-sm hover:bg-[var(--color-brand-accent-hover)] motion-safe:transition-colors motion-safe:duration-[var(--motion-fast)] focus:outline-none focus:ring-1 focus:ring-[var(--color-brand-accent)]"
                  >
                    S
                  </button>
                </Tooltip>
              ) : (
                <div className="flex items-center justify-center h-8 w-8 rounded-xl bg-[var(--color-brand-accent)] text-white font-bold text-sm flex-shrink-0 shadow-sm">
                  S
                </div>
              )
            ) : (
              <>
                <div className="flex items-center justify-center h-8 w-8 rounded-xl bg-[var(--color-brand-accent)] text-white font-bold text-sm flex-shrink-0 shadow-sm">
                  S
                </div>
                <RailLabel className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm font-bold text-white leading-tight tracking-tight">SDMAS</p>
                      <p className="text-[10px] text-[var(--nav-text)] leading-tight">v2.0</p>
                    </div>
                    {onToggle && (
                      <button
                        onClick={onToggle}
                        aria-label="Collapse sidebar"
                        className="flex items-center justify-center h-6 w-6 rounded-lg text-[var(--nav-text)]/40 hover:text-[var(--nav-text)]/80 hover:bg-white/5 motion-safe:transition-colors motion-safe:duration-[var(--motion-fast)] focus:outline-none flex-shrink-0"
                      >
                        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
                        </svg>
                      </button>
                    )}
                  </div>
                </RailLabel>
              </>
            )}
          </div>
        </div>

        {/* Nav sections */}
        <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-0.5" aria-label="Main navigation">
          {navSections.map((section, si) => (
            <NavSection
              key={section.label}
              section={section}
              collapsed={collapsed}
              sectionIndex={si}
            />
          ))}
        </nav>

        {/* User section at bottom */}
        <div
          className={cn(
            'flex-shrink-0 border-t border-[var(--nav-border)]',
            'transition-[padding] motion-safe:duration-[var(--motion-base)] motion-safe:ease-[var(--ease-standard)]',
            collapsed ? 'px-2 py-3' : 'px-3 py-3'
          )}
        >
          <div
            className={cn(
              'flex items-center rounded-xl transition-colors motion-safe:duration-[var(--motion-fast)]',
              'hover:bg-[var(--nav-bg-hover)] cursor-default',
              collapsed ? 'justify-center p-1.5' : 'gap-2.5 px-2 py-1.5',
            )}
          >
            <span
              className={cn(
                'flex items-center justify-center rounded-xl text-white font-bold flex-shrink-0',
                collapsed ? 'h-8 w-8 text-xs' : 'h-8 w-8 text-sm',
                'bg-[var(--color-brand-accent)]',
              )}
            >
              {(user?.display_name || user?.username || '?').charAt(0).toUpperCase()}
            </span>

            {!collapsed && (
              <RailLabel className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-white truncate leading-tight">
                  {user?.display_name || user?.username}
                </p>
                {campusLoading ? (
                  <Skeleton className="h-3 w-28 mt-1.5" />
                ) : campusName ? (
                  <p className="text-[10px] text-[var(--nav-text)] truncate leading-tight mt-0.5 flex items-center gap-1">
                    <span className="h-1 w-1 rounded-full bg-current opacity-60 shrink-0" aria-hidden="true" />
                    {campusName}
                  </p>
                ) : null}
                <div className="flex flex-wrap gap-1 mt-1">
                  <SidebarRoleBadge role={user?.role} />
                  {(user?.roles || [])
                    .filter((r) => r !== user?.role)
                    .map((r) => (
                      <SidebarRoleBadge key={r} role={r} />
                    ))}
                </div>
              </RailLabel>
            )}
          </div>
        </div>
      </aside>

      {/* Mobile sidebar via Drawer */}
      <Drawer
        open={mobileOpen}
        onClose={closeMobile}
        title="SDMAS v2.0"
        side="left"
        size="sm"
        panelClassName="bg-[var(--nav-bg)]"
        headerClassName="text-white"
      >
        <nav className="space-y-0.5 -mx-4">
          {navSections.map((section) => (
            <div key={section.label} className="mb-1">
              <p className="px-4 pt-3 pb-1 text-[9px] font-semibold uppercase tracking-widest text-[var(--nav-text)]/30">
                {section.label}
              </p>
              {section.items.map((item, idx) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/dashboard'}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center px-4 py-2.5 rounded-xl text-sm font-medium transition-all animate-fade-in-left',
                      isActive
                        ? 'bg-[var(--nav-bg-active)] text-[var(--nav-text-active)]'
                        : 'text-[var(--nav-text)] hover:bg-[var(--nav-bg-hover)] hover:text-white'
                    )
                  }
                  onClick={closeMobile}
                  style={{ animationDelay: `${idx * 30}ms` }}
                >
                  <span className="flex items-center gap-3 min-w-0 flex-1 motion-safe:active:scale-[0.98]">
                    <svg className="h-4.5 w-4.5 flex-shrink-0 text-[var(--nav-icon)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={item.icon} />
                    </svg>
                    {item.label}
                  </span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        {/* Mobile user section */}
        <div className="mt-4 pt-4 border-t border-[var(--nav-border)] -mx-4 px-4">
          <div className="flex items-center gap-3 rounded-xl -mx-1 px-2 py-2">
            <span className="flex items-center justify-center h-9 w-9 rounded-xl bg-[var(--color-brand-accent)] text-white font-bold text-sm flex-shrink-0 shadow-sm">
              {(user?.display_name || user?.username || '?').charAt(0).toUpperCase()}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-white truncate leading-tight">
                {user?.display_name || user?.username}
              </p>
              {campusLoading ? (
                <Skeleton className="h-3 w-28 mt-1.5" />
              ) : campusName ? (
                <p className="text-[10px] text-[var(--nav-text)] truncate leading-tight mt-0.5 flex items-center gap-1">
                  <span className="h-1 w-1 rounded-full bg-current opacity-60 shrink-0" aria-hidden="true" />
                  {campusName}
                </p>
              ) : null}
              <p className="text-[10px] text-[var(--nav-text)] truncate leading-tight mt-0.5">
                {user?.email}
              </p>
              <div className="flex flex-wrap gap-1 mt-1.5">
                <SidebarRoleBadge role={user?.role} />
                {(user?.roles || [])
                  .filter((r) => r !== user?.role)
                  .map((r) => (
                    <SidebarRoleBadge key={r} role={r} />
                  ))}
              </div>
            </div>
          </div>
        </div>
      </Drawer>
    </>
  )
}

// ── NavSection ────────────────────────────────────────────────────────────────

function NavSection({
  section,
  collapsed,
  sectionIndex,
}: {
  section: NavSection
  collapsed: boolean
  sectionIndex: number
}) {
  return (
    <div className="mb-1 last:mb-0">
      {!collapsed && (
        <p className="px-2.5 pt-3 pb-1 text-[9px] font-semibold uppercase tracking-widest text-[var(--nav-text)]/30 first:pt-1">
          {section.label}
        </p>
      )}
      {collapsed && sectionIndex > 0 && (
        <div className="mx-3 my-2 border-t border-[var(--nav-border)]" aria-hidden="true" />
      )}
      <div className="space-y-0.5">
        {section.items.map((item, idx) => (
          <SidebarNavItem key={item.to} idx={idx}>
            <NavItemLink item={item} collapsed={collapsed} />
          </SidebarNavItem>
        ))}
      </div>
    </div>
  )
}

// ── NavItemLink ───────────────────────────────────────────────────────────────

function NavItemLink({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  return (
    <NavLink
      to={item.to}
      end={item.to === '/dashboard'}
      className={({ isActive }) =>
        cn(
          'group relative flex items-center gap-3 rounded-xl text-sm font-medium',
          'motion-safe:active:scale-[0.98]',
          'transition-all motion-reduce:transition-none duration-[var(--motion-fast)] ease-[var(--ease-standard)]',
          'focus:outline-none focus:ring-1 focus:ring-[var(--color-brand-accent)]',
          isActive
            ? 'bg-[var(--nav-bg-active)] text-[var(--nav-text-active)]'
            : 'text-[var(--nav-text)] hover:bg-[var(--nav-bg-hover)] hover:text-[var(--nav-text-hover)]',
          collapsed ? 'justify-center px-0 py-2.5 mx-1' : 'px-2.5 py-2'
        )
      }
      aria-label={item.label}
    >
      {({ isActive }: { isActive: boolean }) => (
        <>
          {isActive && (
            <SharedElement
              layoutId={ACTIVE_INDICATOR_ID}
              aria-hidden="true"
              data-sidebar-indicator=""
              className="absolute left-0 top-1/2 -mt-2.5 h-5 w-0.5 rounded-full bg-[var(--color-brand-accent)]"
            />
          )}
          {collapsed ? (
            <Tooltip
              content={item.label}
              position="right"
              delay={300}
              portal
              className="flex-shrink-0"
            >
              <svg
                className={cn(
                  'flex-shrink-0 transition-transform motion-reduce:transition-none duration-[var(--motion-fast)]',
                  'group-hover:scale-110 motion-reduce:group-hover:scale-100'
                )}
                style={{ width: 20, height: 20 }}
                fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={item.icon} />
              </svg>
            </Tooltip>
          ) : (
            <>
              <svg
                className={cn(
                  'flex-shrink-0 transition-transform motion-reduce:transition-none duration-[var(--motion-fast)]',
                  'group-hover:scale-110 motion-reduce:group-hover:scale-100'
                )}
                style={{ width: 16, height: 16 }}
                fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={item.icon} />
              </svg>
              <RailLabel className="flex-1 min-w-0 flex items-center gap-3">
                <span className="truncate min-w-0 text-[13px]">{item.label}</span>
                {item.badge !== undefined && item.badge > 0 && (
                  <span className="ml-auto flex items-center justify-center h-4.5 min-w-[18px] px-1 rounded-full bg-[var(--color-brand-accent)] text-[9px] font-bold text-white">
                    {item.badge}
                  </span>
                )}
              </RailLabel>
            </>
          )}
        </>
      )}
    </NavLink>
  )
}
