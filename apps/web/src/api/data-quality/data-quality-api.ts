import { api } from '../client/http-client'

// ── Types ─────────────────────────────────────────────────────────────

export interface DataQualityFinding {
  id: number
  campus_id: number | null
  check_code: string
  category: string
  severity: string
  entity_type: string
  entity_id: number
  student_id: number | null
  field: string
  description: string
  evidence: Record<string, unknown> | null
  status: 'open' | 'resolved' | 'ignored'
  detected_at: string
  last_verified_at: string
  resolved_at: string | null
  resolved_by: number | null
  resolved_reason: string | null
}

export interface DataQualityFindingPage {
  items: DataQualityFinding[]
  total: number
  page: number
  size: number
  pages: number
}

export interface DataQualityOverview {
  critical: number
  high: number
  medium: number
  low: number
  total: number
  by_category: Record<string, number>
  overall_quality: number
  severity_weights: Record<string, number>
  total_checks: number
}

export interface DataQualityRunResult {
  created: number
  updated: number
  resolved: number
  total_open: number
  run_at: string
}

export interface DataQualityFindingParams {
  category?: string | null
  severity?: string | null
  status?: string | null
  check_code?: string | null
  entity_type?: string | null
  page?: number
  size?: number
}

// ── API client ────────────────────────────────────────────────────────

export const dataQualityApi = {
  getOverview: () => api.get<DataQualityOverview>('/api/data-quality/overview'),

  listFindings: (params: DataQualityFindingParams = {}) =>
    api.get<DataQualityFindingPage>('/api/data-quality/findings', {
      category: params.category,
      severity: params.severity,
      status: params.status,
      check_code: params.check_code,
      entity_type: params.entity_type,
      page: params.page,
      size: params.size,
    }),

  /** P11 — single finding for deep-linking from a case back to its source. */
  getFinding: (findingId: number) => api.get<DataQualityFinding>(`/api/data-quality/findings/${findingId}`),

  runChecks: () => api.post<DataQualityRunResult>('/api/data-quality/run'),

  resolveFinding: (findingId: number, reason: string) =>
    api.post<DataQualityFinding>(`/api/data-quality/findings/${findingId}/resolve`, {
      reason,
    }),

  ignoreFinding: (findingId: number, reason: string) =>
    api.post<DataQualityFinding>(`/api/data-quality/findings/${findingId}/ignore`, {
      reason,
    }),
}
