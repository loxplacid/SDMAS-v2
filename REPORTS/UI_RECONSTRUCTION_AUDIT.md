# SDMAS v2 — UI Reconstruction Audit

> **Date:** August 19, 2026
> **Auditor:** Buffy (Lead Product Designer + Principal Frontend Architect)
> **Status:** Phase 0 Complete — Findings and Recommendations

---

## 1. Current Frontend Architecture

| Aspect | Detail |
|--------|--------|
| Framework | React 19 + TypeScript 5.7 |
| Bundler | Vite 6 |
| Styling | Tailwind CSS 4 with CSS custom properties design system |
| Router | React Router DOM 7 (lazy-loaded routes) |
| State | Component-local state (no global store) |
| Animation | `motion` (Framer Motion successor) + custom FLIP engine + animejs |
| Charts | Recharts 3.10 |
| Search | Fuse.js + SQLite WASM (FTS5) local index |
| PWA | vite-plugin-pwa |
| Testing | Vitest 3.2 + Testing Library |
| API | Custom fetch client with JWT refresh, request deduplication |

### Component Architecture
- **UI Primitives:** 36 components in `components/ui/` (Button, Modal, Table, Card, Badge, etc.)
- **Layout:** AppLayout → Sidebar + Header + Outlet pattern
- **Table System:** Advanced DataTable with filter rail, FLIP animations, density control, keyboard nav, selection, saved views
- **Data Workspace:** Higher-level abstraction wrapping DataTable + FilterRail + Inspector pattern
- **Motion:** Custom motion system with tokens, tiers (efficient/minimal/precise), presence, reveal, flip

### Route Count: ~80+ routes
### Role Count: 7 (admin, principal, accountant, staff, teacher, student, parent)

---

## 2. Every Route/Page

### Auth
| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/login` | LoginPage | ✅ Working | Full login form with validation |
| `*` (catch-all) | → `/dashboard` | ✅ Working | Redirects to dashboard |

### Command Center / Dashboards
| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/dashboard` | DashboardPage | ⚠️ Partial | Gradient hero, mixes Command Center + Analytics data |
| `/command-center` | CommandCenterPage | ✅ Working | Best page in app — real API, sparklines, alerts, workflow |
| `/admin` | — | ❌ Missing | No admin dashboard exists |

### Role-Specific Dashboards
| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/teacher` | TeacherDashboardPage | ⚠️ Partial | Gradient hero, basic stats |
| `/student` | StudentDashboardPage | ⚠️ Partial | Gradient hero, basic stats |
| `/parent` | ParentDashboardPage | ⚠️ Partial | Gradient hero, basic stats |
| `/principal` | PrincipalDashboardPage | ⚠️ Partial | Gradient hero, basic stats |
| `/accountant` | AccountantDashboardPage | ⚠️ Partial | Gradient hero, basic stats |
| `/staff` | StaffDashboardPage | ⚠️ Partial | Gradient hero, basic stats |

### Students
| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/students` | StudentListPage | ✅ Working | DataWorkspace + inspector, CRUD, export, bulk delete |
| `/students/:id` | StudentDetailPage | ✅ Working | Real API, skeleton + error states |
| `/students/:id/360` | Student360Page | ✅ Working | Real API |

### Teachers
| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/teachers` | TeacherListPage | ✅ Working | Real API |
| `/teachers/:id` | TeacherDetailPage | ✅ Working | Real API |
| `/teachers/:id/360` | Teacher360Page | ✅ Working | Real API |

### Academic
| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/academic` | AcademicPage | ⚠️ Navigation hub only | Gradient card navigation |
| `/academic/years` | AcademicYearListPage | ✅ Working | Real API |
| `/academic/years/:id` | AcademicYearDetailPage | ✅ Working | Real API |
| `/academic/classes` | ClassListPage | ✅ Working | Real API |
| `/academic/classes/:id/360` | Class360Page | ✅ Working | Real API |
| `/academic/sections` | SectionListPage | ✅ Working | Real API |
| `/academic/enrollments` | EnrollmentListPage | ✅ Working | Real API |
| `/academic/terms` | TermListPage | ✅ Working | Real API |
| `/academic/assignments` | TeacherAssignmentListPage | ✅ Working | Real API |

### Subjects
| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/subjects` | SubjectListPage | ✅ Working | Real API |

### Attendance
| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/attendance` | AttendancePage | ⚠️ Navigation hub only | Gradient card navigation |
| `/attendance/records` | AttendanceRecordsPage | ✅ Working | DataWorkspace, server-paginated |
| `/attendance/records/:id` | AttendanceRecordDetailPage | ✅ Working | Real API |
| `/attendance/record` | RecordAttendancePage | ✅ Working | Real API |
| `/attendance/daily` | DailyAttendancePage | ✅ Working | Real API |
| `/attendance/student` | StudentAttendancePage | ✅ Working | Real API |
| `/attendance/section` | SectionAttendancePage | ✅ Working | Real API |
| `/attendance-intelligence` | AttendanceIntelligencePage | ⚠️ Navigation hub | Gradient card navigation |
| `/attendance-intelligence/dashboard` | AttendanceIntelligenceDashboardPage | ✅ Working | Real API |
| `/attendance-intelligence/period` | PeriodAttendancePage | ✅ Working | Real API |
| `/attendance-intelligence/corrections` | AttendanceCorrectionsPage | ✅ Working | Real API |
| `/attendance-intelligence/thresholds` | AttendanceThresholdsPage | ✅ Working | Real API |

### Fees
| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/fees` | FeesPage | ⚠️ Navigation hub only | Gradient card navigation |
| `/fees/fee-types` | FeeTypeListPage | ✅ Working | Real API, but uses `confirm()` |
| `/fees/structures` | FeeStructureListPage | ✅ Working | Real API |
| `/fees/student-fees` | StudentFeesPage | ✅ Working | Real API |
| `/fees/dues` | FeeDueListPage | ✅ Working | Real API |
| `/fees/payments` | PaymentListPage | ✅ Working | Real API |
| `/fees/summary` | FinancialSummaryPage | ✅ Working | Real API |

### School Finance
| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/school-finance` | SchoolFinancePage | ⚠️ Navigation hub | Gradient card navigation |
| `/school-finance/dashboard` | SchoolFinanceDashboardPage | ✅ Working | Real API, gradient hero |
| `/school-finance/fee-schedules` | FeeSchedulesPage | ✅ Working | Real API |
| `/school-finance/reconciliation` | ReconciliationPage | ✅ Working | Real API |
| `/school-finance/receipts` | ReceiptsPage | ✅ Working | Real API |
| `/school-finance/transactions` | TransactionsPage | ✅ Working | Real API |
| `/school-finance/outstanding` | OutstandingBalancesPage | ✅ Working | Real API |
| `/school-finance/reports` | FinanceReportsPage | ✅ Working | Real API |
| `/school-finance/exceptions` | FinancialExceptionsPage | ✅ Working | Real API |

### Reports
| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/reports` | ReportsHubPage | ⚠️ Navigation hub | Gradient card navigation |
| `/reports/cards` | ReportCardsPage | ✅ Working | Real API |
| `/reports/attendance` | AttendanceReportPage | ✅ Working | Real API |
| `/reports/fees/collection` | FeeCollectionReportPage | ✅ Working | Real API |
| `/reports/fees/outstanding` | OutstandingReportPage | ✅ Working | Real API |
| `/reports/receipts` | ReceiptLookupPage | ✅ Working | Real API |
| `/reports/builder` | ReportBuilderHubPage | ⚠️ Navigation | Gradient card navigation |
| `/reports/builder/new` | ReportBuilderWorkspace | ✅ Working | Real API |
| `/reports/builder/exports` | ExportJobsPage | ✅ Working | Real API |
| `/reports/builder/saved` | SavedReportsPage | ✅ Working | Real API |

### Analytics
| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/analytics` | AnalyticsHubPage | ⚠️ Navigation hub | Gradient card navigation |
| `/analytics/attendance` | AttendanceAnalyticsPage | ✅ Working | Real API + Recharts |
| `/analytics/finance` | FinanceAnalyticsPage | ✅ Working | Real API + Recharts |
| `/analytics/students` | StudentAnalyticsPage | ✅ Working | Real API + Recharts |
| `/analytics/academic` | AcademicAnalyticsPage | ✅ Working | Real API + Recharts |

### Operations
| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/operations` | OperationsHubPage | ⚠️ Navigation hub | Gradient card navigation |
| `/operations/export/students` | StudentExportPage | ✅ Working | Real API |
| `/operations/export/attendance` | AttendanceExportPage | ✅ Working | Real API |
| `/operations/export/payments` | PaymentExportPage | ✅ Working | Real API |
| `/operations/rollover` | RolloverPage | ✅ Working | Real API |
| `/operations/batch/enroll` | BatchEnrollPage | ✅ Working | Real API |
| `/operations/batch/fee-dues` | BatchFeeDuesPage | ✅ Working | Real API |

### Intelligence
| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/risk` | RiskCenterPage | ✅ Working | Real API, gradient hero |
| `/data-quality` | DataQualityCenterPage | ✅ Working | Real API, gradient hero |
| `/action-center` | ActionCenterPage | ✅ Working | Real API, gradient hero |
| `/work` | WorkQueuePage | ✅ Working | Real API, gradient hero |
| `/cases/:id` | CaseDetailPage | ✅ Working | Real API |
| `/timeline` | TimelinePage | ✅ Working | Real API |

### Notifications
| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/notifications` | NotificationsPage | ✅ Working | Real API |

### Communications
| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/communications` | CommunicationsHubPage | ⚠️ Navigation hub | Gradient card navigation |
| `/communications/compose` | ComposerPage | ✅ Working | Real API |
| `/communications/templates` | TemplatesPage | ✅ Working | Real API, uses `window.confirm()` |
| `/communications/sent` | SentMessagesPage | ✅ Working | Real API |

### Leave
| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/leave` | LeaveListPage | ✅ Working | Real API |
| `/leave/new` | NewLeavePage | ✅ Working | Real API |
| `/leave/:id` | LeaveDetailPage | ✅ Working | Real API |

### Admissions
| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/admissions` | AdmissionsPage | ⚠️ Navigation hub | Gradient card navigation |
| `/admissions/applications` | ApplicationListPage | ✅ Working | Real API |
| `/admissions/new` | NewInquiryPage | ✅ Working | Real API |
| `/admissions/merit-list` | MeritListPage | ✅ Working | Real API |
| `/admissions/:id` | ApplicationDetailPage | ✅ Working | Real API |

### Admin
| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/admin/audit-logs` | AuditLogViewerPage | ⚠️ Partial | Real API, uses legacy Table |
| `/admin/approvals` | ApprovalInboxPage | ✅ Working | Real API |
| `/users` | UserListPage | ⚠️ Partial | Real API, role filter incomplete |
| `/profile` | ProfilePage | ✅ Working | Real API |

### Migration
| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/migration` | MigrationCenterPage | ✅ Working | Real API |
| `/migration/new` | MigrationWizardPage | ✅ Working | Real API |
| `/migration/:id` | MigrationWizardPage | ✅ Working | Real API |

### Workflow
| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/workflow` | ApprovalInboxPage | ✅ Working | Real API |

### Parent Portal
| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/parent` | ParentDashboardPage | ⚠️ Partial | Gradient hero |
| `/parent/children` | ParentChildrenPage | ✅ Working | Real API |
| `/parent/attendance` | ParentAttendancePage | ✅ Working | Real API |
| `/parent/fees` | ParentFeesPage | ✅ Working | Real API |
| `/parent/academic` | ParentAcademicPage | ✅ Working | Real API |
| `/parent/announcements` | ParentAnnouncementsPage | ✅ Working | Real API |
| `/parent/documents` | ParentDocumentsPage | ✅ Working | Real API |
| `/parent/messages` | ParentCommunicationPage | ✅ Working | Real API |

### Student Portal
| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/student` | StudentDashboardPage | ⚠️ Partial | Gradient hero |
| `/student/timetable` | StudentTimetablePage | ✅ Working | Real API |
| `/student/attendance` | StudentPortalAttendancePage | ✅ Working | Real API |
| `/student/subjects` | StudentSubjectsPage | ✅ Working | Real API |
| `/student/results` | StudentResultsPage | ✅ Working | Real API |
| `/student/assignments` | StudentAssignmentsPage | ✅ Working | Real API |
| `/student/announcements` | StudentAnnouncementsPage | ✅ Working | Real API |
| `/student/documents` | StudentDocumentsPage | ✅ Working | Real API |

---

## 3. Every Navigation Item (Admin Role)

Current admin nav is flat with 24 items, no grouping:

1. Command Center
2. Action Center
3. Risk Center
4. Data Quality
5. Work Queue
6. Timeline
7. Leave
8. Admissions
9. Students
10. Teachers
11. Academics
12. Attendance
13. Fees
14. Subjects
15. Communications
16. Reports
17. Report Cards
18. Analytics
19. Notifications
20. Data Ops
21. Data Migration
22. Users
23. Audit Logs
24. Approvals

**Issues:**
- No section grouping in sidebar (sidebar does group, but sections are: Overview, Records, Operations, System — missing Finance and Intelligence sections)
- "Data Ops" is vague
- "Report Cards" is a sub-page of Reports but shown as separate top-level nav
- No Admin Dashboard link

---

## 4. Every API Integration

### Backend API Routers (30+ routers)
auth, admin, student, student_lifecycle, academic, attendance, attendance_intelligence, fees, notifications, push, analytics, reports, report_cards, institution, admission, workflow, leave, audit_export, audit, student_360, class_360, teacher_360, academic_ops, school_finance, report_builder, documents, communications, parent, search, student_portal, cases, data_quality, risk, command_center, timeline, process_mining, compliance, events, exceptions, ledger, billing, jobs, optimization, simulation

### Frontend API Clients (30+ modules)
auth, command-center, risk, cases, data-quality, timeline, student, student-360, class-360, teacher-360, academic (year, class, section, enrollment, term, subject, teacher, teacher-assignment), attendance, attendance-intelligence, fees (type, structure, due, payment, summary), school-finance (dashboard, payment-method, fee-schedule, transaction-log, reconciliation, receipt, outstanding-balance, finance-report), reports, report-builder, analytics (overview, attendance, finance, student, academic), notifications, audit, search

**Assessment:** Nearly every frontend page has a real API client. The API integration is **comprehensive**.

---

## 5. Every Broken Page

| Page | Issue |
|------|-------|
| `/admin` | Route does not exist — needs to be created |
| Fee Type List | Uses `window.confirm()` for deactivation instead of ConfirmDialog |
| Communications Templates | Uses `window.confirm()` for delete |
| Migration Wizard | Uses `window.confirm()` for rollback |
| Audit Log Viewer | Uses legacy Table component instead of DataTable/DataWorkspace |
| User List | Role filter only shows "admin" and "staff" (missing 5 roles) |
| Dashboard (`/dashboard`) | Duplicate of Command Center — should redirect or differentiate |
| Student Detail | Edit button navigates to `/students/:id/edit` which doesn't exist |

---

## 6. Every Incomplete Page

| Page | Issue |
|------|-------|
| Dashboard | Overlaps with Command Center; gradient hero too generic |
| 7 Hub Pages (academic, attendance, fees, reports, analytics, operations, communications, admissions, school-finance, report-builder) | ALL are simple gradient-card navigation pages with no data — just link cards |
| 7 Role Dashboards | All use same pattern: gradient hero + basic stats cards |
| Student Detail | Missing edit route — links to non-existent `/students/:id/edit` |
| Login | Has decorative gradient orbs — "AI dashboard" aesthetic |

---

## 7. Every Fake/Mock/Static Implementation

| Location | Issue |
|----------|-------|
| Analytics Hub | Pure navigation — no data |
| Reports Hub | Pure navigation — no data |
| Fees Hub | Pure navigation — no data |
| Attendance Hub | Pure navigation — no data |
| Operations Hub | Pure navigation — no data |
| Academic Hub | Pure navigation — no data |
| Communications Hub | Pure navigation — no data |
| Admissions Hub | Pure navigation — no data |
| School Finance Hub | Pure navigation — no data |
| Report Builder Hub | Pure navigation — no data |
| User List role filter | Only shows 2 of 7 roles |
| Student Detail edit link | Points to non-existent route |

**Note:** No pages use fabricated API responses or fake data arrays. The codebase is notably clean of mock data.

---

## 8. Every Console/Runtime Error

- `communications/composer.tsx:70` — `catch(console.error)` — should use toast
- No other console.log/warn/error found in pages

---

## 9. Every TypeScript Issue

TypeScript check timed out (>60s). This indicates either:
- Complex type inference chains
- Large type unions
- Potentially type errors that slow compilation

**Action needed:** Run `tsc --noEmit` with extended timeout to capture errors.

---

## 10. Every Broken Interaction

| Interaction | Issue |
|-------------|-------|
| Student Detail "Edit" button | Navigates to `/students/:id/edit` — route doesn't exist |
| Fee Type "Deactivate" | Uses `window.confirm()` — ugly, non-enterprise |
| Template delete | Uses `window.confirm()` |
| Migration rollback | Uses `window.confirm()` |
| User List role filter | Missing 5 of 7 roles in dropdown |
| `window.location.href = '/profile'` in header dropdown | Should use `navigate()` |

---

## 11. Every Inconsistent Component

| Issue | Location |
|-------|----------|
| Hub pages all use same gradient-card pattern | 10+ pages |
| Dashboard heroes all use gradient + grid overlay | 7+ pages |
| Some pages use DataTable, others legacy Table | Audit Log uses legacy, Students use DataTable |
| Some pages use DataWorkspace, others manual Table+Pagination | Inconsistent data presentation |
| Loading states vary: some use Skeleton, some use pulse divs, some use Loading component | No standard |
| Error states: some use ErrorState component, some inline | No standard |
| Empty states: some use EmptyState component, some inline | No standard |
| `window.confirm()` vs ConfirmDialog | 3 pages use confirm() |

---

## 12. Every Accessibility Issue

| Issue | Severity |
|-------|----------|
| Hub page gradient icons lack alt text | Medium |
| Sparkline SVGs lack meaningful aria-label | Low |
| Command palette keyboard navigation | Needs audit |
| Dialog focus trapping | Needs audit |
| Table keyboard navigation only on some tables | Inconsistent |
| Mobile hamburger menu aria-label present | ✅ Good |
| Focus-visible styles defined in CSS | ✅ Good |
| `prefers-reduced-motion` handled in CSS | ✅ Good |

---

## 13. Every Responsive Issue

| Issue | Location |
|-------|----------|
| Tables hide columns on mobile but don't adapt layout | All table pages |
| Dashboard grids use `grid-cols-2 sm:grid-cols-3 xl:grid-cols-6` | OK but metric cards may be too small on tablets |
| Hub page card grids | `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3` — reasonable |
| Sidebar: desktop hover-expand + mobile drawer | ✅ Good |
| Header: mobile hamburger + search icon | ✅ Good |
| Command palette | No mobile-adapted layout |
| Charts | May overflow on small screens |
| Detail pages | No mobile-specific layout adjustments |

---

## 14. Every Performance Problem

| Issue | Severity |
|-------|----------|
| Student list fetches 10,000 records at once | High — should use server pagination |
| No code splitting beyond route-level lazy loading | Medium |
| animejs imported alongside motion | Bundle bloat — two animation libraries |
| sqlite-wasm imported globally | Large WASM module |
| No virtualization for large lists | Medium — tables with many rows |
| Request deduplication implemented | ✅ Good |
| Lazy route loading implemented | ✅ Good |

---

## 15. Every Visual Inconsistency

| Issue | Count |
|-------|-------|
| Gradient hero sections (navy + grid pattern) | 7+ pages |
| Gradient icon cards (rainbow colored, scale on hover) | 10+ hub pages |
| Inconsistent border-radius (rounded-xl vs rounded-2xl vs rounded-2xl) | Throughout |
| Inconsistent card padding | Some p-4, some p-6, some p-8 |
| Gradient text (`bg-gradient-to-br ... bg-clip-text`) | 3 pages |
| Backdrop blur usage | 1 instance (workflow approval overlay) |
| Inconsistent button sizing | Some size="sm", some default |
| Inconsistent section headers | Some use h2, some h3, some text-base, some text-lg |

---

## 16. Every Page That Needs Redesign

### HIGH PRIORITY (Structural)
1. **Admin Dashboard** — Must be created from scratch
2. **Command Center** — Needs visual tightening (hero too large, metrics grid dense but sections below less so)
3. **All Hub Pages (10+)** — Currently just gradient card navigation; need real data previews
4. **All Role Dashboards (7)** — All follow same generic gradient pattern

### MEDIUM PRIORITY (Visual)
5. **Login Page** — Decorative gradient orbs, needs enterprise treatment
6. **Audit Log Viewer** — Uses legacy Table, needs DataTable migration
7. **User List** — Incomplete role filter, needs DataTable migration
8. **Student Detail** — Broken edit link, needs polish
9. **All 360° Views** — Gradient avatar circles, needs refinement

### LOW PRIORITY (Polish)
10. **Analytics Pages** — Charts functional but hub is empty
11. **Reports Pages** — Functional but hub is empty
12. **Finance Pages** — Functional but hub is empty

---

## 17. Missing Admin Functionality

| Missing | Priority |
|---------|----------|
| Admin Dashboard (`/admin` route) | Critical |
| System overview (orgs, campuses, users, sessions, health) | Critical |
| User management overview (counts, role distribution) | High |
| Access control overview (roles, permissions, privileged users) | High |
| Operational health (failed jobs, queues, notifications) | High |
| Security overview (logins, failures, suspicious activity) | High |
| Tenancy overview (orgs, campuses, config status) | High |
| System activity (recent actions, jobs, migrations) | Medium |

---

## 18. Missing Loading/Error/Empty States

| Page | Missing State |
|------|---------------|
| Dashboard | ✅ Has loading + error |
| Command Center | ✅ Has loading + error + empty |
| Student List | ✅ Has loading + error + empty (via DataWorkspace) |
| Fee Type List | ✅ Has loading + error |
| User List | ✅ Has loading + error |
| Audit Log Viewer | ✅ Has loading + error |
| Hub Pages | ❌ No states (pure navigation) |
| Role Dashboards | ⚠️ Partial — some have loading, some don't |
| Analytics Pages | ⚠️ Varies |
| Report Pages | ⚠️ Varies |
| Student Detail | ✅ Has loading + error |

---

## 19. Missing Permission Handling

| Issue | Location |
|-------|----------|
| Hub pages don't check permissions before showing links | All hub pages |
| Some nav items shown to roles that can't access them | Needs audit |
| Delete buttons not permission-gated on some pages | Fee type deactivation |
| Create buttons not permission-gated on some pages | Various |

---

## 20. Recommended Implementation Order

### Phase 1: Design System Foundation (Days 1-2)
1. Audit and refine CSS custom properties
2. Eliminate gradient-icon-card pattern from hub pages
3. Establish consistent component tokens
4. Remove animejs dependency (use motion exclusively)

### Phase 2: Application Shell (Days 2-3)
1. Rebuild sidebar with proper section hierarchy
2. Rebuild header with enterprise density
3. Add Admin Dashboard route and page
4. Fix mobile navigation

### Phase 3: Core Infrastructure (Days 3-5)
1. Migrate all pages to DataTable system
2. Standardize loading/error/empty states
3. Replace all `window.confirm()` with ConfirmDialog
4. Fix broken routes (student edit, admin dashboard)

### Phase 4: Hub Page Transformation (Days 5-7)
1. Convert all hub pages from gradient-card navigation to data-rich overview pages
2. Each hub should show: key metrics, recent items, quick actions

### Phase 5: Dashboard Redesign (Days 7-9)
1. Redesign all 7 role dashboards
2. Tighten Command Center visual density
3. Create Admin Dashboard with real data

### Phase 6: Page-by-Page Polish (Days 9-14)
1. Login page enterprise treatment
2. Student/Teacher detail pages
3. 360° views
4. All form pages
5. All report pages

### Phase 7: Responsive + A11y + Performance (Days 14-16)
1. Mobile table behavior
2. Keyboard navigation audit
3. Bundle optimization
4. Remove dead code

### Phase 8: Visual Consistency Pass (Days 16-17)
1. Typography audit
2. Spacing audit
3. Border/radius audit
4. Animation timing audit
5. Shadow audit

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| Total Routes | ~80+ |
| Working Routes (API-backed) | ~70 |
| Broken Routes | 2 (admin dashboard missing, student edit missing) |
| Navigation Hub Pages (empty) | 10+ |
| Gradient Hero Sections | 7+ |
| Gradient Icon Card Patterns | 10+ |
| `window.confirm()` Usage | 3 |
| Legacy Table Usage | 1 (audit log) |
| Role Dashboards (generic) | 7 |
| Missing Permission Gates | Multiple |
| Missing Loading States | ~5 pages |
| Missing Error States | ~5 pages |
| Missing Empty States | ~10 pages |

---

## Key Architectural Strengths (Preserve)

1. **API integration is comprehensive** — nearly every page has real backend support
2. **DataTable system is mature** — filter rail, FLIP animations, density, keyboard nav, saved views
3. **RBAC is well-structured** — role-based nav, permission constants, RoleGuard, Can component
4. **Motion system is sophisticated** — tiered, token-based, respects prefers-reduced-motion
5. **Design tokens are thorough** — 200+ CSS custom properties for colors, spacing, typography, shadows, motion
6. **Request deduplication** — inflight request map prevents duplicate API calls
7. **JWT refresh** — automatic token refresh with proper error handling
8. **Lazy loading** — all routes lazy-loaded with Suspense

## Key Architectural Weaknesses (Fix)

1. **No global state management** — every component manages its own loading/error/data
2. **Two animation libraries** — animejs + motion (bundle bloat)
3. **Hub pages are empty** — 10+ pages are just navigation cards with no data
4. **No admin dashboard** — critical missing feature
5. **Visual consistency** — gradient heroes and rainbow icon cards repeated everywhere
6. **`window.confirm()`** — 3 places using browser dialogs
7. **Inconsistent data table patterns** — some pages use DataTable, others legacy Table
