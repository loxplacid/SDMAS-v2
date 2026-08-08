import { api } from '../client/http-client'

// ── Types ─────────────────────────────────────────────────────────────

export type CaseStatus =
  | 'open'
  | 'acknowledged'
  | 'in_progress'
  | 'waiting'
  | 'resolved'
  | 'closed'

export type CasePriority = 'critical' | 'high' | 'medium' | 'low'

export type CaseType =
  | 'attendance'
  | 'finance'
  | 'academic'
  | 'documents'
  | 'data_quality'
  | 'admissions'
  | 'operational'
  | 'administrative'

export type CaseSourceType = 'manual' | 'risk_finding' | 'data_quality_finding'

export interface CaseItem {
  id: number
  case_number: string
  campus_id: number | null
  title: string
  description: string | null
  case_type: CaseType
  priority: CasePriority
  original_priority: CasePriority
  status: CaseStatus
  source_type: CaseSourceType
  source_id: number | null
  student_id: number | null
  created_by: number | null
  assigned_to: number | null
  assigned_at: string | null
  due_at: string | null
  escalated_at: string | null
  resolved_at: string | null
  resolved_by: number | null
  resolved_reason: string | null
  closed_at: string | null
  closed_by: number | null
  version: number
  created_at: string
  updated_at: string
  sla_state: 'ON_TRACK' | 'DUE_SOON' | 'OVERDUE' | 'RESOLVED'
  assignee_name: string | null
}

export interface CaseEventItem {
  id: number
  event_seq: number
  event_type: string
  actor_id: number | null
  actor_name: string | null
  message: string
  data: Record<string, unknown> | null
  created_at: string
}

export interface CaseCommentItem {
  id: number
  author_id: number | null
  author_name: string | null
  body: string
  created_at: string
}

export interface CaseEvidenceItem {
  id: number
  kind: string
  title: string
  summary: string | null
  reference_type: string | null
  reference_id: number | null
  data: Record<string, unknown> | null
  added_by: number | null
  created_at: string
}

export interface CaseDetail {
  case: CaseItem
  events: CaseEventItem[]
  comments: CaseCommentItem[]
  evidence: CaseEvidenceItem[]
}

export interface CasePage {
  items: CaseItem[]
  total: number
  page: number
  size: number
  pages: number
}

export interface CaseOverview {
  open: number
  critical: number
  overdue: number
  due_today: number
  my_open: number
  unassigned: number
  by_status: Record<string, number>
  generated_at: string
}

export interface CaseMetrics {
  open: number
  critical: number
  overdue: number
  due_today: number
  by_type: Record<string, number>
  by_priority: Record<string, number>
  avg_resolution_hours: number | null
  median_resolution_hours: number | null
  resolution_rate: number | null
  sla_compliance: number | null
  generated_at: string
}

export interface WorkloadItem {
  assignee_id: number
  assignee_name: string | null
  open_cases: number
  critical_cases: number
  overdue_cases: number
}

export interface AssignableUser {
  id: number
  name: string
  role: string
}

export interface BulkResult {
  updated: number[]
  skipped: number
}

export interface EscalationResult {
  escalated: number[]
  count: number
}

export interface CaseListParams {
  view?: 'all' | 'my' | 'unassigned' | 'open' | 'overdue' | 'due_soon' | 'resolved'
  status?: CaseStatus | null
  priority?: CasePriority | null
  case_type?: CaseType | null
  assignee_id?: number | null
  source_type?: CaseSourceType | null
  search?: string | null
  sort?: 'priority' | 'due' | 'created' | 'updated'
  page?: number
  size?: number
}

export interface CaseCreateParams {
  title: string
  description?: string | null
  case_type?: CaseType
  priority?: CasePriority | null
  source_type?: CaseSourceType
  source_id?: number | null
  student_id?: number | null
  assigned_to?: number | null
  due_at?: string | null
}

// ── API client ────────────────────────────────────────────────────────

export const casesApi = {
  list: (params: CaseListParams = {}) =>
    api.get<CasePage>('/api/cases', {
      view: params.view,
      status: params.status,
      priority: params.priority,
      case_type: params.case_type,
      assignee_id: params.assignee_id,
      source_type: params.source_type,
      search: params.search,
      sort: params.sort,
      page: params.page,
      size: params.size,
    }),

  overview: () => api.get<CaseOverview>('/api/cases/overview'),

  metrics: () => api.get<CaseMetrics>('/api/cases/metrics'),

  workload: () => api.get<WorkloadItem[]>('/api/cases/workload'),

  assignable: () => api.get<AssignableUser[]>('/api/cases/assignable'),

  get: (caseId: number) => api.get<CaseDetail>(`/api/cases/${caseId}`),

  create: (params: CaseCreateParams) =>
    api.post<CaseItem>('/api/cases', params),

  transition: (caseId: number, status: CaseStatus, reason?: string | null, version?: number) =>
    api.post<CaseItem>(`/api/cases/${caseId}/transition`, { status, reason, version }),

  assign: (caseId: number, assigneeId: number, reason?: string | null, version?: number) =>
    api.post<CaseItem>(`/api/cases/${caseId}/assign`, { assignee_id: assigneeId, reason, version }),

  changePriority: (caseId: number, priority: CasePriority, reason?: string | null, version?: number) =>
    api.post<CaseItem>(`/api/cases/${caseId}/priority`, { priority, reason, version }),

  setDueDate: (caseId: number, dueAt: string | null, reason?: string | null, version?: number) =>
    api.post<CaseItem>(`/api/cases/${caseId}/due-date`, { due_at: dueAt, reason, version }),

  addComment: (caseId: number, body: string) =>
    api.post<CaseCommentItem>(`/api/cases/${caseId}/comment`, { body }),

  addEvidence: (caseId: number, params: {
    kind: string
    title: string
    summary?: string | null
    reference_type?: string | null
    reference_id?: number | null
    metadata?: Record<string, unknown> | null
  }) =>
    api.post<CaseEvidenceItem>(`/api/cases/${caseId}/evidence`, params),

  bulkAssign: (caseIds: number[], assigneeId: number) =>
    api.post<BulkResult>('/api/cases/bulk/assign', { case_ids: caseIds, assignee_id: assigneeId }),

  bulkPriority: (caseIds: number[], priority: CasePriority, reason?: string | null) =>
    api.post<BulkResult>('/api/cases/bulk/priority', { case_ids: caseIds, priority, reason }),

  bulkStatus: (caseIds: number[], status: CaseStatus, reason?: string | null) =>
    api.post<BulkResult>('/api/cases/bulk/status', { case_ids: caseIds, status, reason }),

  bulkDueDate: (caseIds: number[], dueAt: string | null) =>
    api.post<BulkResult>('/api/cases/bulk/due-date', { case_ids: caseIds, due_at: dueAt }),

  escalate: () => api.post<EscalationResult>('/api/cases/escalate'),
}
