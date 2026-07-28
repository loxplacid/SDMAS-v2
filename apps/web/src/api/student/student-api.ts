import { api } from '../client/http-client'
import type { StudentResponse, StudentCreate, StudentUpdate, Page } from '../generated/types'

export type StudentListParams = {
  page?: number
  size?: number
  search?: string
  status?: string
}

export const studentApi = {
  list: (params: StudentListParams = {}) =>
    api.get<Page<StudentResponse>>('/students', params as Record<string, string | number | boolean | undefined | null>),

  getById: (id: number) =>
    api.get<StudentResponse>(`/students/${id}`),

  create: (data: StudentCreate) =>
    api.post<StudentResponse>('/students', data, true),

  update: (id: number, data: StudentUpdate) =>
    api.patch<StudentResponse>(`/students/${id}`, data),

  delete: (id: number) =>
    api.delete<void>(`/students/${id}`),
}