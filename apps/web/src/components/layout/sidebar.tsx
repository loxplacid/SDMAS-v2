import { useState, useCallback } from 'react'
import { NavLink } from 'react-router-dom'
import { cn } from '../../lib/utils'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'
import { useAuth } from '../../api/auth/auth-context'
import { getNavItemsForRole } from '../../types/roles'
import type { NavItem } from '../../types/roles'

export function Sidebar() {
  const { user } = useAuth()
  const navItems = getNavItemsForRole(user?.role || '')

  const [hovered, setHovered] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [mobileClosing, setMobileClosing] = useState(false)
  const collapsed = !hovered

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

  // Keyboard shortcut to toggle mobile sidebar (Ctrl+B / ⌘B)
  useKeyboardShortcut({
    'mod+b': () => {
      // Only toggle mobile sidebar on viewports where the FAB is visible
      if (window.innerWidth >= 1024) return
      if (mobileOpen && !mobileClosing) {
        closeMobile()
      } else if (!mobileOpen) {
        openMobile()
      }
    },
  }, [mobileOpen, mobileClosing, closeMobile, openMobile])

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        className={cn(
          'hidden lg:flex flex-col h-screen flex-shrink-0 z-30',
          'bg-[var(--nav-bg)]',
          'transition-all duration-300 ease-in-out',
          collapsed ? 'w-[var(--nav-collapsed-width)]' : 'w-[var(--nav-width)]'
        )}
      >
        {/* Logo */}
        <div className={cn(
          'flex items-center border-b border-[var(--nav-border)] h-[var(--header-height)] transition-all',
          collapsed ? 'justify-center px-0' : 'px-5'
        )}>
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex items-center justify-center h-8 w-8 rounded-xl bg-[var(--color-brand-accent)] text-white font-bold text-sm flex-shrink-0 shadow-sm">
              S
            </div>
            {!collapsed && (
              <div className="min-w-0 transition-opacity duration-200">
                <p className="text-sm font-bold text-white leading-tight">SDMAS</p>
                <p className="text-[10px] text-[var(--nav-text)] leading-tight">v2.0</p>
              </div>
            )}
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto px-2.5 py-4 space-y-0.5" aria-label="Main navigation">
          {navItems.map((item, idx) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/dashboard'}
              className={({ isActive }) =>
                cn(
                  'group relative flex items-center gap-3 px-2.5 py-2.5 rounded-xl text-sm font-medium',
                  'transition-all motion-reduce:transition-none duration-[var(--motion-fast)] ease-[var(--ease-standard)]',
                  'focus:outline-none focus:ring-1 focus:ring-[var(--color-brand-accent)]',
                  'animate-slide-in-left',
                  isActive
                    ? 'bg-[var(--nav-bg-active)] text-[var(--nav-text-active)]'
                    : 'text-[var(--nav-text)] hover:bg-[var(--nav-bg-hover)] hover:text-[var(--nav-text-hover)]',
                  collapsed && 'justify-center px-0'
                )
              }
              aria-label={item.label}
              title={collapsed ? item.label : undefined}
              style={{ animationDelay: `${idx * 30}ms` }}
            >
              {({ isActive }: { isActive: boolean }) => (
                <>
                  {/* Active indicator bar */}
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
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={item.icon} />
                  </svg>
                  {!collapsed && (
                    <>
                      <span className="truncate">{item.label}</span>
                      {item.badge !== undefined && item.badge > 0 && (
                        <span className="ml-auto flex items-center justify-center h-5 min-w-[20px] px-1 rounded-full bg-[var(--color-brand-accent)] text-[10px] font-bold text-white">
                          {item.badge}
                        </span>
                      )}
                    </>
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* Mobile sidebar */}
      {showMobile && (
        <div className="lg:hidden fixed inset-0 z-40" role="dialog" aria-modal="true">
          <div
            className={cn(
              'fixed inset-0 bg-black/50',
              mobileClosing ? 'animate-fade-out' : 'animate-fade-in'
            )}
            onClick={closeMobile}
          />
          <aside
            className={cn(
              'fixed left-0 top-0 bottom-0 w-[260px] bg-[var(--nav-bg)] z-50',
              mobileClosing ? 'animate-slide-out-left' : 'animate-slide-in-left'
            )}
          >
            <div className="flex items-center justify-between px-5 h-[var(--header-height)] border-b border-[var(--nav-border)]">
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center h-8 w-8 rounded-xl bg-[var(--color-brand-accent)] text-white font-bold text-sm">S</div>
                <div>
                  <p className="text-sm font-bold text-white">SDMAS</p>
                  <p className="text-[10px] text-[var(--nav-text)]">v2.0</p>
                </div>
              </div>
              <button onClick={closeMobile} className="text-[var(--nav-text)] hover:text-white transition-colors">
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <nav className="p-3 space-y-0.5 overflow-y-auto h-[calc(100%-var(--header-height))]">          {navItems.map((item, idx) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/dashboard'}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all animate-fade-in-left',
                  isActive ? 'bg-[var(--nav-bg-active)] text-[var(--nav-text-active)]' : 'text-[var(--nav-text)] hover:bg-[var(--nav-bg-hover)] hover:text-white'
                )
              }
              onClick={closeMobile}
              style={{ animationDelay: `${idx * 40}ms` }}
            >
              <svg className="h-5 w-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={item.icon} />
              </svg>
              {item.label}
            </NavLink>
          ))}
            </nav>
          </aside>
        </div>
      )}

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
