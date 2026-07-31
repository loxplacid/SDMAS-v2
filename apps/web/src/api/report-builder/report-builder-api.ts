import { api } from '../client/http-client'

export type ReportBuilderListParams = {
  page?: number
  size?: number
  category?: string
  status?: string
}

export interface ReportFilterSchema { key: string; label: string; type: string; required?: boolean; options?: { value: string; label: string }[]; placeholder?: string | null }
export interface ReportColumnSchema { key: string; header: string; type?: string; format?: string | null }
export interface ReportDefinitionInfo { id: number; code: string; name: string; description: string | null; category: string; allowed_roles: string[]; filters: ReportFilterSchema[]; columns: ReportColumnSchema[]; default_params?: Record<string, any>; config?: any }
export interface ReportExecuteResponse { columns: ReportColumnSchema[]; rows: Record<string, any>[]; summary: Record<string, any>; total_rows: number }
export interface SavedReportResponse { id: number; user_id: number; report_definition_id: number; name: string; params: Record<string, any>; schedule?: Record<string, any> | null; created_at: string; updated_at: string }
export interface ExportJobResponse { id: number; user_id: number; report_definition_id: number; params: Record<string, any>; format: string; status: string; progress: number; total_rows: number | null; error_message: string | null; created_at: string; updated_at: string }
export interface Page<T> { items: T[]; total: number; page: number; size: number; pages: number }

const BASE = '/api/report-builder'

export const reportDefinitionApi = {
  list: (params?: ReportBuilderListParams) => api.get<ReportDefinitionInfo[]>(`${BASE}/definitions`, params as Record<string, string | number | boolean | undefined | null>),
  get: (code: string) => api.get<ReportDefinitionInfo>(`${BASE}/definitions/${code}`),
  categories: () => api.get<string[]>(`${BASE}/categories`),
  registry: (params?: { category?: string }) => api.get<ReportDefinitionInfo[]>(`${BASE}/registry`, params as Record<string, string | number | boolean | undefined | null>),
}

export const reportExecuteApi = {
  execute: (data: { report_definition_id: number; params: Record<string, any> }) =>
    api.post<ReportExecuteResponse>(`${BASE}/execute`, data),
}

export const savedReportApi = {
  create: (data: { report_definition_id: number; name: string; params?: Record<string, any> }) =>
    api.post<SavedReportResponse>(`${BASE}/saved`, data),
  list: (params?: ReportBuilderListParams) => api.get<Page<SavedReportResponse>>(`${BASE}/saved`, params as Record<string, string | number | boolean | undefined | null>),
  get: (id: number) => api.get<SavedReportResponse>(`${BASE}/saved/${id}`),
  update: (id: number, data: { name?: string; params?: Record<string, any> }) =>
    api.patch<SavedReportResponse>(`${BASE}/saved/${id}`, data),
  delete: (id: number) => api.delete(`${BASE}/saved/${id}`),
  listByDefinition: (definitionId: number) =>
    api.get<SavedReportResponse[]>(`${BASE}/saved/by-definition/${definitionId}`),
}

export const exportJobApi = {
  create: (data: { report_definition_id: number; params?: Record<string, any>; format?: string }) =>
    api.post<ExportJobResponse>(`${BASE}/exports`, data),
  list: (params?: ReportBuilderListParams) => api.get<Page<ExportJobResponse>>(`${BASE}/exports`, params as Record<string, string | number | boolean | undefined | null>),
  get: (id: number) => api.get<ExportJobResponse>(`${BASE}/exports/${id}`),
  download: (id: number) => api.get<Blob>(`${BASE}/exports/${id}/download`),
}
