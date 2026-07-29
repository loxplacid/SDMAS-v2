import { useState, useCallback } from 'react'
import { NavLink } from 'react-router-dom'
import { cn } from '../../lib/utils'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'

interface NavItem {
  to: string
  label: string
  icon: string
  badge?: number
}

const navItems: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
  { to: '/students', label: 'Students', icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z' },
  { to: '/teachers', label: 'Teachers', icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z' },
  { to: '/academic', label: 'Academics', icon: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4' },
  { to: '/attendance', label: 'Attendance', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01' },
  { to: '/fees', label: 'Fees', icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z' },
  { to: '/reports', label: 'Reports', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
  { to: '/analytics', label: 'Analytics', icon: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6' },
  { to: '/notifications', label: 'Notifications', icon: 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9' },
  { to: '/operations', label: 'Data Ops', icon: 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15' },
  { to: '/users', label: 'Users', icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z' },
]

export function Sidebar() {
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
