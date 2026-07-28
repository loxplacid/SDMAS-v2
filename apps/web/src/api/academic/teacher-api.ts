import { api } from '../client/http-client'
import type { TeacherResponse, TeacherCreate, TeacherUpdate, Page } from '../generated/types'

export type TeacherListParams = {
  page?: number
  size?: number
  status?: string
}

export const teacherApi = {
  list: (params: TeacherListParams = {}) =>
    api.get<Page<TeacherResponse>>('/api/teachers', params as Record<string, string | number | boolean | undefined | null>),

  getById: (id: number) =>
    api.get<TeacherResponse>(`/api/teachers/${id}`),

  create: (data: TeacherCreate) =>
    api.post<TeacherResponse>('/api/teachers', data),

  update: (id: number, data: TeacherUpdate) =>
    api.patch<TeacherResponse>(`/api/teachers/${id}`, data),
}