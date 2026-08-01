import { api } from '../client/http-client'

// ── Types ─────────────────────────────────────────────────────────────

export interface Metric {
  key: string
  label: string
  value: number
  display: string
  status: 'good' | 'warn' | 'critical' | 'neutral' | 'info'
  drill_down?: string | null
  trend?: number | null
}

export interface TrendPoint {
  label: string
  value: number
}

export interface SchoolHealth {
  available: boolean
  metrics: Metric[]
  trends: Record<string, TrendPoint[]>
}

export interface AttentionAlert {
  id: string
  severity: 'critical' | 'warning' | 'info'
  category: string
  title: string
  message: string
  count?: number | null
  action_label: string
  drill_down?: string | null
}

export interface NeedsAttention {
  available: boolean
  alerts: AttentionAlert[]
}

export interface TodayEvent {
  id: string
  type: 'attendance' | 'payment' | 'admission' | 'approval' | 'leave' | 'announcement'
  title: string
  description: string
  time?: string | null
  drill_down?: string | null
}

export interface TodaySection {
  available: boolean
  events: TodayEvent[]
}

export interface QuickAction {
  id: string
  label: string
  description: string
  route: string
  icon: string
}

export interface CommandCenterOverview {
  generated_at: string
  role: string
  campus_id?: number | null
  academic_year?: string | null
  sections: Record<string, boolean>
  school_health: SchoolHealth
  needs_attention: NeedsAttention
  today: TodaySection
  quick_actions: QuickAction[]
}

// ── API client ────────────────────────────────────────────────────────

export const commandCenterApi = {
  getOverview: () =>
    api.get<CommandCenterOverview>('/api/command-center/overview'),
}
