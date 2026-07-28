import { api } from '../client/http-client'
import type { RolloverPreview, RolloverExecuteInput, RolloverResult } from './types'

export const rolloverApi = {
  preview: (data: RolloverExecuteInput) =>
    api.post<RolloverPreview>('/api/reports/rollover/preview', data),

  execute: (data: RolloverExecuteInput) =>
    api.post<RolloverResult>('/api/reports/rollover/execute', data),
}