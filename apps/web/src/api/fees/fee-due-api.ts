import { api } from '../client/http-client'
import type { FeeDueResponse, Page } from '../generated/types'

export type FeeDueListParams = {
  page?: number
  size?: number
  student_id?: number
  academic_year_id?: number
  status?: string
}

export const feeDueApi = {
  list: (params: FeeDueListParams = {}) =>
    api.get<Page<FeeDueResponse>>(
      '/api/fees/dues',
      params as Record<string, string | number | boolean | undefined | null>,
    ),

  getById: (dueId: number) =>
    api.get<FeeDueResponse>(`/api/fees/dues/${dueId}`),

  createDues: (studentId: number, academicYearId: number) =>
    api.post<FeeDueResponse[]>(
      `/api/fees/dues?student_id=${studentId}&academic_year_id=${academicYearId}`,
    ),

  getStudentDues: (studentId: number, params?: { academic_year_id?: number; status?: string }) =>
    api.get<FeeDueResponse[]>(
      `/api/fees/students/${studentId}/dues`,
      params as Record<string, string | number | boolean | undefined | null>,
    ),

  getStudentFees: (studentId: number, academicYearId: number) =>
    api.get(`/api/fees/students/${studentId}/fees`, { academic_year_id: academicYearId }),
}