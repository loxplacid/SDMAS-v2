import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './api/auth/auth-context'
import { ToastProvider } from './components/ui/toast'
import { ProtectedRoute } from './components/protected-route'
import { AppLayout } from './components/layout'
import { LoginPage } from './pages/login'
import { DashboardPage } from './pages/dashboard'
import { StudentListPage, StudentDetailPage } from './pages/students'
import { AcademicPage, AcademicYearListPage, AcademicYearDetailPage, ClassListPage, SectionListPage, EnrollmentListPage, TermListPage, TeacherAssignmentListPage } from './pages/academic'
import { AttendancePage } from './pages/attendance'
import { AttendanceRecordsPage } from './pages/attendance/attendance-records'
import { AttendanceRecordDetailPage } from './pages/attendance/attendance-record-detail'
import { RecordAttendancePage } from './pages/attendance/record-attendance'
import { DailyAttendancePage } from './pages/attendance/daily-attendance'
import { StudentAttendancePage } from './pages/attendance/student-attendance'
import { SectionAttendancePage } from './pages/attendance/section-attendance'
import { FeesPage } from './pages/fees'
import { FeeTypeListPage } from './pages/fees/fee-type-list'
import { FeeStructureListPage } from './pages/fees/fee-structure-list'
import { StudentFeesPage } from './pages/fees/student-fees'
import { FeeDueListPage } from './pages/fees/fee-due-list'
import { PaymentListPage } from './pages/fees/payment-list'
import { FinancialSummaryPage } from './pages/fees/financial-summary'
import { UserListPage } from './pages/users/user-list'
import { ProfilePage } from './pages/profile'
import { ReportsHubPage } from './pages/reports/reports-hub'
import { AttendanceReportPage } from './pages/reports/attendance-report'
import { FeeCollectionReportPage } from './pages/reports/fee-collection-report'
import { OutstandingReportPage } from './pages/reports/outstanding-report'
import { ReceiptLookupPage } from './pages/reports/receipt-lookup'
import { AnalyticsHubPage } from './pages/analytics/analytics-hub'
import { AttendanceAnalyticsPage } from './pages/analytics/attendance-analytics'
import { FinanceAnalyticsPage } from './pages/analytics/finance-analytics'
import { StudentAnalyticsPage } from './pages/analytics/student-analytics'
import { AcademicAnalyticsPage } from './pages/analytics/academic-analytics'
import { NotificationsPage } from './pages/notifications/notifications-page'
import { OperationsHubPage } from './pages/operations/operations-hub'
import { StudentExportPage } from './pages/operations/student-export'
import { AttendanceExportPage } from './pages/operations/attendance-export'
import { PaymentExportPage } from './pages/operations/payment-export'
import { RolloverPage } from './pages/operations/rollover'
import { BatchEnrollPage } from './pages/operations/batch-enroll'
import { BatchFeeDuesPage } from './pages/operations/batch-fee-dues'
import { TeacherListPage, TeacherDetailPage } from './pages/teachers'
import { SubjectListPage } from './pages/subjects'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              element={
                <ProtectedRoute>
                  <AppLayout />
                </ProtectedRoute>
              }
            >
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/students" element={<StudentListPage />} />
              <Route path="/students/:id" element={<StudentDetailPage />} />
              <Route path="/academic" element={<AcademicPage />} />
              <Route path="/academic/years" element={<AcademicYearListPage />} />
              <Route path="/academic/years/:id" element={<AcademicYearDetailPage />} />
              <Route path="/academic/classes" element={<ClassListPage />} />
              <Route path="/academic/sections" element={<SectionListPage />} />
              <Route path="/academic/enrollments" element={<EnrollmentListPage />} />
              <Route path="/academic/terms" element={<TermListPage />} />
              <Route path="/academic/assignments" element={<TeacherAssignmentListPage />} />
              <Route path="/teachers" element={<TeacherListPage />} />
              <Route path="/teachers/:id" element={<TeacherDetailPage />} />
              <Route path="/subjects" element={<SubjectListPage />} />
              <Route path="/attendance" element={<AttendancePage />} />
              <Route path="/attendance/records" element={<AttendanceRecordsPage />} />
              <Route path="/attendance/records/:id" element={<AttendanceRecordDetailPage />} />
              <Route path="/attendance/record" element={<RecordAttendancePage />} />
              <Route path="/attendance/daily" element={<DailyAttendancePage />} />
              <Route path="/attendance/student" element={<StudentAttendancePage />} />
              <Route path="/attendance/student/:studentId" element={<StudentAttendancePage />} />
              <Route path="/attendance/section" element={<SectionAttendancePage />} />
              <Route path="/attendance/section/:sectionId" element={<SectionAttendancePage />} />
              <Route path="/fees" element={<FeesPage />} />
              <Route path="/fees/fee-types" element={<FeeTypeListPage />} />
              <Route path="/fees/structures" element={<FeeStructureListPage />} />
              <Route path="/fees/student-fees" element={<StudentFeesPage />} />
              <Route path="/fees/dues" element={<FeeDueListPage />} />
              <Route path="/fees/payments" element={<PaymentListPage />} />
              <Route path="/fees/summary" element={<FinancialSummaryPage />} />
              <Route path="/users" element={<UserListPage />} />
              <Route path="/profile" element={<ProfilePage />} />
              <Route path="/reports" element={<ReportsHubPage />} />
              <Route path="/reports/attendance" element={<AttendanceReportPage />} />
              <Route path="/reports/fees/collection" element={<FeeCollectionReportPage />} />
              <Route path="/reports/fees/outstanding" element={<OutstandingReportPage />} />
              <Route path="/reports/receipts" element={<ReceiptLookupPage />} />
              <Route path="/analytics" element={<AnalyticsHubPage />} />
              <Route path="/analytics/attendance" element={<AttendanceAnalyticsPage />} />
              <Route path="/analytics/finance" element={<FinanceAnalyticsPage />} />
              <Route path="/analytics/students" element={<StudentAnalyticsPage />} />
              <Route path="/analytics/academic" element={<AcademicAnalyticsPage />} />
              <Route path="/notifications" element={<NotificationsPage />} />
              <Route path="/operations" element={<OperationsHubPage />} />
              <Route path="/operations/export/students" element={<StudentExportPage />} />
              <Route path="/operations/export/attendance" element={<AttendanceExportPage />} />
              <Route path="/operations/export/payments" element={<PaymentExportPage />} />
              <Route path="/operations/rollover" element={<RolloverPage />} />
              <Route path="/operations/batch/enroll" element={<BatchEnrollPage />} />
              <Route path="/operations/batch/fee-dues" element={<BatchFeeDuesPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}