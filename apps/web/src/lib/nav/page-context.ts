/**
 * P8 — page hierarchy: route → shell breadcrumb context.
 *
 * The app header shows a restrained two-level context ("Records / Students"
 * or "Leadership / Command Center") instead of a bare title. This module is
 * the single route → (section, page) registry — pure and unit-testable.
 * Longest-prefix matching keeps detail routes (e.g. /students/42) inside
 * their section without an entry per id.
 */

export interface PageCrumb {
  label: string
  /** Link target for non-terminal crumbs. */
  href?: string
}

/** Section (workspace) label per route prefix — longest match wins. */
const SECTION_BY_PREFIX: ReadonlyArray<[string, string]> = [
  ['/dashboard', 'Overview'],
  ['/command-center', 'Leadership'],
  ['/action-center', 'Leadership'],
  ['/risk', 'Leadership'],
  ['/data-quality', 'Leadership'],
  ['/work', 'Leadership'],
  ['/cases', 'Leadership'],
  ['/timeline', 'Leadership'],
  ['/principal', 'Leadership'],
  ['/students', 'Records'],
  ['/teachers', 'Records'],
  ['/academic', 'Records'],
  ['/subjects', 'Records'],
  ['/admissions', 'Records'],
  ['/attendance', 'Operations'],
  ['/leave', 'Operations'],
  ['/communications', 'Operations'],
  ['/staff', 'Operations'],
  ['/fees', 'Finance'],
  ['/school-finance', 'Finance'],
  ['/accountant', 'Finance'],
  ['/reports', 'Reporting'],
  ['/analytics', 'Insights'],
  ['/operations', 'System'],
  ['/users', 'System'],
  ['/notifications', 'System'],
  ['/profile', 'Account'],
  ['/teacher', 'My Work'],
  ['/student', 'My Space'],
  ['/parent', 'My Space'],
]

/** Known leaf page names (exact route → human label). */
const PAGE_NAMES: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/command-center': 'Command Center',
  '/action-center': 'Action Center',
  '/risk': 'Risk Center',
  '/data-quality': 'Data Quality',
  '/work': 'Work Queue',
  '/cases': 'Case',
  '/timeline': 'Timeline',
  '/students': 'Students',
  '/teachers': 'Teachers',
  '/subjects': 'Subjects',
  '/academic': 'Academics',
  '/academic/years': 'Academic Years',
  '/academic/classes': 'Classes',
  '/academic/sections': 'Sections',
  '/academic/terms': 'Terms',
  '/academic/enrollments': 'Enrollments',
  '/academic/assignments': 'Teacher Assignments',
  '/attendance': 'Attendance',
  '/attendance/records': 'Records',
  '/attendance/daily': 'Daily Attendance',
  '/attendance/record': 'Record Attendance',
  '/attendance/student': 'Student Attendance',
  '/attendance/section': 'Section Attendance',
  '/attendance-intelligence': 'Attendance Intelligence',
  '/fees': 'Fees',
  '/fees/fee-types': 'Fee Types',
  '/fees/structures': 'Fee Structures',
  '/fees/student-fees': 'Student Fees',
  '/fees/dues': 'Fee Dues',
  '/fees/payments': 'Payments',
  '/fees/summary': 'Financial Summary',
  '/school-finance': 'School Finance',
  '/school-finance/fee-schedules': 'Fee Schedules',
  '/school-finance/reconciliation': 'Reconciliation',
  '/school-finance/receipts': 'Receipts',
  '/school-finance/transactions': 'Transactions',
  '/school-finance/outstanding': 'Outstanding Balances',
  '/school-finance/reports': 'Finance Reports',
  '/reports': 'Reports',
  '/reports/cards': 'Report Cards',
  '/reports/attendance': 'Attendance Report',
  '/reports/fees/collection': 'Fee Collection',
  '/reports/fees/outstanding': 'Outstanding Report',
  '/reports/receipts': 'Receipt Lookup',
  '/reports/builder': 'Report Builder',
  '/analytics': 'Analytics',
  '/analytics/attendance': 'Attendance Analytics',
  '/analytics/finance': 'Finance Analytics',
  '/analytics/students': 'Student Analytics',
  '/analytics/academic': 'Academic Analytics',
  '/notifications': 'Notifications',
  '/operations': 'Data Operations',
  '/operations/rollover': 'Rollover',
  '/operations/batch/enroll': 'Batch Enroll',
  '/operations/batch/fee-dues': 'Batch Fee Dues',
  '/users': 'Users',
  '/admin/audit-logs': 'Audit Logs',
  '/admin/approvals': 'Approvals',
  '/leave': 'Leave',
  '/leave/new': 'New Leave',
  '/admissions': 'Admissions',
  '/admissions/applications': 'Applications',
  '/admissions/new': 'New Inquiry',
  '/communications': 'Communications',
  '/communications/compose': 'Compose',
  '/communications/templates': 'Templates',
  '/communications/sent': 'Sent',
  '/profile': 'Profile',
  '/student': 'My Dashboard',
  '/student/timetable': 'Timetable',
  '/student/attendance': 'My Attendance',
  '/student/subjects': 'My Subjects',
  '/student/results': 'My Results',
  '/student/assignments': 'Assignments',
  '/student/announcements': 'Announcements',
  '/student/documents': 'Documents',
  '/teacher': 'My Dashboard',
  '/parent': 'My Dashboard',
  '/parent/children': 'My Children',
  '/parent/attendance': 'Attendance',
  '/parent/fees': 'Fees & Payments',
  '/parent/academic': 'Academics',
  '/parent/announcements': 'Announcements',
  '/parent/documents': 'Documents',
  '/parent/messages': 'Messages',
}

function humanizeSegment(segment: string): string {
  return segment
    .split(/[-_]/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

/** Longest matching section for a route, with its prefix (for the link). */
function findSection(path: string): { label: string; href: string } | null {
  let best: { label: string; href: string } | null = null
  for (const [prefix, label] of SECTION_BY_PREFIX) {
    if (path.startsWith(prefix) && (!best || prefix.length > best.href.length)) {
      best = { label, href: prefix }
    }
  }
  return best
}

/**
 * Resolve a route to its shell breadcrumb hierarchy.
 *
 * Examples:
 *   /students        → [{ label: 'Records', href: '/students' }, { label: 'Students' }]
 *   /students/42     → [{ label: 'Records', href: '/students' }, { label: 'Students' }]
 *   /command-center  → [{ label: 'Leadership', href: '/command-center' }, { label: 'Command Center' }]
 *   /fees/payments   → [{ label: 'Finance', href: '/fees' }, { label: 'Payments' }]
 */
export function getPageHierarchy(path: string): PageCrumb[] {
  const section = findSection(path)

  let page = PAGE_NAMES[path]
  if (!page) {
    const segments = path.split('/').filter(Boolean)
    const last = segments[segments.length - 1] ?? ''
    if (last && !/^\d+$/.test(last)) {
      page = humanizeSegment(last)
    } else if (segments.length > 1) {
      // Detail routes (/:id) fall back to their entity name.
      page = humanizeSegment(segments[segments.length - 2])
    }
  }
  if (!page) page = 'Home'

  const crumbs: PageCrumb[] = []
  if (section && section.label !== page) {
    crumbs.push({ label: section.label, href: section.href })
  }
  crumbs.push({ label: page })
  return crumbs
}
