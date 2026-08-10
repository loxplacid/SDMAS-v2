import { useState, useCallback, useEffect, useMemo } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Sidebar } from './sidebar'
import { Header } from './header'
import { CommandPalette } from '../ui/command-palette'
import { UniversalSearchModal } from '../ui/universal-search-modal'
import { KeyboardShortcutsDialog } from '../ui/keyboard-shortcuts-dialog'
import { InstallPWA } from '../ui/install-pwa'
import { SystemThemeToast } from '../ui/system-theme-toast'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'
import { useUniversalSearch } from '../../hooks/use-universal-search'
import { useNavPersistence } from '../../hooks/use-nav-persistence'
import { useAuth } from '../../api/auth/auth-context'
import {
  buildContextualCommands,
  buildRecentCommands,
  type ContextCommand,
} from '../../lib/nav/contextual-commands'
import { buildCommandGroups } from '../../lib/nav/command-groups'
import { RouteTransition } from '../ui/route-transition'

export function AppLayout() {
  const [commandOpen, setCommandOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [shortcutsOpen, setShortcutsOpen] = useState(false)
  const location = useLocation()
  const { user } = useAuth()

  const reactNavigate = useNavigate()
  const navPersistence = useNavPersistence()

  const navigate = useCallback((path: string) => {
    reactNavigate(path)
  }, [reactNavigate])

  // Universal search: instant local FTS5 index, synced in the background.
  const universalSearch = useUniversalSearch()

  // Command palette groups: route-aware contextual commands first (P8 §10),
  // then the visited-page "Recent" group (P8 §9), then the role-filtered
  // static page/action groups (D1 §3 — never expose surfaces the role
  // cannot reach). Rebuilt on route, role or history change only.
  const commandGroups = useMemo(() => {
    const contextual = buildContextualCommands(location.pathname, navigate)
    const recent = buildRecentCommands(navPersistence.recentItems, location.pathname, navigate)
    const groups = buildCommandGroups(navigate, user?.role)
    const ordered: Array<{ label: string; items: ContextCommand[] }> = []
    if (contextual.length > 0) ordered.push({ label: 'On this page', items: contextual })
    if (recent.length > 0) ordered.push({ label: 'Recent', items: recent })
    ordered.push(...groups)
    return ordered
  }, [navigate, location.pathname, navPersistence.recentItems, user?.role])

  // `?` opens the keyboard shortcuts dialog
  useKeyboardShortcut({ '?': () => setShortcutsOpen(true) }, [])

  // `Cmd+K` opens the command palette (P8 §9) — the header's ⌘K hint points
  // at the same surface. The palette's own handler owns the close half of
  // the toggle, so this only opens when closed. `Cmd+Shift+K` opens the
  // universal search modal.
  useKeyboardShortcut(
    {
      'mod+k': () => {
        if (!commandOpen) setCommandOpen(true)
      },
      'mod+shift+k': () => setSearchOpen(true),
    },
    [],
  )

  // Track page views for recent items
  useEffect(() => {
    const pageLabels: Record<string, string> = {
      '/dashboard': 'Dashboard',
      '/command-center': 'Command Center',
      '/action-center': 'Action Center',
      '/risk': 'Risk Center',
      '/data-quality': 'Data Quality',
      '/work': 'Work Queue',
      '/timeline': 'Timeline',
      '/students': 'Students',
      '/teachers': 'Teachers',
      '/academic': 'Academics',
      '/attendance': 'Attendance',
      '/attendance/records': 'Attendance Records',
      '/attendance/daily': 'Daily Attendance',
      '/communications': 'Communications',
      '/communications/compose': 'Compose Message',
      '/communications/templates': 'Message Templates',
      '/communications/sent': 'Sent Messages',
      '/fees': 'Fees',
      '/fees/fee-types': 'Fee Types',
      '/fees/structures': 'Fee Structures',
      '/fees/payments': 'Payments',
      '/reports': 'Reports',
      '/analytics': 'Analytics',
      '/notifications': 'Notifications',
      '/operations': 'Operations',
      '/users': 'Users',
      '/profile': 'Profile',
    }
    const label = pageLabels[location.pathname]
    if (label) {
      navPersistence.addRecentItem(location.pathname, label)
    }
  }, [location.pathname])

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--color-bg)]">
      <Sidebar
        collapsed={navPersistence.sidebarCollapsed}
        onToggle={navPersistence.toggleSidebar}
      />
      <div className="flex-1 flex flex-col min-w-0">
        <Header
          onOpenCommandPalette={() => setCommandOpen(true)}
          onOpenSearch={() => setSearchOpen(true)}
          onOpenShortcuts={() => setShortcutsOpen(true)}
        />
        <main className="flex-1 overflow-y-auto">
          <div className="p-4 lg:p-6 xl:p-8 max-w-[1400px] mx-auto w-full min-h-full">
            <RouteTransition>
              <Outlet />
            </RouteTransition>
          </div>
        </main>
      </div>

      {/* Command Palette (navigation + actions) */}
      <CommandPalette
        open={commandOpen}
        onClose={() => setCommandOpen(false)}
        groups={commandGroups}
      />

      {/* Universal Search Modal (instant local FTS5, background-synced) */}
      <UniversalSearchModal
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        search={universalSearch.search}
        status={universalSearch.status}
        onNavigate={(route) => {
          navigate(route)
          setSearchOpen(false)
        }}
      />

      {/* Keyboard Shortcuts Help */}
      <KeyboardShortcutsDialog
        open={shortcutsOpen}
        onClose={() => setShortcutsOpen(false)}
      />

      {/* Mobile ? shortcut button (visible below sm breakpoint) */}
      <button
        onClick={() => setShortcutsOpen(true)}
        className="sm:hidden fixed bottom-6 left-6 z-[var(--z-nav)] flex items-center justify-center h-10 w-10 rounded-full bg-[var(--color-surface)] text-[var(--color-text-secondary)] shadow-lg border border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)] transition-all active:scale-95 motion-reduce:active:scale-100 text-base font-bold animate-fade-in-scale"
        style={{ animationDelay: '600ms' }}
        aria-label="Keyboard shortcuts"
      >
        ?
      </button>

      {/* PWA Install Prompt */}
      <InstallPWA />

      {/* System Theme Change Toast */}
      <SystemThemeToast />
    </div>
  )
}
