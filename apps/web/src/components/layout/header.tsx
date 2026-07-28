import { useState, useRef, useEffect } from 'react'
import { useAuth } from '../../api/auth/auth-context'
import { cn } from '../../lib/utils'
import { NotificationBell } from '../notifications/notification-bell'

export function Header() {
  const { user, logout } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-4 lg:px-6">
      <div className="text-sm text-gray-500">
        <span className="hidden sm:inline">SDMAS v2</span>
      </div>
      <div className="flex items-center gap-2" ref={menuRef}>
        <NotificationBell />
        <div className="relative">
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="flex items-center gap-2 text-sm text-gray-700 hover:text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded-md px-2 py-1"
            aria-haspopup="true"
            aria-expanded={menuOpen}
          >
            <span className="hidden sm:inline">{user?.display_name || user?.username}</span>
            <span className="inline-flex items-center justify-center h-7 w-7 rounded-full bg-blue-100 text-xs font-semibold text-blue-800">
              {(user?.display_name || user?.username || '?').charAt(0).toUpperCase()}
            </span>
          </button>
          {menuOpen && (
            <div
              className="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg border border-gray-200 py-1 z-50"
              role="menu"
            >
              <div className="px-4 py-2 text-sm text-gray-500 border-b border-gray-100">
                <p className="font-medium text-gray-900 truncate">{user?.display_name || user?.username}</p>
                <p className="text-xs capitalize">{user?.role}</p>
              </div>
              <a
                href="/profile"
                className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                role="menuitem"
                onClick={(e) => { e.preventDefault(); window.location.href = '/profile'; setMenuOpen(false) }}
              >
                Profile
              </a>
              <button
                onClick={() => { logout(); setMenuOpen(false) }}
                className="block w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                role="menuitem"
              >
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}