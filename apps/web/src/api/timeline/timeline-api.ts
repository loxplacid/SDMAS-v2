import { api } from '../client/http-client'

// ── Types ─────────────────────────────────────────────────────────────

export interface TimelineItem {
  id: string
  event_type: string
  timestamp: string
  actor: string
  entity: string
  description: string
  severity: 'info' | 'success' | 'warning' | 'critical'
  source: string
  metadata: Record<string, unknown>
  deep_link?: string | null
}

export interface TimelineSourceInfo {
  key: string
  label: string
  count: number
  available: boolean
}

export interface TimelineResponse {
  items: TimelineItem[]
  total: number
  page: number
  page_size: number
  sources: TimelineSourceInfo[]
  degraded: boolean
}

export interface TimelineParams {
  entity_type?: 'school' | 'student' | 'class' | 'teacher'
  entity_id?: number
  source?: string
  event_type?: string
  actor?: string
  start?: string
  end?: string
  page?: number
  page_size?: number
}

// ── API client ────────────────────────────────────────────────────────

export const timelineApi = {
  get: (params: TimelineParams = {}) =>
    api.get<TimelineResponse>('/api/timeline', {
      entity_type: params.entity_type,
      entity_id: params.entity_id,
      source: params.source,
      event_type: params.event_type,
      actor: params.actor,
      start: params.start,
      end: params.end,
      page: params.page,
      page_size: params.page_size,
    }),
}
