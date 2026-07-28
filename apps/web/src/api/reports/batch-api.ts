import { api } from '../client/http-client'
import type { BatchEnrollInput, BatchEnrollResult, BatchFeeDueInput, BatchFeeDueResult } from './types'

export const batchApi = {
  enroll: (data: BatchEnrollInput) =>
    api.post<BatchEnrollResult>('/api/reports/batch/enroll', data),

  createFeeDues: (data: BatchFeeDueInput) =>
    api.post<BatchFeeDueResult>('/api/reports/batch/fee-dues', data),
}