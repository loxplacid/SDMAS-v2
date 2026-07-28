import { api } from '../client/http-client'
import type { PaymentResponse, PaymentCreate, PaymentResult, Page } from '../generated/types'

export type PaymentListParams = {
  page?: number
  size?: number
  student_id?: number
  fee_due_id?: number
}

export const paymentApi = {
  list: (params: PaymentListParams = {}) =>
    api.get<Page<PaymentResponse>>(
      '/api/fees/payments',
      params as Record<string, string | number | boolean | undefined | null>,
    ),

  getById: (paymentId: number) =>
    api.get<PaymentResponse>(`/api/fees/payments/${paymentId}`),

  record: (data: PaymentCreate) =>
    api.post<PaymentResult>('/api/fees/payments', data),

  getStudentPayments: (studentId: number) =>
    api.get<PaymentResponse[]>(`/api/fees/students/${studentId}/payments`),

  getFeeDuePayments: (feeDueId: number) =>
    api.get<PaymentResponse[]>(`/api/fees/dues/${feeDueId}/payments`),

  getByDateRange: (startDate: string, endDate: string) =>
    api.get<PaymentResponse[]>('/api/fees/payments/by-date-range', { start_date: startDate, end_date: endDate }),

  getByReceiptNumber: (receiptNumber: string) =>
    api.get<PaymentResponse>(`/api/fees/payments/by-receipt/${receiptNumber}`),
}