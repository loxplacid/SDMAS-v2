import { api } from '../client/http-client'
import type { TeacherAssignmentResponse, TeacherAssignmentCreate, Page } from '../generated/types'

export type TeacherAssignmentListParams = {
  page?: number
  size?: number
  class_id?: number
  teacher_id?: number
}

export const teacherAssignmentApi = {
  list: (params: TeacherAssignmentListParams = {}) =>
    api.get<Page<TeacherAssignmentResponse>>('/api/teacher-assignments', params as Record<string, string | number | boolean | undefined | null>),

  getById: (id: number) =>
    api.get<TeacherAssignmentResponse>(`/api/teacher-assignments/${id}`),

  create: (data: TeacherAssignmentCreate) =>
    api.post<TeacherAssignmentResponse>('/api/teacher-assignments', data),

  delete: (id: number) =>
    api.delete<void>(`/api/teacher-assignments/${id}`),
}