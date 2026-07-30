import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './api/auth/auth-context'
import { ToastProvider } from './components/ui/toast'
import { ProtectedRoute } from './components/protected-route'
import { RoleGuard } from './components/auth/role-guard'
import { AppLayout } from './components/layout'

// ── Lazy-loaded page components ──

// Login (outside main layout)
const LoginPage = lazy(() => import('./pages/login').then((m) => ({ default: m.LoginPage })))

// Dashboard
const DashboardPage = lazy(() => import('./pages/dashboard').then((m) => ({ default: m.DashboardPage })))

// Students
const StudentListPage = lazy(() => import('./pages/students/student-list').then((m) => ({ default: m.StudentListPage })))
const StudentDetailPage = lazy(() => import('./pages/students/student-detail').then((m) => ({ default: m.StudentDetailPage })))

// Academic
const AcademicPage = lazy(() => import('./pages/academic').then((m) => ({ default: m.AcademicPage })))
const AcademicYearListPage = lazy(() => import('./pages/academic/academic-year-list').then((m) => ({ default: m.AcademicYearListPage })))
const AcademicYearDetailPage = lazy(() => import('./pages/academic/academic-year-detail').then((m) => ({ default: m.AcademicYearDetailPage })))
const ClassListPage = lazy(() => import('./pages/academic/class-list').then((m) => ({ default: m.ClassListPage })))
const SectionListPage = lazy(() => import('./pages/academic/section-list').then((m) => ({ default: m.SectionListPage })))
const EnrollmentListPage = lazy(() => import('./pages/academic/enrollment-list').then((m) => ({ default: m.EnrollmentListPage })))
const TermListPage = lazy(() => import('./pages/academic/term-list').then((m) => ({ default: m.TermListPage })))
const TeacherAssignmentListPage = lazy(() => import('./pages/academic/teacher-assignment-list').then((m) => ({ default: m.TeacherAssignmentListPage })))

// Teachers
const TeacherListPage = lazy(() => import('./pages/teachers/teacher-list').then((m) => ({ default: m.TeacherListPage })))
const TeacherDetailPage = lazy(() => import('./pages/teachers/teacher-detail').then((m) => ({ default: m.TeacherDetailPage })))

// Subjects
const SubjectListPage = lazy(() => import('./pages/subjects/subject-list').then((m) => ({ default: m.SubjectListPage })))

// Attendance
const AttendancePage = lazy(() => import('./pages/attendance').then((m) => ({ default: m.AttendancePage })))
const AttendanceRecordsPage = lazy(() => import('./pages/attendance/attendance-records').then((m) => ({ default: m.AttendanceRecordsPage })))
const AttendanceRecordDetailPage = lazy(() => import('./pages/attendance/attendance-record-detail').then((m) => ({ default: m.AttendanceRecordDetailPage })))
const RecordAttendancePage = lazy(() => import('./pages/attendance/record-attendance').then((m) => ({ default: m.RecordAttendancePage })))
const DailyAttendancePage = lazy(() => import('./pages/attendance/daily-attendance').then((m) => ({ default: m.DailyAttendancePage })))
const StudentAttendancePage = lazy(() => import('./pages/attendance/student-attendance').then((m) => ({ default: m.StudentAttendancePage })))
const SectionAttendancePage = lazy(() => import('./pages/attendance/section-attendance').then((m) => ({ default: m.SectionAttendancePage })))

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
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
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
              <Route path="/students" element={<Suspense fallback={null}><StudentListPage /></Suspense>} />
              <Route path="/students/:id" element={<Suspense fallback={null}><StudentDetailPage /></Suspense>} />
              <Route path="/academic" element={<Suspense fallback={null}><AcademicPage /></Suspense>} />
              <Route path="/academic/years" element={<Suspense fallback={null}><AcademicYearListPage /></Suspense>} />
              <Route path="/academic/years/:id" element={<Suspense fallback={null}><AcademicYearDetailPage /></Suspense>} />
              <Route path="/academic/classes" element={<Suspense fallback={null}><ClassListPage /></Suspense>} />
              <Route path="/academic/sections" element={<Suspense fallback={null}><SectionListPage /></Suspense>} />
              <Route path="/academic/enrollments" element={<Suspense fallback={null}><EnrollmentListPage /></Suspense>} />
              <Route path="/academic/terms" element={<Suspense fallback={null}><TermListPage /></Suspense>} />
              <Route path="/academic/assignments" element={<Suspense fallback={null}><TeacherAssignmentListPage /></Suspense>} />
              <Route path="/teachers" element={<Suspense fallback={null}><TeacherListPage /></Suspense>} />
              <Route path="/teachers/:id" element={<Suspense fallback={null}><TeacherDetailPage /></Suspense>} />
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
              <Route path="/fees" element={<Suspense fallback={null}><FeesPage /></Suspense>} />
              <Route path="/fees/fee-types" element={<Suspense fallback={null}><FeeTypeListPage /></Suspense>} />
              <Route path="/fees/structures" element={<Suspense fallback={null}><FeeStructureListPage /></Suspense>} />
              <Route path="/fees/student-fees" element={<Suspense fallback={null}><StudentFeesPage /></Suspense>} />
              <Route path="/fees/dues" element={<Suspense fallback={null}><FeeDueListPage /></Suspense>} />
              <Route path="/fees/payments" element={<Suspense fallback={null}><PaymentListPage /></Suspense>} />
              <Route path="/fees/summary" element={<Suspense fallback={null}><FinancialSummaryPage /></Suspense>} />
              <Route path="/users" element={<Suspense fallback={null}><UserListPage /></Suspense>} />
              <Route path="/profile" element={<Suspense fallback={null}><ProfilePage /></Suspense>} />

              {/* ── Role-based Workspace Routes ── */}
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
              <Route path="/student/attendance" element={<Navigate to="/attendance/student" replace />} />
              <Route path="/student/fees" element={<Navigate to="/fees/student-fees" replace />} />
              <Route path="/student/schedule" element={
                <div className="flex flex-col items-center justify-center min-h-[60vh] animate-fade-in">
                  <div className="flex items-center justify-center h-16 w-16 rounded-2xl bg-[var(--color-surface-hover)] mb-4">
                    <svg className="h-8 w-8 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  </div>
                  <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-1">Schedule</h3>
                  <p className="text-sm text-[var(--color-text-tertiary)] text-center max-w-sm">
                    Your class schedule will appear here once it's configured.
                  </p>
                </div>
              } />

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
              <Route path="/parent/payments" element={<Navigate to="/fees/dues" replace />} />
              <Route path="/reports" element={<Suspense fallback={null}><ReportsHubPage /></Suspense>} />
              <Route path="/reports/attendance" element={<Suspense fallback={null}><AttendanceReportPage /></Suspense>} />
              <Route path="/reports/fees/collection" element={<Suspense fallback={null}><FeeCollectionReportPage /></Suspense>} />
              <Route path="/reports/fees/outstanding" element={<Suspense fallback={null}><OutstandingReportPage /></Suspense>} />
              <Route path="/reports/receipts" element={<Suspense fallback={null}><ReceiptLookupPage /></Suspense>} />
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

              {/* Leave */}
              <Route path="/leave" element={<Suspense fallback={null}><LeaveListPage /></Suspense>} />
              <Route path="/leave/new" element={<Suspense fallback={null}><NewLeavePage /></Suspense>} />
              <Route path="/leave/:id" element={<Suspense fallback={null}><LeaveDetailPage /></Suspense>} />

              {/* Admissions */}
              <Route path="/admissions" element={<Suspense fallback={null}><AdmissionsPage /></Suspense>} />
              <Route path="/admissions/applications" element={<Suspense fallback={null}><ApplicationListPage /></Suspense>} />
              <Route path="/admissions/new" element={<Suspense fallback={null}><NewInquiryPage /></Suspense>} />
              <Route path="/admissions/:id" element={<Suspense fallback={null}><ApplicationDetailPage /></Suspense>} />
            </Route>
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}