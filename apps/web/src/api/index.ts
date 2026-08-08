export { api, getAccessToken, clearTokens } from './client/http-client'
export { commandCenterApi } from './command-center/command-center-api'
export type {
  CommandCenterOverview,
  Metric,
  SchoolHealth,
  AttentionAlert,
  NeedsAttention,
  TodayEvent,
  TodaySection,
  QuickAction,
} from './command-center/command-center-api'
export { riskApi } from './risk/risk-api'
export { casesApi } from './cases/cases-api'
export type {
  CaseItem,
  CaseDetail,
  CaseEventItem,
  CaseCommentItem,
  CaseEvidenceItem,
  CasePage,
  CaseOverview,
  CaseMetrics,
  WorkloadItem,
  AssignableUser,
  BulkResult,
  EscalationResult,
  CaseListParams,
  CaseCreateParams,
  CasePriority,
  CaseStatus,
  CaseType,
  CaseSourceType,
} from './cases/cases-api'
export { dataQualityApi } from './data-quality/data-quality-api'
export type {
  DataQualityFinding,
  DataQualityFindingPage,
  DataQualityOverview,
  DataQualityRunResult,
  DataQualityFindingParams,
} from './data-quality/data-quality-api'
export { timelineApi } from './timeline/timeline-api'
export type {
  TimelineItem,
  TimelineSourceInfo,
  TimelineResponse,
  TimelineParams,
} from './timeline/timeline-api'
export type {
  RiskFinding,
  RiskFindingPage,
  RiskOverview,
  RecomputeResult,
  RuleConfig,
  RiskFindingParams,
  RuleConfigUpdate,
  TeacherRiskFinding,
  TeacherRiskSummary,
} from './risk/risk-api'
export { authApi, adminUserApi } from './auth/auth-api'
export { auditLogApi } from './audit/audit-api'
export { studentApi } from './student/student-api'
export type { StudentListParams } from './student/student-api'
export { student360Api } from './student-360/student-360-api'
export type { Student360Response } from './student-360/student-360-api'
export { class360Api } from './class-360/class-360-api'
export type { Class360Response } from './class-360/class-360-api'
export { teacher360Api } from './teacher-360/teacher-360-api'
export type { Teacher360Response } from './teacher-360/teacher-360-api'
export { academicYearApi } from './academic/academic-year-api'
export type { AcademicYearListParams } from './academic/academic-year-api'
export { classApi } from './academic/class-api'
export type { ClassListParams } from './academic/class-api'
export { sectionApi } from './academic/section-api'
export type { SectionListParams } from './academic/section-api'
export { enrollmentApi } from './academic/enrollment-api'
export type { EnrollmentListParams } from './academic/enrollment-api'
export { termApi } from './academic/term-api'
export { subjectApi } from './academic/subject-api'
export type { SubjectListParams } from './academic/subject-api'
export { teacherApi } from './academic/teacher-api'
export type { TeacherListParams } from './academic/teacher-api'
export { teacherAssignmentApi } from './academic/teacher-assignment-api'
export type { TeacherAssignmentListParams } from './academic/teacher-assignment-api'
export { attendanceApi } from './attendance/attendance-api'
export type { AttendanceListParams, StudentAttendanceParams } from './attendance/attendance-api'
export { attendanceIntelligenceApi } from './attendance-intelligence/attendance-intelligence-api'
export type { AttendanceIntelligenceListParams, AttendanceIntelligenceDashboard, ChronicAbsenteeismRecord, LowAttendanceAlertItem, StudentAttendanceTrend, ClassAttendanceTrend, SectionAttendanceTrend, PeriodAttendanceResponse, AttendanceCorrectionResponse, AttendanceThresholdResponse, AbsenceReasonResponse } from './attendance-intelligence/attendance-intelligence-api'
export { feeTypeApi } from './fees/fee-type-api'
export type { FeeTypeListParams } from './fees/fee-type-api'
export { feeStructureApi } from './fees/fee-structure-api'
export type { FeeStructureListParams } from './fees/fee-structure-api'
export { feeDueApi } from './fees/fee-due-api'
export type { FeeDueListParams } from './fees/fee-due-api'
export { paymentApi } from './fees/payment-api'
export type { PaymentListParams } from './fees/payment-api'
export { summaryApi } from './fees/summary-api'
export { schoolFinanceDashboardApi, paymentMethodApi, feeScheduleApi, transactionLogApi, reconciliationApi, receiptApi, outstandingBalanceApi, financeReportApi } from './school-finance/school-finance-api'
export type { SchoolFinanceListParams, SchoolFinanceDashboard, PaymentMethodResponse, PaymentMethodCreate, PaymentMethodUpdate, FeeScheduleResponse, FeeScheduleCreate, FeeScheduleUpdate, TransactionLogResponse, PaymentReconciliationResponse, ReconciliationCreate, ReceiptResponse, ReceiptGenerate, ReceiptDetailResponse, FinanceReportResponse, FinanceReportGenerate, OutstandingBalanceItem, OutstandingBalanceSummary } from './school-finance/school-finance-api'
export {
  attendanceReportApi,
  feeReportApi,
  rolloverApi,
  batchApi,
  exportApi,
} from './reports'
export type {
  AttendanceReportParams,
  CollectionReportParams,
  OutstandingReportParams,
  ExportParams,
  ClassAttendanceSummaryReport,
  SectionAttendanceSummaryReport,
  CollectionReportItem,
  OutstandingReportItem,
  DetailedReceipt,
  RolloverPreview,
  RolloverExecuteInput,
  RolloverResult,
  BatchEnrollItem,
  BatchEnrollInput,
  BatchEnrollResult,
  BatchFeeDueInput,
  BatchFeeDueResult,
} from './reports'

export {
  reportDefinitionApi,
  reportExecuteApi,
  savedReportApi,
  exportJobApi,
} from './report-builder/report-builder-api'
export type {
  ReportBuilderListParams,
  ReportFilterSchema,
  ReportColumnSchema,
  ReportDefinitionInfo,
  ReportExecuteResponse,
  SavedReportResponse,
  ExportJobResponse,
  Page,
} from './report-builder/report-builder-api'