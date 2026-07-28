import { api } from '../client/http-client'
import type { ClassResponse, ClassCreate, ClassUpdate, Page } from '../generated/types'

export type ClassListParams = {
  page?: number
  size?: number
  academic_year_id?: number
  status?: string
}

export const classApi = {
  list: (params: ClassListParams = {}) =>
    api.get<Page<ClassResponse>>('/api/classes', params as Record<string, string | number | boolean | undefined | null>),

  getById: (id: number) =>
    api.get<ClassResponse>(`/api/classes/${id}`),

  create: (data: ClassCreate) =>
    api.post<ClassResponse>('/api/classes', data),

  update: (id: number, data: ClassUpdate) =>
    api.patch<ClassResponse>(`/api/classes/${id}`, data),

  delete: (id: number) =>
    api.delete<void>(`/api/classes/${id}`),
}