import { api } from '../client/http-client'

export type SchoolFinanceListParams = {
  page?: number
  size?: number
  campus_id?: number
  student_id?: number
  fee_structure_id?: number
  from_date?: string
  to_date?: string
  status?: string
  transaction_type?: string
  report_type?: string
  min_amount?: number
  max_amount?: number
  q?: string
}

export interface PaymentMethodResponse {
  id: number
  name: string
  code: string
  description: string | null
  is_active: boolean
  requires_reference: boolean
  gateway_config: Record<string, unknown> | null
  campus_id: number | null
  created_at: string
  updated_at: string
}

export interface PaymentMethodCreate {
  name: string
  code: string
  description?: string | null
  is_active?: boolean
  requires_reference?: boolean
  gateway_config?: Record<string, unknown> | null
  campus_id?: number | null
}

export interface PaymentMethodUpdate {
  name?: string | null
  code?: string | null
  description?: string | null
  is_active?: boolean | null
  requires_reference?: boolean | null
  gateway_config?: Record<string, unknown> | null
}

export interface FeeScheduleResponse {
  id: number
  fee_structure_id: number
  name: string
  installment_number: number
  due_date: string
  amount: number
  penalty_amount: number
  discount_amount: number
  campus_id: number | null
  status: string
  created_at: string
  updated_at: string
}

export interface FeeScheduleCreate {
  fee_structure_id: number
  name: string
  installment_number: number
  due_date: string
  amount: number
  penalty_amount?: number
  discount_amount?: number
  campus_id?: number | null
  status?: string
}

export interface FeeScheduleUpdate {
  name?: string | null
  due_date?: string | null
  amount?: number | null
  penalty_amount?: number | null
  discount_amount?: number | null
  status?: string | null
}

export interface TransactionLogResponse {
  id: number
  transaction_type: string
  payment_id: number | null
  fee_due_id: number | null
  student_id: number
  amount: number
  balance_before: number
  balance_after: number
  reference_number: string | null
  idempotency_key: string | null
  description: string | null
  campus_id: number | null
  recorded_by: number | null
  created_at: string
}

export interface PaymentReconciliationResponse {
  id: number
  reconciliation_date: string
  total_amount: number
  total_count: number
  status: string
  notes: string | null
  reconciled_by: number | null
  campus_id: number | null
  created_at: string
  updated_at: string
  items: ReconciliationItemResponse[]
}

export interface ReconciliationCreate {
  reconciliation_date: string
  total_amount?: number
  total_count?: number
  notes?: string | null
  campus_id?: number | null
  items?: ReconciliationItemCreate[]
}

export interface ReconciliationItemCreate {
  payment_id: number
  expected_amount: number
  actual_amount: number
  notes?: string | null
}

export interface ReconciliationItemResponse {
  id: number
  reconciliation_id: number
  payment_id: number
  expected_amount: number
  actual_amount: number
  difference: number
  status: string
  notes: string | null
  created_at: string
}

export interface ReceiptResponse {
  id: number
  payment_id: number
  receipt_number: string
  receipt_date: string
  amount: number
  payment_method_name: string
  reference_number: string | null
  notes: string | null
  status: string
  printed_count: number
  generated_by: number | null
  campus_id: number | null
  created_at: string
  updated_at: string
}

export interface ReceiptGenerate {
  payment_id: number
  notes?: string | null
}

export interface ReceiptDetailResponse extends ReceiptResponse {
  student_name: string | null
  student_number: string | null
  fee_type_name: string | null
  academic_year_name: string | null
  class_name: string | null
  section_name: string | null
}

export interface FinanceReportResponse {
  id: number
  report_type: string
  title: string
  parameters: Record<string, unknown> | null
  file_format: string
  status: string
  campus_id: number | null
  generated_by: number | null
  error_message: string | null
  created_at: string
  completed_at: string | null
}

export interface FinanceReportGenerate {
  report_type: string
  title: string
  parameters?: Record<string, unknown> | null
  file_format?: string
  campus_id?: number | null
}

export interface OutstandingBalanceItem {
  student_id: number
  student_name: string | null
  student_number: string | null
  class_name: string | null
  section_name: string | null
  total_assigned: number
  total_paid: number
  outstanding: number
  due_count: number
  overdue_count: number
  status: string
}

export interface OutstandingBalanceSummary {
  total_students: number
  total_assigned: number
  total_paid: number
  total_outstanding: number
  total_overdue: number
  items: OutstandingBalanceItem[]
}

export interface SchoolFinanceDashboard {
  total_collected: number
  total_outstanding: number
  total_overdue: number
  payment_count: number
  reconciled_count: number
  pending_reconciliation: number
  collection_rate: number
  today_collection: number
  today_count: number
  recent_transactions: TransactionLogResponse[]
}

// ── P13 — financial exceptions (computed, read-only) ────────────────────

export interface LinkedCaseInfo {
  id: number
  case_number: string
  status: string
}

export interface FinancialException {
  key: string
  category: string
  severity: string
  title: string
  description: string
  student_id: number | null
  student_name: string | null
  payment_id: number | null
  amount: number | null
  reconciliation_item_id: number | null
  reconciliation_status: string | null
  evidence: Record<string, unknown>
  created_at: string | null
  linked_case: LinkedCaseInfo | null
}

export interface FinancialExceptionSummary {
  total: number
  by_category: Record<string, number>
  by_severity: Record<string, number>
  items: FinancialException[]
}

export type FinancialExceptionCategory =
  | 'reconciliation'
  | 'receipts'
  | 'ledger'
  | 'duplicates'

export interface Page<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

const BASE = '/api/school-finance'

export const paymentMethodApi = {
  create: (data: PaymentMethodCreate) =>
    api.post<PaymentMethodResponse>(`${BASE}/payment-methods`, data),

  get: (id: number) =>
    api.get<PaymentMethodResponse>(`${BASE}/payment-methods/${id}`),

  list: (params: SchoolFinanceListParams = {}) =>
    api.get<Page<PaymentMethodResponse>>(`${BASE}/payment-methods`, params as any),

  update: (id: number, data: PaymentMethodUpdate) =>
    api.patch<PaymentMethodResponse>(`${BASE}/payment-methods/${id}`, data),

  delete: (id: number) =>
    api.delete(`${BASE}/payment-methods/${id}`),
}

export const feeScheduleApi = {
  create: (data: FeeScheduleCreate) =>
    api.post<FeeScheduleResponse>(`${BASE}/fee-schedules`, data),

  get: (id: number) =>
    api.get<FeeScheduleResponse>(`${BASE}/fee-schedules/${id}`),

  list: (params: SchoolFinanceListParams = {}) =>
    api.get<Page<FeeScheduleResponse>>(`${BASE}/fee-schedules`, params as any),

  update: (id: number, data: FeeScheduleUpdate) =>
    api.patch<FeeScheduleResponse>(`${BASE}/fee-schedules/${id}`, data),

  delete: (id: number) =>
    api.delete(`${BASE}/fee-schedules/${id}`),

  getByFeeStructure: (feeStructureId: number) =>
    api.get<FeeScheduleResponse[]>(`${BASE}/fee-structures/${feeStructureId}/schedules`),
}

export const transactionLogApi = {
  get: (id: number) =>
    api.get<TransactionLogResponse>(`${BASE}/transactions/${id}`),

  list: (params: SchoolFinanceListParams = {}) =>
    api.get<Page<TransactionLogResponse>>(`${BASE}/transactions`, params as any),

  getStudentBalance: (studentId: number) =>
    api.get<{ balance: number }>(`${BASE}/transactions/student/${studentId}/balance`),
}

export const reconciliationApi = {
  create: (data: ReconciliationCreate) =>
    api.post<PaymentReconciliationResponse>(`${BASE}/reconciliations`, data),

  get: (id: number) =>
    api.get<PaymentReconciliationResponse>(`${BASE}/reconciliations/${id}`),

  list: (params: SchoolFinanceListParams = {}) =>
    api.get<Page<PaymentReconciliationResponse>>(`${BASE}/reconciliations`, params as any),

  verify: (id: number) =>
    api.post<PaymentReconciliationResponse>(`${BASE}/reconciliations/${id}/verify`),

  approve: (id: number) =>
    api.post<PaymentReconciliationResponse>(`${BASE}/reconciliations/${id}/approve`),
}

export const receiptApi = {
  generate: (data: ReceiptGenerate) =>
    api.post<ReceiptResponse>(`${BASE}/receipts/generate`, data),

  get: (id: number) =>
    api.get<ReceiptResponse>(`${BASE}/receipts/${id}`),

  getByNumber: (receiptNumber: string) =>
    api.get<ReceiptResponse>(`${BASE}/receipts/by-number/${encodeURIComponent(receiptNumber)}`),

  list: (params: SchoolFinanceListParams = {}) =>
    api.get<Page<ReceiptResponse>>(`${BASE}/receipts`, params as any),

  print: (id: number) =>
    api.get<Blob>(`${BASE}/receipts/${id}/print`),

  getDetail: (id: number) =>
    api.get<ReceiptDetailResponse>(`${BASE}/receipts/${id}/detail`),

  exportCsv: (params: SchoolFinanceListParams = {}) =>
    api.get<Blob>(`${BASE}/receipts/export/csv`, params as any),
}

export const outstandingBalanceApi = {
  getOutstanding: (params: SchoolFinanceListParams = {}) =>
    api.get<OutstandingBalanceSummary>(`${BASE}/outstanding-balances`, params as any),
}

export const financeReportApi = {
  generate: (data: FinanceReportGenerate) =>
    api.post<FinanceReportResponse>(`${BASE}/reports/generate`, data),

  listReports: (params: SchoolFinanceListParams = {}) =>
    api.get<Page<FinanceReportResponse>>(`${BASE}/reports`, params as any),

  exportCollectionSummaryCsv: (params: SchoolFinanceListParams = {}) =>
    api.get<Blob>(`${BASE}/reports/collection-summary/csv`, params as any),
}

export const schoolFinanceDashboardApi = {
  getDashboard: (params: SchoolFinanceListParams = {}) =>
    api.get<SchoolFinanceDashboard>(`${BASE}/dashboard`, params as any),
}

export const financialExceptionApi = {
  list: (params: SchoolFinanceListParams = {}) =>
    api.get<FinancialExceptionSummary>(`${BASE}/exceptions`, params as any),
}
