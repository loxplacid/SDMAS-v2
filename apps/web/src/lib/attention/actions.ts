/**
 * P8 — Action Center attention model.
 *
 * A single, pure representation of "what needs your attention right now",
 * fed exclusively by real backend data:
 *   - command-center `needs_attention` alerts (computed deterministically by
 *     the API from live school data), and
 *   - risk-engine findings (real persisted rows with audited resolve /
 *     acknowledge endpoints).
 *
 * Nothing here is fabricated: severities, categories, counts and drill-down
 * targets all come from the API payloads. This module only normalizes the two
 * sources into one shape and provides grouping/filtering/ordering helpers —
 * all pure and unit-testable.
 */

import type { AttentionAlert } from '../../api/command-center/command-center-api'
import type { RiskFinding } from '../../api/risk/risk-api'

export type ActionSource = 'command' | 'risk'
export type ActionSeverity = 'critical' | 'high' | 'warning' | 'info'
export type ActionStatus = 'open' | 'acknowledged' | 'resolved'

/** Domain buckets used by the Action Center's filter tabs. */
export type ActionGroup = 'financial' | 'attendance' | 'system' | 'records'

export interface ActionItem {
  id: string
  source: ActionSource
  severity: ActionSeverity
  group: ActionGroup
  category: string
  title: string
  description: string
  actionLabel: string
  drillDown?: string | null
  count?: number | null
  status: ActionStatus
  /** Present only for risk-engine items (bulk resolution targets). */
  riskFindingId?: number
  detectedAt?: string
  resolvedAt?: string | null
  resolvedReason?: string | null
}

// ── Domain grouping (backend vocabulary → Action Center tabs) ─────────

const GROUP_BY_CATEGORY: Record<string, ActionGroup> = {
  fees: 'financial',
  finance: 'financial',
  payments: 'financial',
  billing: 'financial',
  attendance: 'attendance',
  admissions: 'records',
  academic: 'records',
  documents: 'records',
  approvals: 'system',
  rollover: 'system',
  risk: 'system',
  jobs: 'system',
  operational: 'system',
  system: 'system',
}

export function groupForCategory(category: string): ActionGroup {
  return GROUP_BY_CATEGORY[category] ?? 'system'
}

export const GROUP_LABELS: Record<ActionGroup, string> = {
  financial: 'Financial',
  attendance: 'Attendance',
  system: 'System',
  records: 'Records',
}

export const SEVERITY_ORDER: Record<ActionSeverity, number> = {
  critical: 0,
  high: 1,
  warning: 2,
  info: 3,
}

/** Map the risk engine's 4-level scale onto the shared severity ladder. */
function normalizeSeverity(severity: string): ActionSeverity {
  switch (severity) {
    case 'critical':
      return 'critical'
    case 'high':
      return 'high'
    case 'medium':
    case 'warning':
      return 'warning'
    default:
      return 'info'
  }
}

// ── Normalizers ───────────────────────────────────────────────────────

export function commandAlertToAction(alert: AttentionAlert): ActionItem {
  return {
    id: `cmd:${alert.id}`,
    source: 'command',
    severity: normalizeSeverity(alert.severity),
    group: groupForCategory(alert.category),
    category: alert.category,
    title: alert.title,
    description: alert.message,
    actionLabel: alert.action_label,
    drillDown: alert.drill_down ?? null,
    count: alert.count ?? null,
    // Command-center alerts are recomputed on every request — they are
    // always "open" until the underlying data changes. There is no resolve
    // endpoint for them, so no resolve affordance is offered.
    status: 'open',
  }
}

export function riskFindingToAction(finding: RiskFinding): ActionItem {
  const drill =
    finding.student_id != null
      ? `/students/${finding.student_id}/360`
      : finding.entity_type === 'admission_application'
        ? `/admissions/${finding.entity_id}`
        : null
  return {
    id: `risk:${finding.id}`,
    source: 'risk',
    severity: normalizeSeverity(finding.severity),
    group: groupForCategory(finding.category),
    category: finding.category,
    title: finding.reason,
    description: finding.recommended_action,
    actionLabel: finding.status === 'open' ? 'Open record' : 'View record',
    drillDown: drill,
    count: null,
    status: finding.status === 'resolved' ? 'resolved' : finding.status === 'acknowledged' ? 'acknowledged' : 'open',
    riskFindingId: finding.id,
    detectedAt: finding.detected_at,
    resolvedAt: finding.resolved_at,
    resolvedReason: finding.resolved_reason,
  }
}

/** Normalize both sources into one ordered list (critical first). */
export function toActionItems(alerts: AttentionAlert[], findings: RiskFinding[]): ActionItem[] {
  return [...alerts.map(commandAlertToAction), ...findings.map(riskFindingToAction)].sort(
    (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]
  )
}

// ── Filtering ─────────────────────────────────────────────────────────

export interface ActionFilters {
  group?: ActionGroup | null
  severity?: ActionSeverity | null
  status?: ActionStatus | null
  query?: string
}

export function filterActions(items: ActionItem[], filters: ActionFilters): ActionItem[] {
  const q = (filters.query ?? '').trim().toLowerCase()
  return items.filter((item) => {
    if (filters.group && item.group !== filters.group) return false
    if (filters.severity && item.severity !== filters.severity) return false
    if (filters.status && item.status !== filters.status) return false
    if (q) {
      const haystack = `${item.title} ${item.description} ${item.category} ${item.actionLabel}`.toLowerCase()
      if (!haystack.includes(q)) return false
    }
    return true
  })
}
