/**
 * D1 §3 — role-aware command groups for the command palette.
 *
 * The palette must respect the current user's permissions the same way the
 * sidebar does. Pages are derived from `getNavItemsForRole` — the single
 * source of truth for role navigation — so a user can never command-search
 * their way into a surface the sidebar hides. Actions are additionally
 * filtered by `hasRouteAccess`, the same primitive the RoleGuard enforces
 * on every route.
 *
 * Pure and unit-testable; the shell supplies `navigate` and the role.
 */

import { getNavItemsForRole, hasRouteAccess } from '../../types/roles'
import type { ContextCommand } from './contextual-commands'

interface ActionCommand {
  id: string
  label: string
  description: string
  path: string
  icon: string
  keywords: string[]
}

const ACTION_COMMANDS: ActionCommand[] = [
  {
    id: 'act-student-add',
    label: 'Add Student',
    description: 'Create a new student record',
    path: '/students',
    icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197',
    keywords: ['new', 'create', 'register'],
  },
  {
    id: 'act-attendance-record',
    label: 'Record Attendance',
    description: 'Mark daily attendance',
    path: '/attendance/daily',
    icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2',
    keywords: ['mark', 'daily'],
  },
  {
    id: 'act-payment',
    label: 'Record Payment',
    description: 'Record a fee payment',
    path: '/fees/payments',
    icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2',
    keywords: ['fee', 'collect'],
  },
  {
    id: 'act-enrollment',
    label: 'Batch Enroll',
    description: 'Enroll multiple students',
    path: '/operations/batch/enroll',
    icon: 'M12 4.354a4 4 0 110 5.292',
    keywords: ['bulk', 'register'],
  },
]

/** Curated descriptions for the highest-value routes (kept off nav items). */
const ROUTE_DESCRIPTIONS: Record<string, string> = {
  '/command-center': 'School health, alerts & today',
  '/action-center': 'What needs your attention right now',
  '/risk': 'Deterministic risk findings & attention',
  '/data-quality': 'Duplicates, missing fields & invalid records',
  '/work': 'Operational cases assigned to you or open for action',
  '/timeline': 'Unified operational activity feed',
  '/dashboard': 'Executive overview',
  '/students': 'Manage student records',
  '/teachers': 'Manage teaching staff',
  '/academic': 'Classes, sections, terms',
  '/attendance': 'Track student attendance',
  '/fees': 'Fee structures and payments',
  '/reports': 'Attendance and fee reports',
  '/analytics': 'Data insights and trends',
  '/communications': 'Send messages & announcements',
  '/notifications': 'System alerts',
  '/operations': 'Exports, rollover, batch ops',
  '/users': 'Manage system users',
  '/profile': 'Your account settings',
}

/**
 * Extra command-palette keywords per route so fuzzy queries like "health",
 * "alerts" or "export" still surface the right page (labels alone miss
 * these natural command phrases). Keys mirror ROUTE_DESCRIPTIONS.
 */
const ROUTE_KEYWORDS: Record<string, string[]> = {
  '/command-center': ['home', 'overview', 'leadership', 'health', 'alerts'],
  '/action-center': ['attention', 'actions', 'resolve', 'todo', 'alerts'],
  '/risk': ['risk', 'attention', 'findings', 'alerts', 'rules'],
  '/data-quality': ['quality', 'duplicates', 'data', 'integrity', 'cleanliness'],
  '/work': ['cases', 'queue', 'assignments', 'sla', 'overdue', 'todo'],
  '/timeline': ['activity', 'feed', 'audit', 'events', 'history'],
  '/students': ['people', 'enrollment'],
  '/teachers': ['staff', 'faculty'],
  '/academic': ['classes', 'years', 'terms'],
  '/attendance': ['present', 'absent'],
  '/fees': ['payments', 'financial'],
  '/reports': ['summaries'],
  '/analytics': ['charts', 'insights'],
  '/communications': ['email', 'sms', 'announcement', 'bulk'],
  '/notifications': ['alerts', 'messages'],
  '/operations': ['export', 'rollover', 'batch'],
  '/users': ['accounts', 'admin'],
  '/profile': ['settings', 'account'],
}

/**
 * Build the palette's static groups for a role. Returns `[]` groups when a
 * role has no commands (defensive — every defined role has nav).
 */
export function buildCommandGroups(
  navigate: (path: string) => void,
  role: string | undefined,
): Array<{ label: string; items: ContextCommand[] }> {
  const pages: ContextCommand[] = getNavItemsForRole(role || '').map((item) => ({
    id: `nav-${item.to}`,
    label: item.label,
    description: ROUTE_DESCRIPTIONS[item.to],
    icon: item.icon,
    action: () => navigate(item.to),
    keywords: [item.label.toLowerCase(), ...(ROUTE_KEYWORDS[item.to] ?? [])],
  }))

  const actions: ContextCommand[] = ACTION_COMMANDS.filter((cmd) =>
    hasRouteAccess(role || '', cmd.path)
  ).map((cmd) => ({
    id: cmd.id,
    label: cmd.label,
    description: cmd.description,
    icon: cmd.icon,
    action: () => navigate(cmd.path),
    keywords: cmd.keywords,
  }))

  const groups: Array<{ label: string; items: ContextCommand[] }> = []
  if (pages.length > 0) groups.push({ label: 'Pages', items: pages })
  if (actions.length > 0) groups.push({ label: 'Actions', items: actions })
  return groups
}
