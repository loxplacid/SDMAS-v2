import { api } from '../client/http-client'
import type { FeeTypeResponse, FeeTypeCreate, FeeTypeUpdate, Page } from '../generated/types'

export type FeeTypeListParams = {
  page?: number
  size?: number
  status?: string
}

export const feeTypeApi = {
  list: (params: FeeTypeListParams = {}) =>
    api.get<Page<FeeTypeResponse>>(
      '/api/fees/fee-types',
      params as Record<string, string | number | boolean | undefined | null>,
    ),

  getById: (typeId: number) =>
    api.get<FeeTypeResponse>(`/api/fees/fee-types/${typeId}`),

  create: (data: FeeTypeCreate) =>
    api.post<FeeTypeResponse>('/api/fees/fee-types', data),

  update: (typeId: number, data: FeeTypeUpdate) =>
    api.patch<FeeTypeResponse>(`/api/fees/fee-types/${typeId}`, data),

  deactivate: (typeId: number) =>
    api.post<FeeTypeResponse>(`/api/fees/fee-types/${typeId}/deactivate`),
}