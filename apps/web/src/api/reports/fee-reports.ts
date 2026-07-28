import { api } from '../client/http-client'
import type { CollectionReportItem, OutstandingReportItem, DetailedReceipt } from './types'

export type CollectionReportParams = {
  academic_year_id: number
  start_date?: string
  end_date?: string
}

export type OutstandingReportParams = {
  academic_year_id: number
  class_id?: number
}

export const feeReportApi = {
  getCollectionReport: (params: CollectionReportParams) =>
    api.get<CollectionReportItem[]>(
      '/api/reports/fees/collection',
      params as Record<string, string | number | boolean | undefined | null>,
    ),

  getOutstandingReport: (params: OutstandingReportParams) =>
    api.get<OutstandingReportItem[]>(
      '/api/reports/fees/outstanding',
      params as Record<string, string | number | boolean | undefined | null>,
    ),

  getReceipt: (paymentId: number) =>
    api.get<DetailedReceipt>(`/api/reports/receipts/${paymentId}`),
}