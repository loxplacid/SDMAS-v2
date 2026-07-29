import { useState, useCallback } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import { Sidebar } from './sidebar'
import { Header } from './header'
import { CommandPalette } from '../ui/command-palette'
import { KeyboardShortcutsDialog } from '../ui/keyboard-shortcuts-dialog'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'
import { RouteTransition } from '../ui/route-transition'

const navIcons: Record<string, string> = {
  dashboard: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6',
  students: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z',
  teachers: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
  academic: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
  attendance: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2',
  fees: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  reports: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
  analytics: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6',
  notifications: 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9',
  operations: 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15',
  users: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z',
  profile: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
}

const locationToNavLabel: Record<string, string> = {
  dashboard: 'Dashboard',
  students: 'Students',
  teachers: 'Teachers',
  academic: 'Academics',
  attendance: 'Attendance',
  fees: 'Fees',
  reports: 'Reports',
  analytics: 'Analytics',
  notifications: 'Notifications',
  operations: 'Operations',
  users: 'Users',
  profile: 'Profile',
}

function buildCommandGroups(navigate: (path: string) => void) {
  return [
    {
      label: 'Pages',
      items: [
        { id: 'nav-dashboard', label: 'Dashboard', description: 'Executive overview', icon: navIcons.dashboard, action: () => navigate('/dashboard'), keywords: ['home', 'overview'] },
        { id: 'nav-students', label: 'Students', description: 'Manage student records', icon: navIcons.students, action: () => navigate('/students'), keywords: ['people', 'enrollment'] },
        { id: 'nav-teachers', label: 'Teachers', description: 'Manage teaching staff', icon: navIcons.teachers, action: () => navigate('/teachers'), keywords: ['staff', 'faculty'] },
        { id: 'nav-academic', label: 'Academics', description: 'Classes, sections, terms', icon: navIcons.academic, action: () => navigate('/academic'), keywords: ['classes', 'years', 'terms'] },
        { id: 'nav-attendance', label: 'Attendance', description: 'Track student attendance', icon: navIcons.attendance, action: () => navigate('/attendance'), keywords: ['present', 'absent'] },
        { id: 'nav-fees', label: 'Fees', description: 'Fee structures and payments', icon: navIcons.fees, action: () => navigate('/fees'), keywords: ['payments', 'financial'] },
        { id: 'nav-reports', label: 'Reports', description: 'Attendance and fee reports', icon: navIcons.reports, action: () => navigate('/reports'), keywords: ['summaries'] },
        { id: 'nav-analytics', label: 'Analytics', description: 'Data insights and trends', icon: navIcons.analytics, action: () => navigate('/analytics'), keywords: ['charts', 'insights'] },
        { id: 'nav-notifications', label: 'Notifications', description: 'System alerts', icon: navIcons.notifications, action: () => navigate('/notifications'), keywords: ['alerts', 'messages'] },
        { id: 'nav-operations', label: 'Data Operations', description: 'Exports, rollover, batch ops', icon: navIcons.operations, action: () => navigate('/operations'), keywords: ['export', 'rollover', 'batch'] },
        { id: 'nav-users', label: 'Users', description: 'Manage system users', icon: navIcons.users, action: () => navigate('/users'), keywords: ['accounts', 'admin'] },
        { id: 'nav-profile', label: 'Profile', description: 'Your account settings', icon: navIcons.profile, action: () => navigate('/profile'), keywords: ['settings', 'account'] },
      ],
    },
    {
      label: 'Actions',
      items: [
        { id: 'act-student-add', label: 'Add Student', description: 'Create a new student record', icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197', action: () => navigate('/students'), keywords: ['new', 'create', 'register'] },
        { id: 'act-attendance-record', label: 'Record Attendance', description: 'Mark daily attendance', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2', action: () => navigate('/attendance/daily'), keywords: ['mark', 'daily'] },
        { id: 'act-payment', label: 'Record Payment', description: 'Record a fee payment', icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2', action: () => navigate('/fees/payments'), keywords: ['fee', 'collect'] },
        { id: 'act-enrollment', label: 'Batch Enroll', description: 'Enroll multiple students', icon: 'M12 4.354a4 4 0 110 5.292', action: () => navigate('/operations/batch/enroll'), keywords: ['bulk', 'register'] },
      ],
    },
  ]
}

export function AppLayout() {
  const [commandOpen, setCommandOpen] = useState(false)
  const [shortcutsOpen, setShortcutsOpen] = useState(false)

  const reactNavigate = useNavigate()

  const navigate = useCallback((path: string) => {
    reactNavigate(path)
  }, [reactNavigate])

  // `?` opens the keyboard shortcuts dialog
  useKeyboardShortcut({ '?': () => setShortcutsOpen(true) }, [])

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--color-bg)]">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Header
          onOpenCommandPalette={() => setCommandOpen(true)}
          onOpenSearch={() => setCommandOpen(true)}
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

      {/* Command Palette */}
      <CommandPalette
        open={commandOpen}
        onClose={() => setCommandOpen(false)}
        groups={buildCommandGroups(navigate)}
      />

      {/* Keyboard Shortcuts Help */}
      <KeyboardShortcutsDialog
        open={shortcutsOpen}
        onClose={() => setShortcutsOpen(false)}
      />

      {/* Mobile ? shortcut button (visible below sm breakpoint) */}
      <button
        onClick={() => setShortcutsOpen(true)}
        className="sm:hidden fixed bottom-6 left-6 z-30 flex items-center justify-center h-10 w-10 rounded-full bg-[var(--color-surface)] text-[var(--color-text-secondary)] shadow-lg border border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)] transition-all active:scale-95 motion-reduce:active:scale-100 text-base font-bold animate-fade-in-scale"
        style={{ animationDelay: '600ms' }}
        aria-label="Keyboard shortcuts"
        title="Keyboard shortcuts (?)"
      >
        ?
      </button>
    </div>
  )
}
