import { api } from '../client/http-client'
import type { AcademicYearResponse, AcademicYearCreate, AcademicYearUpdate, Page } from '../generated/types'

export type AcademicYearListParams = {
  page?: number
  size?: number
  status?: string
}

export const academicYearApi = {
  list: (params: AcademicYearListParams = {}) =>
    api.get<Page<AcademicYearResponse>>('/api/academic-years', params as Record<string, string | number | boolean | undefined | null>),

  getById: (id: number) =>
    api.get<AcademicYearResponse>(`/api/academic-years/${id}`),

  create: (data: AcademicYearCreate) =>
    api.post<AcademicYearResponse>('/api/academic-years', data),

  update: (id: number, data: AcademicYearUpdate) =>
    api.patch<AcademicYearResponse>(`/api/academic-years/${id}`, data),

  delete: (id: number) =>
    api.delete<void>(`/api/academic-years/${id}`),
}