import { api } from '../client/http-client'
import type { Page } from '../generated/types'

export interface AuditLogEntry {
  id: number
  user_id: number | null
  username: string | null
  action: string
  resource_type: string
  resource_id: string | null
  details: Record<string, unknown> | string | null
  ip_address: string | null
  user_agent: string | null
  campus_id: number | null
  created_at: string
}

export interface AuditLogListParams {
  page?: number
  size?: number
  user_id?: number
  action?: string
  resource_type?: string
  resource_id?: string
  campus_id?: number
  start_date?: string
  end_date?: string
}

async function list(params: AuditLogListParams = {}): Promise<Page<AuditLogEntry>> {
  return api.get<Page<AuditLogEntry>>('/api/admin/audit-logs', {
    page: params.page || 1,
    size: params.size || 50,
    ...(params.user_id !== undefined && { user_id: params.user_id }),
    ...(params.action && { action: params.action }),
    ...(params.resource_type && { resource_type: params.resource_type }),
    ...(params.resource_id && { resource_id: params.resource_id }),
    ...(params.campus_id !== undefined && { campus_id: params.campus_id }),
    ...(params.start_date && { start_date: params.start_date }),
    ...(params.end_date && { end_date: params.end_date }),
  })
}

export const auditLogApi = { list }
