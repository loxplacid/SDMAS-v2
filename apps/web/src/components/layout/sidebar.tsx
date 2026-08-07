import { useState, useCallback, type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { cn, capitalize } from '../../lib/utils'
import { useMove } from '../../lib/motion'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'
import { useAuth } from '../../api/auth/auth-context'
import { useCampus } from '../../hooks/use-campus'
import { getNavSectionsForRole, ROLE_BADGE_COLORS } from '../../types/roles'
import type { NavItem, NavSection } from '../../types/roles'
import { Drawer } from '../ui/drawer'
import { Skeleton } from '../ui/skeleton'

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
 * column at `fast` (120ms) as the rail collapses. Rendered only while the
 * rail is expanded, so each expand replays the enter choreography; on
 * collapse the labels unmount and the shrinking rail clips them out.
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
}

export function Sidebar({ collapsed: controlledCollapsed, onToggle }: SidebarProps) {
  const { user } = useAuth()
  const { campusName, isLoading: campusLoading } = useCampus()
  const navSections = getNavSectionsForRole(user?.role || '')

  const [hovered, setHovered] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [mobileClosing, setMobileClosing] = useState(false)
  const collapsed = controlledCollapsed !== undefined ? controlledCollapsed : !hovered

  const closeMobile = useCallback(() => {
    if (mobileOpen) {
      setMobileClosing(true)
      setTimeout(() => {
        setMobileClosing(false)
        setMobileOpen(false)
      }, 200)
    }
  }, [mobileOpen])

  const openMobile = useCallback(() => {
    setMobileOpen(true)
    setMobileClosing(false)
  }, [])

  const showMobile = mobileOpen

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
          'hidden lg:flex flex-col h-screen flex-shrink-0 z-30 overflow-hidden',
          'bg-[var(--nav-bg)]',
          // Collapse/expand is an E/W rail move at `slow` (260ms, spec §6.2):
          // enter curve on expand, mirrored (accelerate) on collapse. Width
          // only — labels and icons animate via transform/opacity below.
          // (Deviation from the spec's FLIP-the-content-column: a scale-FLIP
          // of the data pages would distort table text; the width move is the
          // pattern Linear/Notion use and stays composited.)
          'transition-[width] duration-[var(--motion-slow)]',
          collapsed
            ? 'w-[var(--nav-collapsed-width)] ease-[var(--ease-emphasized-accelerate)]'
            : 'w-[var(--nav-width)] ease-[var(--ease-emphasized-decelerate)]'
        )}
      >
        {/* Logo + Pin */}
        <div className={cn(
          'flex items-center border-b border-[var(--nav-border)] h-[var(--header-height)]',
          'transition-[padding] duration-[var(--motion-fast)] ease-[var(--ease-standard)]',
          collapsed ? 'justify-center px-0' : 'px-5'
        )}>
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex items-center justify-center h-8 w-8 rounded-xl bg-[var(--color-brand-accent)] text-white font-bold text-sm flex-shrink-0 shadow-sm">
              S
            </div>
            {!collapsed && (
              <RailLabel className="min-w-0">
                <p className="text-sm font-bold text-white leading-tight">SDMAS</p>
                <p className="text-[10px] text-[var(--nav-text)] leading-tight">v2.0</p>
              </RailLabel>
            )}
          </div>
        </div>

        {/* Nav sections */}
        <nav className="flex-1 overflow-y-auto px-2.5 py-4" aria-label="Main navigation">
          {!collapsed && (
            <RailLabel className="mb-3 px-2">
              <button
                onClick={onToggle}
                className="flex items-center gap-2 text-[10px] font-medium text-[var(--nav-text)]/40 hover:text-[var(--nav-text)]/70 motion-safe:transition-colors motion-safe:duration-[var(--motion-fast)] uppercase tracking-wider"
              >
                <svg className={cn('h-3 w-3 motion-safe:transition-transform motion-safe:duration-[var(--motion-base)]', collapsed && 'rotate-180')} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
                </svg>
                Collapse
              </button>
            </RailLabel>
          )}
          {navSections.map((section, si) => (
            <div key={section.label} className="mb-3 last:mb-0">
              {!collapsed && (
                <RailLabel className="px-2.5 pb-1 text-[10px] font-semibold uppercase tracking-widest text-[var(--nav-text)]/30">
                  {section.label}
                </RailLabel>
              )}
              <div className="space-y-0.5">
                {section.items.map((item, idx) => (
                  <SidebarNavItem key={item.to} idx={idx}>
                    <NavLink
                      to={item.to}
                      end={item.to === '/dashboard'}
                      className={({ isActive }) =>
                        cn(
                          'group relative flex items-center gap-3 px-2.5 py-2.5 rounded-xl text-sm font-medium',
                          'transition-all motion-reduce:transition-none duration-[var(--motion-fast)] ease-[var(--ease-standard)]',
                          'focus:outline-none focus:ring-1 focus:ring-[var(--color-brand-accent)]',
                          isActive
                            ? 'bg-[var(--nav-bg-active)] text-[var(--nav-text-active)]'
                            : 'text-[var(--nav-text)] hover:bg-[var(--nav-bg-hover)] hover:text-[var(--nav-text-hover)]',
                          collapsed && 'justify-center px-0'
                        )
                      }
                      aria-label={item.label}
                      title={collapsed ? item.label : undefined}
                    >
                      {({ isActive }: { isActive: boolean }) => (
                        <>
                          {isActive && (
                            <span
                              className={cn(
                                'absolute left-0 top-1/2 -translate-y-1/2 h-5 w-0.5 rounded-full bg-[var(--color-brand-accent)]',
                                'animate-active-indicator',
                                collapsed && 'left-0'
                              )}
                            />
                          )}
                          <svg
                            className={cn(
                              'flex-shrink-0 transition-transform motion-reduce:transition-none duration-[var(--motion-fast)]',
                              'group-hover:scale-110 motion-reduce:group-hover:scale-100'
                            )}
                            style={{ width: collapsed ? 20 : 18, height: collapsed ? 20 : 18 }}
                            fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={item.icon} />
                          </svg>
                          {!collapsed && (
                            <RailLabel className="flex-1 min-w-0 flex items-center gap-3">
                              <span className="truncate min-w-0">{item.label}</span>
                              {item.badge !== undefined && item.badge > 0 && (
                                <span className="ml-auto flex items-center justify-center h-5 min-w-[20px] px-1 rounded-full bg-[var(--color-brand-accent)] text-[10px] font-bold text-white">
                                  {item.badge}
                                </span>
                              )}
                            </RailLabel>
                          )}
                        </>
                      )}
                    </NavLink>
                  </SidebarNavItem>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* User section at bottom */}
        <div
          className={cn(
            'flex-shrink-0 border-t border-[var(--nav-border)] transition-[padding] motion-safe:duration-[var(--motion-base)] motion-safe:ease-[var(--ease-standard)]',
            collapsed ? 'px-2 py-3' : 'px-4 py-3'
          )}
        >
          <div
            className={cn(
              'flex items-center rounded-xl transition-colors motion-safe:duration-[var(--motion-fast)]',
              'hover:bg-[var(--nav-bg-hover)]',
              collapsed ? 'justify-center' : 'gap-2.5 px-2 py-1.5',
            )}
          >
            <span
              className={cn(
                'flex items-center justify-center rounded-xl text-white font-bold flex-shrink-0',
                collapsed ? 'h-8 w-8 text-xs' : 'h-8 w-8 text-sm',
                collapsed && user?.role && ROLE_BADGE_COLORS[user.role]
                  ? 'bg-[var(--color-brand-accent)] ring-2 ring-[var(--color-brand-accent)] ring-offset-1 ring-offset-[var(--nav-bg)]'
                  : 'bg-[var(--color-brand-accent)]',
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

      {/* Mobile sidebar via Drawer with navy background */}
      <Drawer
        open={showMobile}
        onClose={closeMobile}
        title="SDMAS v2.0"
        side="left"
        size="sm"
        panelClassName="bg-[var(--nav-bg)]"
        headerClassName="text-white"
      >
        {/* Mobile nav + user section */}
        {/* The Drawer's body handles scrolling (flex-1 overflow-y-auto),
            so nav and user section scroll together naturally. */}
        {/* Offset the Drawer's px-6 body padding to keep mobile nav items
            flush with the same ~10px horizontal margin as the desktop sidebar. */}
        <nav className="space-y-0.5 -mx-4">
          {navSections.map((section) =>
            section.items.map((item, idx) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/dashboard'}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium transition-all animate-fade-in-left',
                    isActive
                      ? 'bg-[var(--nav-bg-active)] text-[var(--nav-text-active)]'
                      : 'text-[var(--nav-text)] hover:bg-[var(--nav-bg-hover)] hover:text-white'
                  )
                }
                onClick={closeMobile}
                style={{ animationDelay: `${idx * 40}ms` }}
              >
                <svg className="h-5 w-5 flex-shrink-0 text-[var(--nav-icon)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={item.icon} />
                </svg>
                {item.label}
              </NavLink>
            ))
          )}
        </nav>

        {/* Mobile user section */}
        <div className="mt-6 pt-4 border-t border-[var(--nav-border)] -mx-4 px-4">
          <div className="flex items-center gap-3 rounded-xl transition-colors motion-safe:duration-[var(--motion-fast)] hover:bg-[var(--nav-bg-hover)] -mx-1 px-2 py-2">
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

      {/* Mobile hamburger */}
      <button
        className={cn(
          'lg:hidden fixed bottom-6 right-6 z-30 flex items-center justify-center h-12 w-12 rounded-full bg-[var(--color-brand-accent)] text-white shadow-lg hover:bg-[var(--color-brand-accent-hover)] transition-all',
          'hover:scale-105 active:scale-95 motion-reduce:hover:scale-100 motion-reduce:active:scale-100',
          'animate-fade-in-scale'
        )}
        style={{ animationDelay: '400ms' }}
        onClick={openMobile}
        aria-label="Open menu"
      >
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>
    </>
  )
}
