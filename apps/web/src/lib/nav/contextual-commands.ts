/**
 * P8 — contextual commands: route-aware actions for the command palette.
 *
 * The palette becomes a global OS-style command surface: on Students it
 * offers Add/Export/Batch Enroll; on Finance, Record Payment / Summary;
 * on Attendance, Daily / Records. Only commands backed by existing routes
 * are registered — no fake buttons, no invented backend actions.
 *
 * Pure and unit-testable; the shell merges the result into the palette's
 * group list on route change.
 */

export interface ContextCommand {
  id: string
  label: string
  description?: string
  icon?: string
  action: () => void
  keywords?: string[]
}

const ICONS = {
  recent: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z',
  add: 'M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z',
  export: 'M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4',
  chart: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
  calendar: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z',
  mail: 'M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z',
  users: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z',
  book: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
  check: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
  bank: 'M3 6l9-4 9 4m-9-4v4m-7 2v8m4-8v8m6-8v8m4-8v8M3 22h18',
}

type Go = (to: string) => () => void

/** Route → contextual commands. Exact match wins; otherwise longest prefix. */
const ROUTE_COMMANDS: ReadonlyArray<[string, (go: Go) => ContextCommand[]]> = [
  [
    '/students',
    (go) => [
      { id: 'ctx-student-add', label: 'Add Student', description: 'Create a new student record', icon: ICONS.add, action: go('/students?action=add'), keywords: ['new', 'create', 'register'] },
      { id: 'ctx-student-export', label: 'Export Students', description: 'Student data export', icon: ICONS.export, action: go('/operations/export/students'), keywords: ['csv', 'spreadsheet'] },
      { id: 'ctx-student-enroll', label: 'Batch Enroll', description: 'Enroll multiple students at once', icon: ICONS.users, action: go('/operations/batch/enroll'), keywords: ['bulk', 'import'] },
    ],
  ],
  [
    '/teachers',
    (go) => [
      { id: 'ctx-teacher-add', label: 'Add Teacher', description: 'Create a new teacher record', icon: ICONS.add, action: go('/teachers?action=add'), keywords: ['new', 'create', 'staff'] },
    ],
  ],
  [
    '/academic',
    (go) => [
      { id: 'ctx-class-add', label: 'Add Class', description: 'Create a new class', icon: ICONS.add, action: go('/academic/classes?action=add'), keywords: ['new'] },
      { id: 'ctx-section-add', label: 'Add Section', description: 'Create a new section', icon: ICONS.add, action: go('/academic/sections?action=add'), keywords: ['new'] },
      { id: 'ctx-term-add', label: 'Add Term', description: 'Create a new term', icon: ICONS.add, action: go('/academic/terms?action=add'), keywords: ['new'] },
      { id: 'ctx-years', label: 'Academic Years', description: 'Manage academic years', icon: ICONS.calendar, action: go('/academic/years'), keywords: ['years'] },
      { id: 'ctx-enrollments', label: 'Enrollments', description: 'View enrollment records', icon: ICONS.users, action: go('/academic/enrollments'), keywords: ['enroll'] },
    ],
  ],
  [
    '/attendance',
    (go) => [
      { id: 'ctx-attendance-daily', label: 'Daily Attendance', description: "Open today's attendance", icon: ICONS.calendar, action: go('/attendance/daily'), keywords: ['today', 'mark'] },
      { id: 'ctx-attendance-records', label: 'Attendance Records', description: 'Browse attendance records', icon: ICONS.chart, action: go('/attendance/records'), keywords: ['history'] },
      { id: 'ctx-attendance-record', label: 'Record Attendance', description: 'Record attendance for a class', icon: ICONS.check, action: go('/attendance/record'), keywords: ['mark'] },
      { id: 'ctx-attendance-risk', label: 'Attendance Intelligence', description: 'View attendance risk findings', icon: ICONS.chart, action: go('/attendance-intelligence'), keywords: ['risk', 'anomaly'] },
    ],
  ],
  [
    '/fees',
    (go) => [
      { id: 'ctx-payment', label: 'Record Payment', description: 'Record a fee payment', icon: ICONS.bank, action: go('/fees/payments?action=new'), keywords: ['fee', 'collect', 'money'] },
      { id: 'ctx-fee-summary', label: 'Financial Summary', description: 'Revenue and collection summary', icon: ICONS.chart, action: go('/fees/summary'), keywords: ['revenue', 'total'] },
      { id: 'ctx-fee-structures', label: 'Fee Structures', description: 'Manage fee structures', icon: ICONS.book, action: go('/fees/structures'), keywords: ['structure'] },
      { id: 'ctx-fee-dues', label: 'Fee Dues', description: 'Outstanding fee dues', icon: ICONS.check, action: go('/fees/dues'), keywords: ['outstanding'] },
    ],
  ],
  [
    '/school-finance',
    (go) => [
      { id: 'ctx-rec-reconciliation', label: 'Reconciliation', description: 'Reconcile receipts and payments', icon: ICONS.check, action: go('/school-finance/reconciliation'), keywords: ['match'] },
      { id: 'ctx-rec-receipts', label: 'Receipts', description: 'Browse receipts', icon: ICONS.bank, action: go('/school-finance/receipts'), keywords: ['receipt'] },
      { id: 'ctx-rec-transactions', label: 'Transactions', description: 'View all transactions', icon: ICONS.chart, action: go('/school-finance/transactions'), keywords: ['ledger'] },
      { id: 'ctx-rec-outstanding', label: 'Outstanding Balances', description: 'Students with balances', icon: ICONS.bank, action: go('/school-finance/outstanding'), keywords: ['balance'] },
    ],
  ],
  [
    '/reports',
    (go) => [
      { id: 'ctx-report-attendance', label: 'Attendance Report', description: 'Generate an attendance report', icon: ICONS.chart, action: go('/reports/attendance'), keywords: ['attendance'] },
      { id: 'ctx-report-fee-collection', label: 'Fee Collection Report', description: 'Generate a fee collection report', icon: ICONS.bank, action: go('/reports/fees/collection'), keywords: ['fees', 'collection'] },
      { id: 'ctx-report-outstanding', label: 'Outstanding Report', description: 'Generate an outstanding report', icon: ICONS.check, action: go('/reports/fees/outstanding'), keywords: ['outstanding'] },
      { id: 'ctx-report-builder', label: 'Report Builder', description: 'Build a custom report', icon: ICONS.book, action: go('/reports/builder'), keywords: ['custom', 'build'] },
    ],
  ],
  [
    '/analytics',
    (go) => [
      { id: 'ctx-analytics-attendance', label: 'Attendance Analytics', description: 'Attendance trends and insights', icon: ICONS.chart, action: go('/analytics/attendance'), keywords: ['trend'] },
      { id: 'ctx-analytics-finance', label: 'Finance Analytics', description: 'Financial trends and insights', icon: ICONS.bank, action: go('/analytics/finance'), keywords: ['revenue'] },
      { id: 'ctx-analytics-students', label: 'Student Analytics', description: 'Student cohort insights', icon: ICONS.users, action: go('/analytics/students'), keywords: ['cohort'] },
    ],
  ],
  [
    '/operations',
    (go) => [
      { id: 'ctx-op-export-students', label: 'Export Students', description: 'Student data export', icon: ICONS.export, action: go('/operations/export/students'), keywords: ['csv'] },
      { id: 'ctx-op-export-attendance', label: 'Export Attendance', description: 'Attendance data export', icon: ICONS.export, action: go('/operations/export/attendance'), keywords: ['csv'] },
      { id: 'ctx-op-export-payments', label: 'Export Payments', description: 'Payment data export', icon: ICONS.export, action: go('/operations/export/payments'), keywords: ['csv'] },
      { id: 'ctx-op-rollover', label: 'Academic Rollover', description: 'Roll the school year over', icon: ICONS.calendar, action: go('/operations/rollover'), keywords: ['year'] },
    ],
  ],
  [
    '/communications',
    (go) => [
      { id: 'ctx-comm-compose', label: 'Compose Message', description: 'Write a message or announcement', icon: ICONS.mail, action: go('/communications/compose'), keywords: ['email', 'sms', 'write'] },
      { id: 'ctx-comm-templates', label: 'Message Templates', description: 'Manage message templates', icon: ICONS.book, action: go('/communications/templates'), keywords: ['template'] },
      { id: 'ctx-comm-sent', label: 'Sent Messages', description: 'Message history', icon: ICONS.mail, action: go('/communications/sent'), keywords: ['history'] },
    ],
  ],
  [
    '/leave',
    (go) => [
      { id: 'ctx-leave-new', label: 'New Leave Request', description: 'File a leave request', icon: ICONS.add, action: go('/leave/new'), keywords: ['time off'] },
    ],
  ],
  [
    '/admissions',
    (go) => [
      { id: 'ctx-admission-inquiry', label: 'New Inquiry', description: 'Register an admission inquiry', icon: ICONS.add, action: go('/admissions/new'), keywords: ['inquiry', 'apply'] },
      { id: 'ctx-admission-applications', label: 'Applications', description: 'Browse admission applications', icon: ICONS.users, action: go('/admissions/applications'), keywords: ['applicants'] },
    ],
  ],
  [
    '/work',
    (go) => [
      { id: 'ctx-work-my', label: 'My Work', description: 'Cases assigned to you', icon: ICONS.users, action: go('/work?view=my'), keywords: ['mine', 'assigned', 'my work'] },
      { id: 'ctx-work-open', label: 'All Open Cases', description: 'Every case awaiting action', icon: ICONS.chart, action: go('/work?status=open'), keywords: ['open', 'pending'] },
      { id: 'ctx-work-overdue', label: 'Overdue Cases', description: 'Cases past their due date', icon: ICONS.check, action: go('/work?view=overdue'), keywords: ['sla', 'late', 'overdue'] },
      { id: 'ctx-work-unassigned', label: 'Unassigned Cases', description: 'Cases no one owns yet', icon: ICONS.book, action: go('/work?view=unassigned'), keywords: ['unowned', 'assign'] },
    ],
  ],
  [
    '/action-center',
    (go) => [
      { id: 'ctx-action-resolve', label: 'Resolve Open Actions', description: 'Resolve open risk findings from the Action Center', icon: ICONS.check, action: go('/action-center?status=open'), keywords: ['resolve', 'attention'] },
      { id: 'ctx-action-critical', label: 'Critical Actions', description: 'Only critical-severity actions', icon: ICONS.check, action: go('/action-center?tab=critical'), keywords: ['critical', 'urgent'] },
      { id: 'ctx-action-finance', label: 'Financial Actions', description: 'Fees, payments and financial attention items', icon: ICONS.bank, action: go('/action-center?tab=financial'), keywords: ['fees', 'payments', 'money'] },
      { id: 'ctx-action-risk', label: 'Open Risk Center', description: 'Full risk engine with rule configuration', icon: ICONS.chart, action: go('/risk'), keywords: ['risk', 'findings'] },
    ],
  ],
  [
    '/data-quality',
    (go) => [
      { id: 'ctx-dq-duplicates', label: 'Duplicate Records', description: 'Filter to duplicate student / payment findings', icon: ICONS.users, action: go('/data-quality?category=duplicates'), keywords: ['duplicates', 'copies'] },
      { id: 'ctx-dq-missing', label: 'Missing Fields', description: 'Students missing guardians or contact data', icon: ICONS.check, action: go('/data-quality?category=missing_fields'), keywords: ['missing', 'incomplete'] },
      { id: 'ctx-dq-invalid', label: 'Invalid Records', description: 'Malformed emails, impossible dates, bad references', icon: ICONS.chart, action: go('/data-quality?category=invalid_format'), keywords: ['invalid', 'formats'] },
      { id: 'ctx-dq-critical', label: 'Critical Findings', description: 'Only critical-severity data quality issues', icon: ICONS.check, action: go('/data-quality?severity=critical'), keywords: ['critical', 'urgent'] },
    ],
  ],
  [
    '/student',
    (go) => [
      { id: 'ctx-stu-timetable', label: 'My Timetable', description: 'View your class schedule', icon: ICONS.calendar, action: go('/student/timetable'), keywords: ['schedule'] },
      { id: 'ctx-stu-attendance', label: 'My Attendance', description: 'View your attendance record', icon: ICONS.check, action: go('/student/attendance'), keywords: ['present'] },
      { id: 'ctx-stu-results', label: 'My Results', description: 'View your results', icon: ICONS.chart, action: go('/student/results'), keywords: ['grades'] },
    ],
  ],
  [
    '/parent',
    (go) => [
      { id: 'ctx-par-children', label: 'My Children', description: 'View your children', icon: ICONS.users, action: go('/parent/children'), keywords: ['kids'] },
      { id: 'ctx-par-attendance', label: 'Children Attendance', description: 'Attendance for your children', icon: ICONS.check, action: go('/parent/attendance'), keywords: ['present'] },
      { id: 'ctx-par-fees', label: 'Fees & Payments', description: 'Payments for your children', icon: ICONS.bank, action: go('/parent/fees'), keywords: ['pay'] },
    ],
  ],
]

/**
 * Resolve route-aware commands for a path. Exact match wins; otherwise the
 * longest matching prefix (detail pages inherit their section's commands).
 */
export function buildContextualCommands(path: string, navigate: (to: string) => void): ContextCommand[] {
  const go: Go = (to) => () => navigate(to)

  const exact = ROUTE_COMMANDS.find(([route]) => path === route)
  if (exact) return exact[1](go)

  let best: [string, (go: Go) => ContextCommand[]] | null = null
  for (const entry of ROUTE_COMMANDS) {
    const [route] = entry
    if (path.startsWith(`${route}/`) && (!best || route.length > best[0].length)) {
      best = entry
    }
  }
  return best ? best[1](go) : []
}

/** Source record for the palette's "Recent" group (see useNavPersistence). */
export interface RecentCommandSource {
  path: string
  label: string
}

const MAX_RECENT_COMMANDS = 6

/**
 * Build the palette's "Recent" group (P8 §9) from visited-page history.
 * The current route is excluded (the shell already shows it), and the list
 * is capped to keep the surface scannable. Pure and unit-testable.
 */
export function buildRecentCommands(
  recentItems: RecentCommandSource[],
  currentPath: string,
  navigate: (to: string) => void
): ContextCommand[] {
  return recentItems
    .filter((item) => item.path !== currentPath)
    .slice(0, MAX_RECENT_COMMANDS)
    // No per-row description: the group label already says "Recent", and a
    // repeated caption under every row would only add noise (§19 dense,
    // not cluttered).
    .map((item) => ({
      id: `recent-${item.path}`,
      label: item.label,
      icon: ICONS.recent,
      action: () => navigate(item.path),
      keywords: ['recent', 'history', item.label],
    }))
}
