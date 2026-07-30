// ── Role definition types ──

export type UserRole = 'admin' | 'teacher' | 'student' | 'parent'

export interface RoleConfig {
  label: string
  description: string
  icon: string
  color: string
  homeRoute: string
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
    homeRoute: '/dashboard',
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

// ── Role-based navigation items ──

const NAV_ICONS = {
  dashboard: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6',
  admissions: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
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
}

/** Nav items visible to Admin role (full access) */
const adminNav: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: NAV_ICONS.dashboard },
  { to: '/leave', label: 'Leave', icon: NAV_ICONS.dashboard, matchPaths: ['/leave'] },
  { to: '/admissions', label: 'Admissions', icon: NAV_ICONS.admissions, matchPaths: ['/admissions'] },
  { to: '/students', label: 'Students', icon: NAV_ICONS.students },
  { to: '/teachers', label: 'Teachers', icon: NAV_ICONS.teachers },
  { to: '/academic', label: 'Academics', icon: NAV_ICONS.academic, matchPaths: ['/academic'] },
  { to: '/attendance', label: 'Attendance', icon: NAV_ICONS.attendance, matchPaths: ['/attendance'] },
  { to: '/fees', label: 'Fees', icon: NAV_ICONS.fees, matchPaths: ['/fees'] },
  { to: '/subjects', label: 'Subjects', icon: NAV_ICONS.academic },
  { to: '/reports', label: 'Reports', icon: NAV_ICONS.reports, matchPaths: ['/reports'] },
  { to: '/analytics', label: 'Analytics', icon: NAV_ICONS.analytics, matchPaths: ['/analytics'] },
  { to: '/notifications', label: 'Notifications', icon: NAV_ICONS.notifications },
  { to: '/operations', label: 'Data Ops', icon: NAV_ICONS.operations },
  { to: '/users', label: 'Users', icon: NAV_ICONS.users },
]

/** Nav items visible to Teacher role */
const teacherNav: NavItem[] = [
  { to: '/teacher', label: 'Dashboard', icon: NAV_ICONS.dashboard },
  { to: '/teacher/classes', label: 'My Classes', icon: NAV_ICONS['my-classes'] },
  { to: '/teacher/students', label: 'Students', icon: NAV_ICONS.students },
  { to: '/attendance', label: 'Attendance', icon: NAV_ICONS.attendance, matchPaths: ['/attendance'] },
  { to: '/notifications', label: 'Notifications', icon: NAV_ICONS.notifications },
  { to: '/profile', label: 'Profile', icon: NAV_ICONS.profile },
]

/** Nav items visible to Student role */
const studentNav: NavItem[] = [
  { to: '/student', label: 'Dashboard', icon: NAV_ICONS.dashboard },
  { to: '/student/attendance', label: 'My Attendance', icon: NAV_ICONS['my-attendance'] },
  { to: '/student/fees', label: 'My Fees', icon: NAV_ICONS['my-fees'] },
  { to: '/student/schedule', label: 'Schedule', icon: NAV_ICONS.schedule },
  { to: '/notifications', label: 'Notifications', icon: NAV_ICONS.notifications },
  { to: '/profile', label: 'Profile', icon: NAV_ICONS.profile },
]

/** Nav items visible to Parent role */
const parentNav: NavItem[] = [
  { to: '/parent', label: 'Dashboard', icon: NAV_ICONS.dashboard },
  { to: '/parent/children', label: 'My Children', icon: NAV_ICONS.students },
  { to: '/parent/payments', label: 'Payments', icon: NAV_ICONS['my-fees'] },
  { to: '/notifications', label: 'Notifications', icon: NAV_ICONS.notifications },
  { to: '/profile', label: 'Profile', icon: NAV_ICONS.profile },
]

/** Get nav items for a given role */
export function getNavItemsForRole(role: string): NavItem[] {
  switch (role) {
    case 'teacher':
      return teacherNav
    case 'student':
      return studentNav
    case 'parent':
      return parentNav
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
      return '/dashboard'
  }
}

/** Check if a role has access to a specific route pattern */
export function hasRouteAccess(role: string, path: string): boolean {
  // Admin has access to everything
  if (role === 'admin') return true

  // Teacher routes
  if (role === 'teacher') {
    if (path.startsWith('/teacher')) return true
    if (path.startsWith('/attendance')) return true
    if (path === '/notifications' || path.startsWith('/notifications')) return true
    if (path === '/profile' || path.startsWith('/profile')) return true
    return false
  }

  // Student routes
  if (role === 'student') {
    if (path.startsWith('/student')) return true
    if (path === '/notifications' || path.startsWith('/notifications')) return true
    if (path === '/profile' || path.startsWith('/profile')) return true
    return false
  }

  // Parent routes
  if (role === 'parent') {
    if (path.startsWith('/parent')) return true
    if (path === '/notifications' || path.startsWith('/notifications')) return true
    if (path === '/profile' || path.startsWith('/profile')) return true
    return false
  }

  return false
}
