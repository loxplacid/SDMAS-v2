// ── Role definition types ──

export type UserRole = 'admin' | 'principal' | 'accountant' | 'staff' | 'teacher' | 'student' | 'parent'

export interface RoleConfig {
  label: string
  description: string
  icon: string
  color: string
  homeRoute: string
}

export interface NavSection {
  label: string
  items: NavItem[]
}

export interface NavItem {
  to: string
  label: string
  icon: string
  badge?: number
  /** Route patterns this item is highlighted for (for sub-route matching) */
  matchPaths?: string[]
}

// ── Role metadata ──

export const ROLE_CONFIG: Record<UserRole, RoleConfig> = {
  admin: {
    label: 'Administrator',
    description: 'Full system access',
    icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z',
    color: 'bg-[var(--color-brand-accent)]',
    homeRoute: '/command-center',
  },
  principal: {
    label: 'Principal',
    description: 'School leadership overview',
    icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z',
    color: 'bg-indigo-500',
    homeRoute: '/command-center',
  },
  accountant: {
    label: 'Accountant',
    description: 'Financial management',
    icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
    color: 'bg-blue-500',
    homeRoute: '/command-center',
  },
  staff: {
    label: 'Staff',
    description: 'General staff access',
    icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
    color: 'bg-teal-500',
    homeRoute: '/command-center',
  },
  teacher: {
    label: 'Teacher',
    description: 'Classes, attendance & students',
    icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
    color: 'bg-emerald-500',
    homeRoute: '/teacher',
  },
  student: {
    label: 'Student',
    description: 'My attendance, fees & schedule',
    icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z',
    color: 'bg-violet-500',
    homeRoute: '/student',
  },
  parent: {
    label: 'Parent',
    description: 'Children overview & payments',
    icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z',
    color: 'bg-amber-500',
    homeRoute: '/parent',
  },
}

// ── Role-based navigation items (grouped by section) ──

const NAV_ICONS = {
  dashboard: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6',
  admissions: 'M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z',
  students: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z',
  teachers: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
  academic: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
  attendance: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01',
  fees: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  reports: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
  analytics: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6',
  notifications: 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9',
  operations: 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15',
  users: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z',
  profile: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
  'my-classes': 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
  'my-attendance': 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2',
  'my-fees': 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  schedule: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z',
  leave: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2zM7 14l3 3 7-7',
  approvals: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4',
}

/** Nav items visible to Admin role (full access) */
const NAV_ICON_COMMUNICATIONS = 'M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z'

const adminNav: NavItem[] = [
  { to: '/command-center', label: 'Command Center', icon: NAV_ICONS.dashboard, matchPaths: ['/command-center'] },
  { to: '/action-center', label: 'Action Center', icon: NAV_ICONS.approvals, matchPaths: ['/action-center'] },
  { to: '/risk', label: 'Risk Center', icon: NAV_ICONS.analytics, matchPaths: ['/risk'] },
  { to: '/data-quality', label: 'Data Quality', icon: NAV_ICONS.reports, matchPaths: ['/data-quality'] },
  { to: '/work', label: 'Work Queue', icon: NAV_ICONS.approvals, matchPaths: ['/work', '/cases'] },
  { to: '/timeline', label: 'Timeline', icon: NAV_ICONS.operations, matchPaths: ['/timeline'] },
  { to: '/leave', label: 'Leave', icon: NAV_ICONS.leave, matchPaths: ['/leave'] },
  { to: '/admissions', label: 'Admissions', icon: NAV_ICONS.admissions, matchPaths: ['/admissions'] },
  { to: '/students', label: 'Students', icon: NAV_ICONS.students },
  { to: '/teachers', label: 'Teachers', icon: NAV_ICONS.teachers },
  { to: '/academic', label: 'Academics', icon: NAV_ICONS.academic, matchPaths: ['/academic'] },
  { to: '/attendance', label: 'Attendance', icon: NAV_ICONS.attendance, matchPaths: ['/attendance'] },
  { to: '/fees', label: 'Fees', icon: NAV_ICONS.fees, matchPaths: ['/fees'] },
  { to: '/subjects', label: 'Subjects', icon: NAV_ICONS.academic },
  { to: '/communications', label: 'Communications', icon: NAV_ICON_COMMUNICATIONS, matchPaths: ['/communications'] },
  { to: '/reports', label: 'Reports', icon: NAV_ICONS.reports, matchPaths: ['/reports'] },
  { to: '/reports/cards', label: 'Report Cards', icon: NAV_ICONS.reports, matchPaths: ['/reports/cards'] },
  { to: '/analytics', label: 'Analytics', icon: NAV_ICONS.analytics, matchPaths: ['/analytics'] },
  { to: '/notifications', label: 'Notifications', icon: NAV_ICONS.notifications },
  { to: '/operations', label: 'Data Ops', icon: NAV_ICONS.operations },
  { to: '/migration', label: 'Data Migration', icon: NAV_ICONS.operations, matchPaths: ['/migration'] },
  { to: '/users', label: 'Users', icon: NAV_ICONS.users },
  { to: '/admin/audit-logs', label: 'Audit Logs', icon: NAV_ICONS.operations, matchPaths: ['/admin/audit-logs'] },
  { to: '/admin/approvals', label: 'Approvals', icon: NAV_ICONS.approvals, matchPaths: ['/admin/approvals'] },
]

/** Nav items visible to Teacher role */
const teacherNav: NavItem[] = [
  { to: '/teacher', label: 'Dashboard', icon: NAV_ICONS.dashboard },
  { to: '/teacher/classes', label: 'My Classes', icon: NAV_ICONS['my-classes'] },
  { to: '/teacher/students', label: 'Students', icon: NAV_ICONS.students },
  { to: '/attendance', label: 'Attendance', icon: NAV_ICONS.attendance, matchPaths: ['/attendance'] },
  { to: '/communications', label: 'Communications', icon: NAV_ICON_COMMUNICATIONS, matchPaths: ['/communications'] },
  { to: '/notifications', label: 'Notifications', icon: NAV_ICONS.notifications },
  { to: '/profile', label: 'Profile', icon: NAV_ICONS.profile },
]

/** Nav items visible to Student role */
const studentNav: NavItem[] = [
  { to: '/student', label: 'Dashboard', icon: NAV_ICONS.dashboard },
  { to: '/student/timetable', label: 'Timetable', icon: NAV_ICONS.schedule, matchPaths: ['/student/timetable'] },
  { to: '/student/attendance', label: 'Attendance', icon: NAV_ICONS['my-attendance'], matchPaths: ['/student/attendance'] },
  { to: '/student/subjects', label: 'Subjects', icon: NAV_ICONS.academic, matchPaths: ['/student/subjects'] },
  { to: '/student/results', label: 'Results', icon: NAV_ICONS.analytics, matchPaths: ['/student/results'] },
  { to: '/student/assignments', label: 'Assignments', icon: NAV_ICONS.operations, matchPaths: ['/student/assignments'] },
  { to: '/student/announcements', label: 'Announcements', icon: NAV_ICON_COMMUNICATIONS, matchPaths: ['/student/announcements'] },
  { to: '/student/documents', label: 'Documents', icon: NAV_ICONS.operations, matchPaths: ['/student/documents'] },
  { to: '/student/fees', label: 'My Fees', icon: NAV_ICONS['my-fees'] },
  { to: '/notifications', label: 'Alerts', icon: NAV_ICONS.notifications },
  { to: '/profile', label: 'Profile', icon: NAV_ICONS.profile },
]

/** Nav items visible to Parent role */
const parentNav: NavItem[] = [
  { to: '/parent', label: 'Dashboard', icon: NAV_ICONS.dashboard },
  { to: '/parent/children', label: 'My Children', icon: NAV_ICONS.students },
  { to: '/parent/attendance', label: 'Attendance', icon: NAV_ICONS['my-attendance'], matchPaths: ['/parent/attendance'] },
  { to: '/parent/fees', label: 'Fees & Payments', icon: NAV_ICONS['my-fees'], matchPaths: ['/parent/fees'] },
  { to: '/parent/academic', label: 'Academics', icon: NAV_ICONS.academic, matchPaths: ['/parent/academic'] },
  { to: '/parent/announcements', label: 'Announcements', icon: NAV_ICON_COMMUNICATIONS, matchPaths: ['/parent/announcements'] },
  { to: '/parent/documents', label: 'Documents', icon: NAV_ICONS.operations, matchPaths: ['/parent/documents'] },
  { to: '/parent/messages', label: 'Messages', icon: NAV_ICONS.notifications, matchPaths: ['/parent/messages'] },
  { to: '/notifications', label: 'Alerts', icon: NAV_ICONS.notifications },
  { to: '/profile', label: 'Profile', icon: NAV_ICONS.profile },
]

/** Nav items visible to Principal role (leadership overview) */
const principalNav: NavItem[] = [
  { to: '/command-center', label: 'Command Center', icon: NAV_ICONS.dashboard, matchPaths: ['/command-center'] },
  { to: '/action-center', label: 'Action Center', icon: NAV_ICONS.approvals, matchPaths: ['/action-center'] },
  { to: '/risk', label: 'Risk Center', icon: NAV_ICONS.analytics, matchPaths: ['/risk'] },
  { to: '/data-quality', label: 'Data Quality', icon: NAV_ICONS.reports, matchPaths: ['/data-quality'] },
  { to: '/work', label: 'Work Queue', icon: NAV_ICONS.approvals, matchPaths: ['/work', '/cases'] },
  { to: '/timeline', label: 'Timeline', icon: NAV_ICONS.operations, matchPaths: ['/timeline'] },
  { to: '/students', label: 'Students', icon: NAV_ICONS.students },
  { to: '/teachers', label: 'Teachers', icon: NAV_ICONS.teachers },
  { to: '/academic', label: 'Academics', icon: NAV_ICONS.academic, matchPaths: ['/academic'] },
  { to: '/attendance', label: 'Attendance', icon: NAV_ICONS.attendance, matchPaths: ['/attendance'] },
  { to: '/communications', label: 'Communications', icon: NAV_ICON_COMMUNICATIONS, matchPaths: ['/communications'] },
  { to: '/reports', label: 'Reports', icon: NAV_ICONS.reports, matchPaths: ['/reports'] },
  { to: '/reports/cards', label: 'Report Cards', icon: NAV_ICONS.reports, matchPaths: ['/reports/cards'] },
  { to: '/analytics', label: 'Analytics', icon: NAV_ICONS.analytics, matchPaths: ['/analytics'] },
  { to: '/notifications', label: 'Notifications', icon: NAV_ICONS.notifications },
  { to: '/profile', label: 'Profile', icon: NAV_ICONS.profile },
]

/** Nav items visible to Accountant role (financial management) */
const accountantNav: NavItem[] = [
  { to: '/command-center', label: 'Command Center', icon: NAV_ICONS.dashboard, matchPaths: ['/command-center'] },
  { to: '/action-center', label: 'Action Center', icon: NAV_ICONS.approvals, matchPaths: ['/action-center'] },
  { to: '/fees/structures', label: 'Fee Structures', icon: NAV_ICONS.fees, matchPaths: ['/fees/structures'] },
  { to: '/fees/dues', label: 'Fee Dues', icon: NAV_ICONS['my-fees'], matchPaths: ['/fees/dues'] },
  { to: '/fees/payments', label: 'Payments', icon: NAV_ICONS.fees, matchPaths: ['/fees/payments'] },
  { to: '/fees/summary', label: 'Financial Summary', icon: NAV_ICONS.analytics, matchPaths: ['/fees/summary'] },
  { to: '/reports', label: 'Reports', icon: NAV_ICONS.reports, matchPaths: ['/reports'] },
  { to: '/notifications', label: 'Notifications', icon: NAV_ICONS.notifications },
  { to: '/profile', label: 'Profile', icon: NAV_ICONS.profile },
]

/** Nav items visible to Staff role (general operations) */
const staffNav: NavItem[] = [
  { to: '/command-center', label: 'Command Center', icon: NAV_ICONS.dashboard, matchPaths: ['/command-center'] },
  { to: '/action-center', label: 'Action Center', icon: NAV_ICONS.approvals, matchPaths: ['/action-center'] },
  { to: '/risk', label: 'Risk Center', icon: NAV_ICONS.analytics, matchPaths: ['/risk'] },
  { to: '/data-quality', label: 'Data Quality', icon: NAV_ICONS.reports, matchPaths: ['/data-quality'] },
  { to: '/work', label: 'Work Queue', icon: NAV_ICONS.approvals, matchPaths: ['/work', '/cases'] },
  { to: '/timeline', label: 'Timeline', icon: NAV_ICONS.operations, matchPaths: ['/timeline'] },
  { to: '/attendance', label: 'Attendance', icon: NAV_ICONS.attendance, matchPaths: ['/attendance'] },
  { to: '/leave', label: 'Leave', icon: NAV_ICONS.leave, matchPaths: ['/leave'] },
  { to: '/communications', label: 'Communications', icon: NAV_ICON_COMMUNICATIONS, matchPaths: ['/communications'] },
  { to: '/notifications', label: 'Notifications', icon: NAV_ICONS.notifications },
  { to: '/profile', label: 'Profile', icon: NAV_ICONS.profile },
]

/** Get nav sections for a given role (grouped by category) */
export function getNavSectionsForRole(role: string): NavSection[] {
  const items = getNavItemsForRole(role)

  if (role === 'admin') {
    return [
      {
        label: 'Overview',
        items: items.filter((i) => ['/command-center', '/action-center', '/risk', '/data-quality', '/work', '/timeline', '/leave', '/admissions', '/notifications'].includes(i.to)),
      },
      {
        label: 'Records',
        items: items.filter((i) => ['/students', '/teachers', '/subjects', '/academic'].includes(i.to)),
      },
      {
        label: 'Operations',
        items: items.filter((i) => ['/attendance', '/fees', '/communications', '/reports', '/reports/cards', '/analytics'].includes(i.to)),
      },
      {
        label: 'System',
        items: items.filter((i) => ['/operations', '/users', '/admin/audit-logs', '/admin/approvals'].includes(i.to)),
      },
    ].filter((s) => s.items.length > 0)
  }

  if (role === 'teacher') {
    return [
      {
        label: 'Overview',
        items: items.filter((i) => ['/teacher'].includes(i.to)),
      },
      {
        label: 'Work',
        items: items.filter((i) => ['/teacher/classes', '/teacher/students', '/attendance', '/communications'].includes(i.to)),
      },
      {
        label: 'Account',
        items: items.filter((i) => ['/notifications', '/profile'].includes(i.to)),
      },
    ].filter((s) => s.items.length > 0)
  }

  if (role === 'student') {
    return [
      {
        label: 'Overview',
        items: items.filter((i) => ['/student'].includes(i.to)),
      },
      {
        label: 'Academics',
        items: items.filter((i) => ['/student/timetable', '/student/subjects', '/student/results', '/student/assignments'].includes(i.to)),
      },
      {
        label: 'Records',
        items: items.filter((i) => ['/student/attendance', '/student/fees', '/student/documents'].includes(i.to)),
      },
      {
        label: 'Updates',
        items: items.filter((i) => ['/student/announcements', '/notifications'].includes(i.to)),
      },
      {
        label: 'Account',
        items: items.filter((i) => ['/profile'].includes(i.to)),
      },
    ].filter((s) => s.items.length > 0)
  }

  if (role === 'parent') {
    return [
      {
        label: 'Overview',
        items: items.filter((i) => ['/parent'].includes(i.to)),
      },
      {
        label: 'Children',
        items: items.filter((i) => ['/parent/children', '/parent/attendance', '/parent/fees', '/parent/academic'].includes(i.to)),
      },
      {
        label: 'School',
        items: items.filter((i) => ['/parent/announcements', '/parent/documents', '/parent/messages', '/notifications'].includes(i.to)),
      },
      {
        label: 'Account',
        items: items.filter((i) => ['/profile'].includes(i.to)),
      },
    ].filter((s) => s.items.length > 0)
  }

  if (role === 'principal') {
    return [
      {
        label: 'Overview',
        items: items.filter((i) => ['/command-center', '/action-center', '/risk', '/data-quality', '/work', '/timeline'].includes(i.to)),
      },
      {
        label: 'Records',
        items: items.filter((i) => ['/students', '/teachers', '/academic'].includes(i.to)),
      },
      {
        label: 'Operations',
        items: items.filter((i) => ['/attendance', '/communications', '/reports', '/reports/cards', '/analytics'].includes(i.to)),
      },
      {
        label: 'Account',
        items: items.filter((i) => ['/notifications', '/profile'].includes(i.to)),
      },
    ].filter((s) => s.items.length > 0)
  }

  if (role === 'accountant') {
    return [
      {
        label: 'Overview',
        items: items.filter((i) => ['/command-center', '/action-center'].includes(i.to)),
      },
      {
        label: 'Finance',
        items: items.filter((i) => ['/fees/structures', '/fees/dues', '/fees/payments', '/fees/summary'].includes(i.to)),
      },
      {
        label: 'Reports',
        items: items.filter((i) => ['/reports'].includes(i.to)),
      },
      {
        label: 'Account',
        items: items.filter((i) => ['/notifications', '/profile'].includes(i.to)),
      },
    ].filter((s) => s.items.length > 0)
  }

  if (role === 'staff') {
    return [
      {
        label: 'Overview',
        items: items.filter((i) => ['/command-center', '/action-center', '/risk', '/data-quality', '/work', '/timeline'].includes(i.to)),
      },
      {
        label: 'Operations',
        items: items.filter((i) => ['/attendance', '/leave', '/communications'].includes(i.to)),
      },
      {
        label: 'Account',
        items: items.filter((i) => ['/notifications', '/profile'].includes(i.to)),
      },
    ].filter((s) => s.items.length > 0)
  }

  return [{ label: 'Navigation', items }]
}

/** Get nav items for a given role */
export function getNavItemsForRole(role: string): NavItem[] {
  switch (role) {
    case 'teacher':
      return teacherNav
    case 'student':
      return studentNav
    case 'parent':
      return parentNav
    case 'principal':
      return principalNav
    case 'accountant':
      return accountantNav
    case 'staff':
      return staffNav
    default:
      return adminNav
  }
}

/** Get the home/landing route for a given role */
export function getHomeRoute(role: string | undefined | null): string {
  switch (role) {
    case 'teacher':
      return '/teacher'
    case 'student':
      return '/student'
    case 'parent':
      return '/parent'
    default:
      // Admin, principal, accountant and staff all land on the Command Center
      return '/command-center'
  }
}

// ── Role badge colors (shared between sidebar, header dropdown, and tables) ──

export const ROLE_BADGE_COLORS: Record<string, string> = {
  admin: 'bg-[var(--color-brand-accent)] text-white',
  principal: 'bg-indigo-500/15 text-indigo-600 dark:text-indigo-400',
  accountant: 'bg-blue-500/15 text-blue-600 dark:text-blue-400',
  staff: 'bg-teal-500/15 text-teal-600 dark:text-teal-400',
  teacher: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400',
  student: 'bg-violet-500/15 text-violet-600 dark:text-violet-400',
  parent: 'bg-amber-500/15 text-amber-600 dark:text-amber-400',
}

/**
 * True when `path` is `base` or a descendant route (`/base/...`). Plain
 * `startsWith` would let `/students` match the `student` role prefix — a
 * real over-permission bug (student role gaining the admin Students page).
 */
function routeOrDescendant(path: string, base: string): boolean {
  return path === base || path.startsWith(`${base}/`)
}

/** Check if a role has access to a specific route pattern */
export function hasRouteAccess(role: string, path: string): boolean {
  // Admin has access to everything
  if (role === 'admin') return true

  // Principal, Accountant, Staff — role workspace + relevant domains
  if (['principal', 'accountant', 'staff'].includes(role)) {
    if (routeOrDescendant(path, `/${role}`)) return true
    if (path === '/command-center' || path.startsWith('/command-center')) return true
    if (path === '/action-center' || path.startsWith('/action-center')) return true
    if (role !== 'accountant' && (path === '/data-quality' || path.startsWith('/data-quality'))) return true
    if (role !== 'accountant' && (path === '/work' || path.startsWith('/work') || path.startsWith('/cases/'))) return true
    if (path === '/timeline' || path.startsWith('/timeline')) return true
    if (role !== 'accountant' && (path === '/risk' || path.startsWith('/risk'))) return true
    if (path === '/notifications' || path.startsWith('/notifications')) return true
    if (path === '/profile' || path.startsWith('/profile')) return true
    if (role === 'accountant' && (path.startsWith('/fees') || path.startsWith('/reports'))) return true
    // Principal mirrors its nav: leadership also operates attendance and
    // communications (not just reports/analytics) — the RoleGuard and the
    // command palette must agree with what the sidebar shows.
    if (role === 'principal' && (path.startsWith('/reports') || path.startsWith('/analytics') || path.startsWith('/attendance') || path.startsWith('/communications'))) return true
    if (role === 'staff' && (path.startsWith('/attendance') || path.startsWith('/leave'))) return true
    return false
  }

  // Teacher routes
  if (role === 'teacher') {
    if (routeOrDescendant(path, '/teacher')) return true
    if (path === '/command-center' || path.startsWith('/command-center')) return true
    if (path === '/timeline' || path.startsWith('/timeline')) return true
    if (path.startsWith('/attendance')) return true
    if (path === '/notifications' || path.startsWith('/notifications')) return true
    if (path === '/profile' || path.startsWith('/profile')) return true
    return false
  }

  // Student routes
  if (role === 'student') {
    if (routeOrDescendant(path, '/student')) return true
    if (path === '/notifications' || path.startsWith('/notifications')) return true
    if (path === '/profile' || path.startsWith('/profile')) return true
    return false
  }

  // Parent routes
  if (role === 'parent') {
    if (routeOrDescendant(path, '/parent')) return true
    if (path === '/notifications' || path.startsWith('/notifications')) return true
    if (path === '/profile' || path.startsWith('/profile')) return true
    return false
  }

  return false
}
