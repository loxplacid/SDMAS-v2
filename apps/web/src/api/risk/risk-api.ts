import { api } from '../client/http-client'

// ── Types ─────────────────────────────────────────────────────────────

export interface RiskFinding {
  id: number
  campus_id: number | null
  entity_type: string
  entity_id: number
  student_id: number | null
  rule_code: string
  category: string
  severity: string
  score: number
  reason: string
  recommended_action: string
  evidence: Record<string, unknown> | null
  status: 'open' | 'acknowledged' | 'resolved'
  detected_at: string
  last_verified_at: string
  resolved_at: string | null
  resolved_by: number | null
  resolved_reason: string | null
}

export interface RiskFindingPage {
  items: RiskFinding[]
  total: number
  page: number
  size: number
  pages: number
}

export interface RiskOverview {
  critical: number
  high: number
  medium: number
  low: number
  total: number
  by_category: Record<string, number>
}

export interface RecomputeResult {
  created: number
  updated: number
  resolved: number
  total_open: number
  run_at: string
}

export interface RuleConfig {
  rule_code: string
  category: string
  name: string
  description: string
  entity_type: string
  enabled: boolean
  thresholds: Record<string, unknown>
  severity_overrides: Record<string, unknown> | null
  defaults: Record<string, unknown>
  recommended_action: string
}

export interface RiskFindingParams {
  category?: string | null
  severity?: string | null
  status?: string | null
  page?: number
  size?: number
}

export interface RuleConfigUpdate {
  enabled?: boolean
  thresholds?: Record<string, unknown>
  severity_overrides?: Record<string, unknown>
}

export interface TeacherRiskFinding {
  id: number
  student_id: number | null
  student_name: string | null
  student_number: string | null
  class_id: number | null
  class_name: string | null
  rule_code: string
  category: string
  severity: string
  score: number
  reason: string
  recommended_action: string
  detected_at: string
  evidence: Record<string, unknown> | null
}

export interface TeacherRiskSummary {
  total: number
  by_severity: Record<string, number>
  findings: TeacherRiskFinding[]
}

// ── API client ────────────────────────────────────────────────────────

export const riskApi = {
  getOverview: () => api.get<RiskOverview>('/api/risk/overview'),

  getTeacherFindings: (teacherId: number) =>
    api.get<TeacherRiskSummary>('/api/risk/teacher-findings', { teacher_id: teacherId }),

  listFindings: (params: RiskFindingParams = {}) =>
    api.get<RiskFindingPage>('/api/risk/findings', {
      category: params.category,
      severity: params.severity,
      status: params.status,
      page: params.page,
      size: params.size,
    }),

  recompute: () => api.post<RecomputeResult>('/api/risk/recompute'),

  getConfig: () => api.get<RuleConfig[]>('/api/risk/config'),

  updateConfig: (ruleCode: string, data: RuleConfigUpdate) =>
    api.put<RuleConfig>(`/api/risk/config/${ruleCode}`, data),

  resolveFinding: (findingId: number, reason: string) =>
    api.post<RiskFinding>(`/api/risk/findings/${findingId}/resolve`, { reason }),

  acknowledgeFinding: (findingId: number) =>
    api.post<RiskFinding>(`/api/risk/findings/${findingId}/acknowledge`),
}
