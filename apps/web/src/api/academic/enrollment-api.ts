import { api } from '../client/http-client'
import type { EnrollmentResponse, EnrollmentCreate, EnrollmentUpdate, Page } from '../generated/types'

export type EnrollmentListParams = {
  page?: number
  size?: number
  student_id?: number
  academic_year_id?: number
  class_id?: number
  section_id?: number
}

export const enrollmentApi = {
  list: (params: EnrollmentListParams = {}) =>
    api.get<Page<EnrollmentResponse>>('/api/enrollments', params as Record<string, string | number | boolean | undefined | null>),

  getById: (id: number) =>
    api.get<EnrollmentResponse>(`/api/enrollments/${id}`),

  create: (data: EnrollmentCreate) =>
    api.post<EnrollmentResponse>('/api/enrollments', data),

  update: (id: number, data: EnrollmentUpdate) =>
    api.patch<EnrollmentResponse>(`/api/enrollments/${id}`, data),

  delete: (id: number) =>
    api.delete<void>(`/api/enrollments/${id}`),
}