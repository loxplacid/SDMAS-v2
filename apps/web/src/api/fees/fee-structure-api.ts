import { api } from '../client/http-client'
import type { FeeStructureResponse, FeeStructureCreate, FeeStructureUpdate, Page } from '../generated/types'

export type FeeStructureListParams = {
  page?: number
  size?: number
  academic_year_id?: number
  class_id?: number
  fee_type_id?: number
  status?: string
}

export const feeStructureApi = {
  list: (params: FeeStructureListParams = {}) =>
    api.get<Page<FeeStructureResponse>>(
      '/api/fees/structures',
      params as Record<string, string | number | boolean | undefined | null>,
    ),

  getById: (structureId: number) =>
    api.get<FeeStructureResponse>(`/api/fees/structures/${structureId}`),

  create: (data: FeeStructureCreate) =>
    api.post<FeeStructureResponse>('/api/fees/structures', data),

  update: (structureId: number, data: FeeStructureUpdate) =>
    api.patch<FeeStructureResponse>(`/api/fees/structures/${structureId}`, data),
}