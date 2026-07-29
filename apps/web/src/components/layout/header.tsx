import { useState, useRef, useEffect, useCallback } from 'react'
import { useAuth } from '../../api/auth/auth-context'
import { NotificationBell } from '../notifications/notification-bell'
import { cn } from '../../lib/utils'
import { ThemeToggle } from '../ui/theme-toggle'

interface HeaderProps {
  onOpenCommandPalette?: () => void
  onOpenSearch?: () => void
  onOpenShortcuts?: () => void
}

export function Header({ onOpenCommandPalette, onOpenSearch, onOpenShortcuts }: HeaderProps) {
  const { user, logout } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)
  const [menuClosing, setMenuClosing] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  const closeMenu = useCallback(() => {
    if (menuOpen) {
      setMenuClosing(true)
      setTimeout(() => {
        setMenuClosing(false)
        setMenuOpen(false)
      }, 120)
    }
  }, [menuOpen])

  const toggleMenu = useCallback(() => {
    if (menuOpen) {
      closeMenu()
    } else {
      setMenuOpen(true)
      setMenuClosing(false)
    }
  }, [menuOpen, closeMenu])

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        closeMenu()
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [closeMenu])

  const showMenu = menuOpen

  return (
    <header className="h-[var(--header-height)] bg-[var(--color-surface)] border-b border-[var(--color-border)] flex items-center justify-between px-4 lg:px-6 flex-shrink-0 animate-fade-in-down">
      {/* Left */}
      <div className="flex items-center gap-2">
        {/* Mobile nav toggle is handled by the sidebar's FAB */}
      </div>

      {/* Center / Right */}
      <div className="flex items-center gap-1" ref={menuRef}>
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
        <button
          onClick={onOpenShortcuts}
          className="hidden sm:flex items-center justify-center h-7 w-7 rounded-lg text-xs font-semibold text-[var(--color-text-tertiary)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-secondary)] transition-colors border border-[var(--color-border)]"
          aria-label="Keyboard shortcuts"
          title="Keyboard shortcuts (?)"
        >
          ?
        </button>

        <ThemeToggle />

        <div className="w-px h-5 bg-[var(--color-border)] mx-1 hidden sm:block" />

        <NotificationBell />

        {/* User Menu */}
        <div className="relative">
          <button
            onClick={toggleMenu}
            className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm transition-colors hover:bg-[var(--color-surface-hover)] focus:outline-none focus:ring-2 focus:ring-[var(--color-brand-accent)]"
            aria-haspopup="true"
            aria-expanded={menuOpen}
          >
            <span className="flex items-center justify-center h-7 w-7 rounded-full bg-[var(--color-brand-accent)] text-[11px] font-bold text-white flex-shrink-0">
              {(user?.display_name || user?.username || '?').charAt(0).toUpperCase()}
            </span>
            <span className="hidden sm:inline text-sm font-medium text-[var(--color-text-primary)] max-w-[120px] truncate">
              {user?.display_name || user?.username}
            </span>
            <svg className={cn(
              'hidden sm:block h-3.5 w-3.5 text-[var(--color-text-muted)] transition-transform duration-150',
              menuOpen && 'rotate-180'
            )} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {showMenu && (
            <div
              className={cn(
                'absolute right-0 mt-2 w-56 bg-[var(--color-surface)] rounded-2xl shadow-xl border border-[var(--color-border)] py-1.5 z-50 origin-top-right',
                menuClosing ? 'animate-fade-out-scale' : 'animate-fade-in-scale'
              )}
              style={{ animationDuration: menuClosing ? 'var(--motion-fast)' : 'var(--motion-fast)', animationTimingFunction: 'var(--ease-spring)' }}
              role="menu"
            >
              <div className="px-4 py-3 border-b border-[var(--color-border)]">
                <p className="text-sm font-semibold text-[var(--color-text-primary)] truncate">
                  {user?.display_name || user?.username}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  {user?.role && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wider bg-[var(--color-brand-accent-light)] text-[var(--color-brand-accent)]">
                      {user.role}
                    </span>
                  )}
                  <span className="text-xs text-[var(--color-text-tertiary)] truncate">{user?.email}</span>
                </div>
              </div>

              <a
                href="/profile"
                className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] transition-colors"
                role="menuitem"
                onClick={(e) => { e.preventDefault(); window.location.href = '/profile'; closeMenu() }}
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
                Profile
              </a>

              <div className="border-t border-[var(--color-border)] my-1" />

              <button
                onClick={() => { logout(); closeMenu() }}
                className="flex items-center gap-2.5 w-full text-left px-4 py-2.5 text-sm text-[var(--color-danger)] hover:bg-[var(--color-danger-light)] transition-colors"
                role="menuitem"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
