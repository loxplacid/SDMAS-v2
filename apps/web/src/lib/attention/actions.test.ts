import { describe, it, expect } from 'vitest'
import {
  toActionItems,
  filterActions,
  groupForCategory,
  commandAlertToAction,
  riskFindingToAction,
  type ActionFilters,
} from './actions'
import type { AttentionAlert } from '../../api/command-center/command-center-api'
import type { RiskFinding } from '../../api/risk/risk-api'

const alert = (overrides: Partial<AttentionAlert> = {}): AttentionAlert => ({
  id: 'low-attendance',
  severity: 'warning',
  category: 'attendance',
  title: '12 students below 75% attendance',
  message: 'Students are flagged after 5+ recorded days.',
  count: 12,
  action_label: 'View students',
  drill_down: '/attendance-intelligence/dashboard',
  ...overrides,
})

const finding = (overrides: Partial<RiskFinding> = {}): RiskFinding => ({
  id: 41,
  campus_id: 1,
  entity_type: 'student',
  entity_id: 7,
  student_id: 7,
  rule_code: 'low_attendance',
  category: 'attendance',
  severity: 'high',
  score: 0.86,
  reason: 'Attendance below threshold',
  recommended_action: 'Review and contact the family',
  evidence: null,
  status: 'open',
  detected_at: '2026-08-01T09:00:00Z',
  last_verified_at: '2026-08-01T09:00:00Z',
  resolved_at: null,
  resolved_by: null,
  resolved_reason: null,
  ...overrides,
})

describe('groupForCategory', () => {
  it('maps backend category vocabulary onto the Action Center domains', () => {
    expect(groupForCategory('fees')).toBe('financial')
    expect(groupForCategory('finance')).toBe('financial')
    expect(groupForCategory('attendance')).toBe('attendance')
    expect(groupForCategory('jobs')).toBe('system')
    expect(groupForCategory('approvals')).toBe('system')
    expect(groupForCategory('admissions')).toBe('records')
    expect(groupForCategory('documents')).toBe('records')
    expect(groupForCategory('unknown-future-category')).toBe('system')
  })
})

describe('toActionItems', () => {
  it('normalizes both sources and orders critical first', () => {
    const items = toActionItems(
      [
        alert({ id: 'a-info', severity: 'info' }),
        alert({ id: 'a-crit', severity: 'critical', title: 'Severe issue' }),
      ],
      [finding({ severity: 'high' })]
    )
    expect(items.map((i) => i.severity)).toEqual(['critical', 'high', 'info'])
    expect(items[0].title).toBe('Severe issue')
  })

  it('flags risk items with their finding id and status', () => {
    const [item] = toActionItems([], [finding()])
    expect(item.source).toBe('risk')
    expect(item.riskFindingId).toBe(41)
    expect(item.status).toBe('open')
    expect(item.drillDown).toBe('/students/7/360')
  })

  it('maps risk severity levels onto the shared ladder', () => {
    const [item] = toActionItems([], [finding({ severity: 'medium' })])
    expect(item.severity).toBe('warning')
  })

  it('resolved findings carry resolved status and drill-down', () => {
    const [item] = toActionItems(
      [],
      [finding({ status: 'resolved', resolved_at: '2026-08-02T10:00:00Z', resolved_reason: 'Paid in cash' })]
    )
    expect(item.status).toBe('resolved')
    expect(item.resolvedReason).toBe('Paid in cash')
  })

  it('command alerts are always open (no resolve endpoint exists)', () => {
    const [item] = toActionItems([alert()], [])
    expect(item.status).toBe('open')
    expect(item.source).toBe('command')
  })
})

describe('filterActions', () => {
  const items = toActionItems(
    [
      alert({ id: 'att', category: 'attendance', severity: 'critical', title: 'Low attendance', message: '12 students' }),
      alert({ id: 'fees', category: 'fees', severity: 'warning', title: 'Overdue fees', message: '₹12.4L overdue' }),
      alert({ id: 'jobs', category: 'jobs', severity: 'info', title: 'Failed jobs', message: '3 failed' }),
    ],
    [finding()]
  )

  it('filters by domain group', () => {
    const out = filterActions(items, { group: 'financial' })
    expect(out.map((i) => i.title)).toEqual(['Overdue fees'])
  })

  it('filters by severity', () => {
    const out = filterActions(items, { severity: 'critical' })
    expect(out.map((i) => i.title)).toEqual(['Low attendance'])
  })

  it('filters by status', () => {
    const out = filterActions(items, { status: 'open' })
    expect(out.length).toBe(items.length)
    const resolved = filterActions(items, { status: 'resolved' })
    expect(resolved.length).toBe(0)
  })

  it('searches title, description and category case-insensitively', () => {
    const byTitle = filterActions(items, { query: 'overdue' })
    expect(byTitle.map((i) => i.title)).toEqual(['Overdue fees'])

    const byCategory = filterActions(items, { query: 'ATTENDANCE' })
    expect(byCategory.length).toBe(2) // command alert + risk finding
  })

  it('applies multiple filters together', () => {
    const filters: ActionFilters = { group: 'attendance', severity: 'critical' }
    const out = filterActions(items, filters)
    expect(out.map((i) => i.title)).toEqual(['Low attendance'])
  })

  it('returns everything when no filters are set', () => {
    expect(filterActions(items, {}).length).toBe(items.length)
  })
})
