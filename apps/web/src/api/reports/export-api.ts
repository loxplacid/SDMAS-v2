import { api } from '../client/http-client'

export type ExportParams = {
  status?: string
  search?: string
  section_id?: number
  start_date?: string
  end_date?: string
  academic_year_id?: number
}

export const exportApi = {
  students: (params: ExportParams = {}) =>
    api.get<Blob>('/api/reports/export/students',
      params as Record<string, string | number | boolean | undefined | null>,
    ),

  attendance: (params: ExportParams = {}) =>
    api.get<Blob>('/api/reports/export/attendance',
      params as Record<string, string | number | boolean | undefined | null>,
    ),

  payments: (params: ExportParams = {}) =>
    api.get<Blob>('/api/reports/export/payments',
      params as Record<string, string | number | boolean | undefined | null>,
    ),
}