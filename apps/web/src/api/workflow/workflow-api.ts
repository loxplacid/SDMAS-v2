import { api } from '../client/http-client'
import type { Page } from '../generated/types'

// ── Types ──

export interface WorkflowStepResponse {
  id: number
  workflow_id: number
  name: string
  label: string | null
  step_order: number
  is_initial: boolean
  is_final: boolean
  assigned_role: string | null
  created_at: string
}

export interface WorkflowTransitionResponse {
  id: number
  workflow_id: number
  from_step_id: number
  to_step_id: number
  label: string | null
  required_role: string | null
  created_at: string
}

export interface WorkflowResponse {
  id: number
  name: string
  code: string
  description: string | null
  entity_type: string
  status: string
  created_at: string
  updated_at: string
  steps?: WorkflowStepResponse[]
  transitions?: WorkflowTransitionResponse[]
}

export interface WorkflowDefinition {
  workflow: WorkflowResponse
  steps: WorkflowStepResponse[]
  transitions: WorkflowTransitionResponse[]
}

export interface WorkflowInstanceResponse {
  id: number
  workflow_id: number
  current_step_id: number
  campus_id: number | null
  entity_type: string
  entity_id: number
  status: string
  created_by: number | null
  created_at: string
  updated_at: string
}

export interface ApprovalHistoryEntry {
  id: number
  instance_id: number
  from_step_id: number | null
  to_step_id: number | null
  action: string
  actor_id: number | null
  comment: string | null
  created_at: string
}

export interface WorkflowInstanceDetail {
  id: number
  workflow_id: number
  current_step_id: number
  entity_type: string
  entity_id: number
  status: string
  created_by: number | null
  created_at: string
  updated_at: string
  workflow: WorkflowResponse | null
  history: ApprovalHistoryEntry[]
}

export interface AvailableTransition {
  transition_id: number
  from_step_id: number
  to_step_id: number
  label: string | null
  to_step_name: string
  to_step_label: string | null
  required_role: string | null
}

export interface WorkflowActionRequest {
  action: 'approve' | 'reject' | 'return' | 'submit' | 'cancel'
  comment?: string | null
  to_step_id?: number | null
}

// ── API calls ──

export const workflowApi = {
  // ── Workflow Definitions ──
  list: (params?: { status?: string; entity_type?: string; page?: number; size?: number }) => {
    return api.get<Page<WorkflowResponse>>('/api/workflows', {
      status: params?.status,
      entity_type: params?.entity_type,
      page: params?.page,
      size: params?.size,
      skip: params?.page ? (params.page - 1) * (params.size || 20) : undefined,
      limit: params?.size || 20,
    })
  },

  getDefinition: (workflowId: number) => {
    return api.get<WorkflowDefinition>(`/api/workflows/${workflowId}`)
  },

  // ── Workflow Instances ──
  listInstances: (params?: {
    status?: string
    entity_type?: string
    workflow_id?: number
    created_by?: number
    page?: number
    size?: number
  }) => {
    return api.get<Page<WorkflowInstanceResponse>>('/api/workflows/instances', {
      status: params?.status,
      entity_type: params?.entity_type,
      workflow_id: params?.workflow_id,
      created_by: params?.created_by,
      skip: params?.page ? (params.page - 1) * (params.size || 20) : undefined,
      limit: params?.size || 20,
    })
  },

  getInstance: (instanceId: number) => {
    return api.get<WorkflowInstanceDetail>(`/api/workflows/instances/${instanceId}`)
  },

  getInstanceByEntity: (entityType: string, entityId: number) => {
    return api.get<WorkflowInstanceDetail | null>(
      `/api/workflows/instances/by-entity/${entityType}/${entityId}`
    )
  },

  startInstance: (data: { workflow_id: number; entity_type: string; entity_id: number }) => {
    return api.post<WorkflowInstanceResponse>('/api/workflows/instances', data)
  },

  // ── Actions ──
  getAvailableTransitions: (instanceId: number) => {
    return api.get<AvailableTransition[]>(
      `/api/workflows/instances/${instanceId}/transitions`
    )
  },

  performAction: (instanceId: number, data: WorkflowActionRequest) => {
    return api.post<WorkflowInstanceResponse>(
      `/api/workflows/instances/${instanceId}/actions`,
      data
    )
  },
}

export type WorkflowApi = typeof workflowApi
