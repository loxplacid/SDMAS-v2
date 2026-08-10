import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './api/auth/auth-context'
import { ToastProvider } from './components/ui/toast'
import { DelightProvider } from './components/delight/delight-provider'
import { MotionProvider } from './lib/motion/motion-config'
import { ProtectedRoute } from './components/protected-route'
import { RoleGuard } from './components/auth/role-guard'
import { AppLayout } from './components/layout'

// ── Lazy-loaded page components ──

// Login (outside main layout)
const LoginPage = lazy(() => import('./pages/login').then((m) => ({ default: m.LoginPage })))

// Dashboard
const DashboardPage = lazy(() => import('./pages/dashboard').then((m) => ({ default: m.DashboardPage })))

// Command Center (primary leadership landing)
const CommandCenterPage = lazy(() => import('./pages/command-center/command-center').then((m) => ({ default: m.CommandCenterPage })))

// Risk & Attention Engine
const RiskCenterPage = lazy(() => import('./pages/risk/risk-center').then((m) => ({ default: m.RiskCenterPage })))

// Action Center
const ActionCenterPage = lazy(() => import('./pages/action-center/action-center').then((m) => ({ default: m.ActionCenterPage })))

// Data Quality Center
const DataQualityCenterPage = lazy(() => import('./pages/data-quality/data-quality').then((m) => ({ default: m.DataQualityCenterPage })))

// Operational Work Queue + Case Detail (P8)
const WorkQueuePage = lazy(() => import('./pages/work/work-queue').then((m) => ({ default: m.WorkQueuePage })))
const CaseDetailPage = lazy(() => import('./pages/cases/case-detail').then((m) => ({ default: m.CaseDetailPage })))

// Unified Operational Timeline
const TimelinePage = lazy(() => import('./pages/timeline/timeline-page').then((m) => ({ default: m.TimelinePage })))

// Students
const StudentListPage = lazy(() => import('./pages/students/student-list').then((m) => ({ default: m.StudentListPage })))
const StudentDetailPage = lazy(() => import('./pages/students/student-detail').then((m) => ({ default: m.StudentDetailPage })))
const Student360Page = lazy(() => import('./pages/students/student-360').then((m) => ({ default: m.Student360Page })))

// Academic
const AcademicPage = lazy(() => import('./pages/academic').then((m) => ({ default: m.AcademicPage })))
const AcademicYearListPage = lazy(() => import('./pages/academic/academic-year-list').then((m) => ({ default: m.AcademicYearListPage })))
const AcademicYearDetailPage = lazy(() => import('./pages/academic/academic-year-detail').then((m) => ({ default: m.AcademicYearDetailPage })))
const ClassListPage = lazy(() => import('./pages/academic/class-list').then((m) => ({ default: m.ClassListPage })))
const Class360Page = lazy(() => import('./pages/academic/class-360').then((m) => ({ default: m.Class360Page })))
const SectionListPage = lazy(() => import('./pages/academic/section-list').then((m) => ({ default: m.SectionListPage })))
const EnrollmentListPage = lazy(() => import('./pages/academic/enrollment-list').then((m) => ({ default: m.EnrollmentListPage })))
const TermListPage = lazy(() => import('./pages/academic/term-list').then((m) => ({ default: m.TermListPage })))
const TeacherAssignmentListPage = lazy(() => import('./pages/academic/teacher-assignment-list').then((m) => ({ default: m.TeacherAssignmentListPage })))

// Teachers
const TeacherListPage = lazy(() => import('./pages/teachers/teacher-list').then((m) => ({ default: m.TeacherListPage })))
const TeacherDetailPage = lazy(() => import('./pages/teachers/teacher-detail').then((m) => ({ default: m.TeacherDetailPage })))
const Teacher360Page = lazy(() => import('./pages/teachers/teacher-360').then((m) => ({ default: m.Teacher360Page })))

// Subjects
const SubjectListPage = lazy(() => import('./pages/subjects/subject-list').then((m) => ({ default: m.SubjectListPage })))

// School Finance
const SchoolFinancePage = lazy(() => import('./pages/school-finance').then((m) => ({ default: m.SchoolFinancePage })))
const SchoolFinanceDashboardPage = lazy(() => import('./pages/school-finance/dashboard').then((m) => ({ default: m.SchoolFinanceDashboardPage })))
const FeeSchedulesPage = lazy(() => import('./pages/school-finance/fee-schedules').then((m) => ({ default: m.FeeSchedulesPage })))
const ReconciliationPage = lazy(() => import('./pages/school-finance/reconciliation').then((m) => ({ default: m.ReconciliationPage })))
const ReceiptsPage = lazy(() => import('./pages/school-finance/receipts').then((m) => ({ default: m.ReceiptsPage })))
const TransactionsPage = lazy(() => import('./pages/school-finance/transactions').then((m) => ({ default: m.TransactionsPage })))
const OutstandingBalancesPage = lazy(() => import('./pages/school-finance/outstanding-balances').then((m) => ({ default: m.OutstandingBalancesPage })))
const FinanceReportsPage = lazy(() => import('./pages/school-finance/reports').then((m) => ({ default: m.FinanceReportsPage })))
const FinancialExceptionsPage = lazy(() => import('./pages/school-finance/exceptions').then((m) => ({ default: m.FinancialExceptionsPage })))

// Attendance
const AttendancePage = lazy(() => import('./pages/attendance').then((m) => ({ default: m.AttendancePage })))
const AttendanceRecordsPage = lazy(() => import('./pages/attendance/attendance-records').then((m) => ({ default: m.AttendanceRecordsPage })))
const AttendanceRecordDetailPage = lazy(() => import('./pages/attendance/attendance-record-detail').then((m) => ({ default: m.AttendanceRecordDetailPage })))
const RecordAttendancePage = lazy(() => import('./pages/attendance/record-attendance').then((m) => ({ default: m.RecordAttendancePage })))
const DailyAttendancePage = lazy(() => import('./pages/attendance/daily-attendance').then((m) => ({ default: m.DailyAttendancePage })))
const StudentAttendancePage = lazy(() => import('./pages/attendance/student-attendance').then((m) => ({ default: m.StudentAttendancePage })))
const SectionAttendancePage = lazy(() => import('./pages/attendance/section-attendance').then((m) => ({ default: m.SectionAttendancePage })))
const AttendanceIntelligencePage = lazy(() => import('./pages/attendance-intelligence').then((m) => ({ default: m.AttendanceIntelligencePage })))
const AttendanceIntelligenceDashboardPage = lazy(() => import('./pages/attendance-intelligence/dashboard').then((m) => ({ default: m.AttendanceIntelligenceDashboardPage })))
const PeriodAttendancePage = lazy(() => import('./pages/attendance-intelligence/period-attendance').then((m) => ({ default: m.PeriodAttendancePage })))
const AttendanceCorrectionsPage = lazy(() => import('./pages/attendance-intelligence/corrections').then((m) => ({ default: m.AttendanceCorrectionsPage })))
const AttendanceThresholdsPage = lazy(() => import('./pages/attendance-intelligence/thresholds').then((m) => ({ default: m.AttendanceThresholdsPage })))

// Fees
const FeesPage = lazy(() => import('./pages/fees').then((m) => ({ default: m.FeesPage })))
const FeeTypeListPage = lazy(() => import('./pages/fees/fee-type-list').then((m) => ({ default: m.FeeTypeListPage })))
const FeeStructureListPage = lazy(() => import('./pages/fees/fee-structure-list').then((m) => ({ default: m.FeeStructureListPage })))
const StudentFeesPage = lazy(() => import('./pages/fees/student-fees').then((m) => ({ default: m.StudentFeesPage })))
const FeeDueListPage = lazy(() => import('./pages/fees/fee-due-list').then((m) => ({ default: m.FeeDueListPage })))
const PaymentListPage = lazy(() => import('./pages/fees/payment-list').then((m) => ({ default: m.PaymentListPage })))
const FinancialSummaryPage = lazy(() => import('./pages/fees/financial-summary').then((m) => ({ default: m.FinancialSummaryPage })))

// Users & Profile
const UserListPage = lazy(() => import('./pages/users/user-list').then((m) => ({ default: m.UserListPage })))
const ProfilePage = lazy(() => import('./pages/profile').then((m) => ({ default: m.ProfilePage })))

// Reports
const ReportsHubPage = lazy(() => import('./pages/reports/reports-hub').then((m) => ({ default: m.ReportsHubPage })))
const ReportCardsPage = lazy(() => import('./pages/report-cards/report-cards').then((m) => ({ default: m.ReportCardsPage })))

// Reports - these have default exports so simple import works
const AttendanceReportPage = lazy(() => import('./pages/reports/attendance-report'))
const FeeCollectionReportPage = lazy(() => import('./pages/reports/fee-collection-report'))
const OutstandingReportPage = lazy(() => import('./pages/reports/outstanding-report'))
const ReceiptLookupPage = lazy(() => import('./pages/reports/receipt-lookup'))

// Analytics
const AnalyticsHubPage = lazy(() => import('./pages/analytics/analytics-hub').then((m) => ({ default: m.AnalyticsHubPage })))
const AttendanceAnalyticsPage = lazy(() => import('./pages/analytics/attendance-analytics').then((m) => ({ default: m.AttendanceAnalyticsPage })))
const FinanceAnalyticsPage = lazy(() => import('./pages/analytics/finance-analytics').then((m) => ({ default: m.FinanceAnalyticsPage })))
const StudentAnalyticsPage = lazy(() => import('./pages/analytics/student-analytics').then((m) => ({ default: m.StudentAnalyticsPage })))
const AcademicAnalyticsPage = lazy(() => import('./pages/analytics/academic-analytics').then((m) => ({ default: m.AcademicAnalyticsPage })))

// Notifications
const NotificationsPage = lazy(() => import('./pages/notifications/notifications-page').then((m) => ({ default: m.NotificationsPage })))

// Operations hub
const OperationsHubPage = lazy(() => import('./pages/operations/operations-hub').then((m) => ({ default: m.OperationsHubPage })))

// Leave
const LeaveListPage = lazy(() => import('./pages/leave/leave-list').then((m) => ({ default: m.LeaveListPage })))
const NewLeavePage = lazy(() => import('./pages/leave/new-leave').then((m) => ({ default: m.NewLeavePage })))
const LeaveDetailPage = lazy(() => import('./pages/leave/leave-detail').then((m) => ({ default: m.LeaveDetailPage })))

// Admissions
const AdmissionsPage = lazy(() => import('./pages/admission').then((m) => ({ default: m.AdmissionsPage })))
const ApplicationListPage = lazy(() => import('./pages/admission/application-list').then((m) => ({ default: m.ApplicationListPage })))
const ApplicationDetailPage = lazy(() => import('./pages/admission/application-detail').then((m) => ({ default: m.ApplicationDetailPage })))
const NewInquiryPage = lazy(() => import('./pages/admission/new-inquiry').then((m) => ({ default: m.NewInquiryPage })))

// Admin
const AuditLogViewerPage = lazy(() => import('./pages/admin/audit-log-viewer'))

// Migration Center (D2)
const MigrationCenterPage = lazy(() => import('./pages/migration/migration-center').then((m) => ({ default: m.MigrationCenterPage })))
const MigrationWizardPage = lazy(() => import('./pages/migration/migration-wizard').then((m) => ({ default: m.MigrationWizardPage })))

// Workflow
const ApprovalInboxPage = lazy(() => import('./pages/workflow').then((m) => ({ default: m.ApprovalInboxPage })))

// Report Builder
const ReportBuilderHubPage = lazy(() => import('./pages/report-builder').then((m) => ({ default: m.ReportBuilderPage })))
const ReportBuilderWorkspace = lazy(() => import('./pages/report-builder/builder').then((m) => ({ default: m.ReportBuilderPage })))
const ExportJobsPage = lazy(() => import('./pages/report-builder/exports').then((m) => ({ default: m.ExportJobsPage })))
const SavedReportsPage = lazy(() => import('./pages/report-builder/saved').then((m) => ({ default: m.SavedReportsPage })))

// Operations - these have default exports so simple import works
const StudentExportPage = lazy(() => import('./pages/operations/student-export'))
const AttendanceExportPage = lazy(() => import('./pages/operations/attendance-export'))
const PaymentExportPage = lazy(() => import('./pages/operations/payment-export'))
const RolloverPage = lazy(() => import('./pages/operations/rollover'))
const BatchEnrollPage = lazy(() => import('./pages/operations/batch-enroll'))
const BatchFeeDuesPage = lazy(() => import('./pages/operations/batch-fee-dues'))

// ── Workspace-specific dashboards ──
const TeacherDashboardPage = lazy(() => import('./pages/teacher/teacher-dashboard').then((m) => ({ default: m.TeacherDashboardPage })))
const StudentDashboardPage = lazy(() => import('./pages/student/student-dashboard').then((m) => ({ default: m.StudentDashboardPage })))
const ParentDashboardPage = lazy(() => import('./pages/parent/parent-dashboard').then((m) => ({ default: m.ParentDashboardPage })))
const ParentChildrenPage = lazy(() => import('./pages/parent/parent-children').then((m) => ({ default: m.ParentChildrenPage })))
const PrincipalDashboardPage = lazy(() => import('./pages/principal/principal-dashboard').then((m) => ({ default: m.PrincipalDashboardPage })))
const AccountantDashboardPage = lazy(() => import('./pages/accountant/accountant-dashboard').then((m) => ({ default: m.AccountantDashboardPage })))
const StaffDashboardPage = lazy(() => import('./pages/staff/staff-dashboard').then((m) => ({ default: m.StaffDashboardPage })))

// Communications
const CommunicationsHubPage = lazy(() => import('./pages/communications').then((m) => ({ default: m.CommunicationsHubPage })))
const ComposerPage = lazy(() => import('./pages/communications/composer').then((m) => ({ default: m.ComposerPage })))
const CommunicationsTemplatesPage = lazy(() => import('./pages/communications/templates').then((m) => ({ default: m.TemplatesPage })))
const SentMessagesPage = lazy(() => import('./pages/communications/sent').then((m) => ({ default: m.SentMessagesPage })))

// Parent Portal pages
const ParentAttendancePage = lazy(() => import('./pages/parent/parent-attendance').then((m) => ({ default: m.ParentAttendancePage })))
const ParentFeesPage = lazy(() => import('./pages/parent/parent-fees').then((m) => ({ default: m.ParentFeesPage })))
const ParentAcademicPage = lazy(() => import('./pages/parent/parent-academic').then((m) => ({ default: m.ParentAcademicPage })))
const ParentAnnouncementsPage = lazy(() => import('./pages/parent/parent-announcements').then((m) => ({ default: m.ParentAnnouncementsPage })))
const ParentDocumentsPage = lazy(() => import('./pages/parent/parent-documents').then((m) => ({ default: m.ParentDocumentsPage })))
const ParentCommunicationPage = lazy(() => import('./pages/parent/parent-communication').then((m) => ({ default: m.ParentCommunicationPage })))

// Student Portal pages
const StudentTimetablePage = lazy(() => import('./pages/student/student-timetable').then((m) => ({ default: m.StudentTimetablePage })))
const StudentPortalAttendancePage = lazy(() => import('./pages/student/student-attendance').then((m) => ({ default: m.StudentAttendancePage })))
const StudentSubjectsPage = lazy(() => import('./pages/student/student-subjects').then((m) => ({ default: m.StudentSubjectsPage })))
const StudentResultsPage = lazy(() => import('./pages/student/student-results').then((m) => ({ default: m.StudentResultsPage })))
const StudentAssignmentsPage = lazy(() => import('./pages/student/student-assignments').then((m) => ({ default: m.StudentAssignmentsPage })))
const StudentAnnouncementsPage = lazy(() => import('./pages/student/student-announcements').then((m) => ({ default: m.StudentAnnouncementsPage })))
const StudentDocumentsPage = lazy(() => import('./pages/student/student-documents').then((m) => ({ default: m.StudentDocumentsPage })))

// ── Fallback shown while a lazy page is loading ──
function PageFallback() {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="flex flex-col items-center gap-3">
        <div className="h-8 w-8 rounded-full border-2 border-[var(--color-brand-accent)] border-t-transparent animate-spin" />
        <p className="text-sm text-[var(--color-text-muted)]">Loading...</p>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <MotionProvider>
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <DelightProvider>
            <Routes>
            <Route
              path="/login"
              element={
                <Suspense fallback={<PageFallback />}>
                  <LoginPage />
                </Suspense>
              }
            />
            <Route
              element={
                <ProtectedRoute>
                  <AppLayout />
                </ProtectedRoute>
              }
            >
              <Route path="/dashboard" element={<Suspense fallback={null}><DashboardPage /></Suspense>} />
              <Route path="/command-center" element={
                <RoleGuard roles={['admin', 'principal', 'accountant', 'staff', 'teacher']}>
                  <Suspense fallback={<PageFallback />}><CommandCenterPage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/risk" element={
                <RoleGuard roles={['admin', 'principal', 'staff']}>
                  <Suspense fallback={<PageFallback />}><RiskCenterPage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/action-center" element={
                <RoleGuard roles={['admin', 'principal', 'staff', 'accountant']}>
                  <Suspense fallback={<PageFallback />}><ActionCenterPage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/data-quality" element={
                <RoleGuard roles={['admin', 'principal', 'staff']}>
                  <Suspense fallback={<PageFallback />}><DataQualityCenterPage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/work" element={
                <RoleGuard roles={['admin', 'principal', 'staff']}>
                  <Suspense fallback={<PageFallback />}><WorkQueuePage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/cases/:id" element={
                <RoleGuard roles={['admin', 'principal', 'staff']}>
                  <Suspense fallback={<PageFallback />}><CaseDetailPage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/timeline" element={
                <RoleGuard roles={['admin', 'principal', 'accountant', 'staff', 'teacher']}>
                  <Suspense fallback={<PageFallback />}><TimelinePage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/students" element={<Suspense fallback={null}><StudentListPage /></Suspense>} />
              <Route path="/students/:id" element={<Suspense fallback={null}><StudentDetailPage /></Suspense>} />
              <Route path="/students/:id/360" element={<Suspense fallback={null}><Student360Page /></Suspense>} />
              <Route path="/academic" element={<Suspense fallback={null}><AcademicPage /></Suspense>} />
              <Route path="/academic/years" element={<Suspense fallback={null}><AcademicYearListPage /></Suspense>} />
              <Route path="/academic/years/:id" element={<Suspense fallback={null}><AcademicYearDetailPage /></Suspense>} />
              <Route path="/academic/classes" element={<Suspense fallback={null}><ClassListPage /></Suspense>} />
              <Route path="/academic/classes/:id/360" element={<Suspense fallback={null}><Class360Page /></Suspense>} />
              <Route path="/academic/sections" element={<Suspense fallback={null}><SectionListPage /></Suspense>} />
              <Route path="/academic/enrollments" element={<Suspense fallback={null}><EnrollmentListPage /></Suspense>} />
              <Route path="/academic/terms" element={<Suspense fallback={null}><TermListPage /></Suspense>} />
              <Route path="/academic/assignments" element={<Suspense fallback={null}><TeacherAssignmentListPage /></Suspense>} />
              <Route path="/teachers" element={<Suspense fallback={null}><TeacherListPage /></Suspense>} />
              <Route path="/teachers/:id" element={<Suspense fallback={null}><TeacherDetailPage /></Suspense>} />
              <Route path="/teachers/:id/360" element={<Suspense fallback={null}><Teacher360Page /></Suspense>} />
              <Route path="/subjects" element={<Suspense fallback={null}><SubjectListPage /></Suspense>} />
              <Route path="/attendance" element={<Suspense fallback={null}><AttendancePage /></Suspense>} />
              <Route path="/attendance/records" element={<Suspense fallback={null}><AttendanceRecordsPage /></Suspense>} />
              <Route path="/attendance/records/:id" element={<Suspense fallback={null}><AttendanceRecordDetailPage /></Suspense>} />
              <Route path="/attendance/record" element={<Suspense fallback={null}><RecordAttendancePage /></Suspense>} />
              <Route path="/attendance/daily" element={<Suspense fallback={null}><DailyAttendancePage /></Suspense>} />
              <Route path="/attendance/student" element={<Suspense fallback={null}><StudentAttendancePage /></Suspense>} />
              <Route path="/attendance/student/:studentId" element={<Suspense fallback={null}><StudentAttendancePage /></Suspense>} />
              <Route path="/attendance/section" element={<Suspense fallback={null}><SectionAttendancePage /></Suspense>} />
              <Route path="/attendance/section/:sectionId" element={<Suspense fallback={null}><SectionAttendancePage /></Suspense>} />
              <Route path="/attendance-intelligence" element={<Suspense fallback={null}><AttendanceIntelligencePage /></Suspense>} />
              <Route path="/attendance-intelligence/dashboard" element={<Suspense fallback={null}><AttendanceIntelligenceDashboardPage /></Suspense>} />
              <Route path="/attendance-intelligence/period" element={<Suspense fallback={null}><PeriodAttendancePage /></Suspense>} />
              <Route path="/attendance-intelligence/corrections" element={<Suspense fallback={null}><AttendanceCorrectionsPage /></Suspense>} />
              <Route path="/attendance-intelligence/thresholds" element={<Suspense fallback={null}><AttendanceThresholdsPage /></Suspense>} />
              <Route path="/fees" element={<Suspense fallback={null}><FeesPage /></Suspense>} />
              <Route path="/fees/fee-types" element={<Suspense fallback={null}><FeeTypeListPage /></Suspense>} />
              <Route path="/fees/structures" element={<Suspense fallback={null}><FeeStructureListPage /></Suspense>} />
              <Route path="/fees/student-fees" element={<Suspense fallback={null}><StudentFeesPage /></Suspense>} />
              <Route path="/fees/dues" element={<Suspense fallback={null}><FeeDueListPage /></Suspense>} />
              <Route path="/fees/payments" element={<Suspense fallback={null}><PaymentListPage /></Suspense>} />
              <Route path="/fees/summary" element={<Suspense fallback={null}><FinancialSummaryPage /></Suspense>} />
              <Route path="/school-finance" element={<Suspense fallback={null}><SchoolFinancePage /></Suspense>} />
              <Route path="/school-finance/dashboard" element={<Suspense fallback={null}><SchoolFinanceDashboardPage /></Suspense>} />
              <Route path="/school-finance/exceptions" element={<Suspense fallback={null}><FinancialExceptionsPage /></Suspense>} />
              <Route path="/school-finance/fee-schedules" element={<Suspense fallback={null}><FeeSchedulesPage /></Suspense>} />
              <Route path="/school-finance/reconciliation" element={<Suspense fallback={null}><ReconciliationPage /></Suspense>} />
              <Route path="/school-finance/receipts" element={<Suspense fallback={null}><ReceiptsPage /></Suspense>} />
              <Route path="/school-finance/transactions" element={<Suspense fallback={null}><TransactionsPage /></Suspense>} />
              <Route path="/school-finance/outstanding" element={<Suspense fallback={null}><OutstandingBalancesPage /></Suspense>} />
              <Route path="/school-finance/reports" element={<Suspense fallback={null}><FinanceReportsPage /></Suspense>} />
              <Route path="/users" element={<Suspense fallback={null}><UserListPage /></Suspense>} />
              <Route path="/profile" element={<Suspense fallback={null}><ProfilePage /></Suspense>} />

              {/* ── Role-based Workspace Routes ── */}

              {/* Principal workspace */}
              <Route path="/principal" element={
                <RoleGuard roles={['principal']}>
                  <Suspense fallback={<PageFallback />}><PrincipalDashboardPage /></Suspense>
                </RoleGuard>
              } />

              {/* Accountant workspace */}
              <Route path="/accountant" element={
                <RoleGuard roles={['accountant']}>
                  <Suspense fallback={<PageFallback />}><AccountantDashboardPage /></Suspense>
                </RoleGuard>
              } />

              {/* Staff workspace */}
              <Route path="/staff" element={
                <RoleGuard roles={['staff']}>
                  <Suspense fallback={<PageFallback />}><StaffDashboardPage /></Suspense>
                </RoleGuard>
              } />

              {/* Teacher workspace */}
              <Route path="/teacher" element={
                <RoleGuard roles={['teacher']}>
                  <Suspense fallback={<PageFallback />}><TeacherDashboardPage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/teacher/classes" element={<Navigate to="/teacher" replace />} />
              <Route path="/teacher/students" element={<Navigate to="/students" replace />} />

              {/* Student workspace */}
              <Route path="/student" element={
                <RoleGuard roles={['student']}>
                  <Suspense fallback={<PageFallback />}><StudentDashboardPage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/student/timetable" element={
                <RoleGuard roles={['student']}>
                  <Suspense fallback={<PageFallback />}><StudentTimetablePage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/student/attendance" element={
                <RoleGuard roles={['student']}>
                  <Suspense fallback={<PageFallback />}><StudentPortalAttendancePage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/student/subjects" element={
                <RoleGuard roles={['student']}>
                  <Suspense fallback={<PageFallback />}><StudentSubjectsPage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/student/results" element={
                <RoleGuard roles={['student']}>
                  <Suspense fallback={<PageFallback />}><StudentResultsPage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/student/assignments" element={
                <RoleGuard roles={['student']}>
                  <Suspense fallback={<PageFallback />}><StudentAssignmentsPage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/student/announcements" element={
                <RoleGuard roles={['student']}>
                  <Suspense fallback={<PageFallback />}><StudentAnnouncementsPage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/student/documents" element={
                <RoleGuard roles={['student']}>
                  <Suspense fallback={<PageFallback />}><StudentDocumentsPage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/student/fees" element={<Navigate to="/fees/student-fees" replace />} />
              <Route path="/student/schedule" element={<Navigate to="/student/timetable" replace />} />

              {/* Parent workspace */}
              <Route path="/parent" element={
                <RoleGuard roles={['parent']}>
                  <Suspense fallback={<PageFallback />}><ParentDashboardPage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/parent/children" element={
                <RoleGuard roles={['parent']}>
                  <Suspense fallback={<PageFallback />}><ParentChildrenPage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/parent/attendance" element={
                <RoleGuard roles={['parent']}>
                  <Suspense fallback={<PageFallback />}><ParentAttendancePage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/parent/fees" element={
                <RoleGuard roles={['parent']}>
                  <Suspense fallback={<PageFallback />}><ParentFeesPage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/parent/academic" element={
                <RoleGuard roles={['parent']}>
                  <Suspense fallback={<PageFallback />}><ParentAcademicPage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/parent/announcements" element={
                <RoleGuard roles={['parent']}>
                  <Suspense fallback={<PageFallback />}><ParentAnnouncementsPage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/parent/documents" element={
                <RoleGuard roles={['parent']}>
                  <Suspense fallback={<PageFallback />}><ParentDocumentsPage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/parent/messages" element={
                <RoleGuard roles={['parent']}>
                  <Suspense fallback={<PageFallback />}><ParentCommunicationPage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/parent/payments" element={<Navigate to="/parent/fees" replace />} />
              <Route path="/reports" element={<Suspense fallback={null}><ReportsHubPage /></Suspense>} />
              <Route path="/reports/cards" element={<Suspense fallback={null}><ReportCardsPage /></Suspense>} />
              <Route path="/reports/attendance" element={<Suspense fallback={null}><AttendanceReportPage /></Suspense>} />
              <Route path="/reports/fees/collection" element={<Suspense fallback={null}><FeeCollectionReportPage /></Suspense>} />
              <Route path="/reports/fees/outstanding" element={<Suspense fallback={null}><OutstandingReportPage /></Suspense>} />
              <Route path="/reports/receipts" element={<Suspense fallback={null}><ReceiptLookupPage /></Suspense>} />
              <Route path="/reports/builder" element={<Suspense fallback={null}><ReportBuilderHubPage /></Suspense>} />
              <Route path="/reports/builder/new" element={<Suspense fallback={null}><ReportBuilderWorkspace /></Suspense>} />
              <Route path="/reports/builder/exports" element={<Suspense fallback={null}><ExportJobsPage /></Suspense>} />
              <Route path="/reports/builder/saved" element={<Suspense fallback={null}><SavedReportsPage /></Suspense>} />
              <Route path="/analytics" element={<Suspense fallback={null}><AnalyticsHubPage /></Suspense>} />
              <Route path="/analytics/attendance" element={<Suspense fallback={null}><AttendanceAnalyticsPage /></Suspense>} />
              <Route path="/analytics/finance" element={<Suspense fallback={null}><FinanceAnalyticsPage /></Suspense>} />
              <Route path="/analytics/students" element={<Suspense fallback={null}><StudentAnalyticsPage /></Suspense>} />
              <Route path="/analytics/academic" element={<Suspense fallback={null}><AcademicAnalyticsPage /></Suspense>} />
              <Route path="/notifications" element={<Suspense fallback={null}><NotificationsPage /></Suspense>} />
              <Route path="/operations" element={<Suspense fallback={null}><OperationsHubPage /></Suspense>} />
              <Route path="/operations/export/students" element={<Suspense fallback={null}><StudentExportPage /></Suspense>} />
              <Route path="/operations/export/attendance" element={<Suspense fallback={null}><AttendanceExportPage /></Suspense>} />
              <Route path="/operations/export/payments" element={<Suspense fallback={null}><PaymentExportPage /></Suspense>} />
              <Route path="/operations/rollover" element={<Suspense fallback={null}><RolloverPage /></Suspense>} />
              <Route path="/operations/batch/enroll" element={<Suspense fallback={null}><BatchEnrollPage /></Suspense>} />
              <Route path="/operations/batch/fee-dues" element={<Suspense fallback={null}><BatchFeeDuesPage /></Suspense>} />

              {/* Admin */}
              <Route path="/admin/audit-logs" element={
                <RoleGuard roles={['admin']}>
                  <Suspense fallback={<PageFallback />}><AuditLogViewerPage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/admin/approvals" element={
                <RoleGuard roles={['admin']}>
                  <Suspense fallback={<PageFallback />}><ApprovalInboxPage /></Suspense>
                </RoleGuard>
              } />

              {/* Migration Center (D2) */}
              <Route path="/migration" element={
                <RoleGuard roles={['admin']}>
                  <Suspense fallback={<PageFallback />}><MigrationCenterPage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/migration/new" element={
                <RoleGuard roles={['admin']}>
                  <Suspense fallback={<PageFallback />}><MigrationWizardPage /></Suspense>
                </RoleGuard>
              } />
              <Route path="/migration/:id" element={
                <RoleGuard roles={['admin']}>
                  <Suspense fallback={<PageFallback />}><MigrationWizardPage /></Suspense>
                </RoleGuard>
              } />

              {/* Leave */}
              <Route path="/leave" element={<Suspense fallback={null}><LeaveListPage /></Suspense>} />
              <Route path="/leave/new" element={<Suspense fallback={null}><NewLeavePage /></Suspense>} />
              <Route path="/leave/:id" element={<Suspense fallback={null}><LeaveDetailPage /></Suspense>} />

              {/* Admissions */}
              <Route path="/admissions" element={<Suspense fallback={null}><AdmissionsPage /></Suspense>} />
              <Route path="/admissions/applications" element={<Suspense fallback={null}><ApplicationListPage /></Suspense>} />
              <Route path="/admissions/new" element={<Suspense fallback={null}><NewInquiryPage /></Suspense>} />
              <Route path="/admissions/:id" element={<Suspense fallback={null}><ApplicationDetailPage /></Suspense>} />

              {/* Communications */}
              <Route path="/communications" element={<Suspense fallback={null}><CommunicationsHubPage /></Suspense>} />
              <Route path="/communications/compose" element={<Suspense fallback={null}><ComposerPage /></Suspense>} />
              <Route path="/communications/templates" element={<Suspense fallback={null}><CommunicationsTemplatesPage /></Suspense>} />
              <Route path="/communications/sent" element={<Suspense fallback={null}><SentMessagesPage /></Suspense>} />
            </Route>
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </DelightProvider>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
    </MotionProvider>
  )
}