import { describe, it, expect, vi } from 'vitest'
import { buildContextualCommands, buildRecentCommands } from '../lib/nav/contextual-commands'

/**
 * P8 §10 — the palette's route-aware commands. Only existing routes are
 * wired; these tests lock the route → action mapping (and that overview
 * routes stay quiet).
 */
describe('buildContextualCommands (P8 §10)', () => {
  it('offers student commands on the students route', () => {
    const navigate = vi.fn()
    const cmds = buildContextualCommands('/students', navigate)
    const labels = cmds.map((c) => c.label)
    expect(labels).toContain('Add Student')
    expect(labels).toContain('Export Students')
    expect(labels).toContain('Batch Enroll')

    cmds.find((c) => c.id === 'ctx-student-add')!.action()
    expect(navigate).toHaveBeenCalledWith('/students?action=add')
  })

  it('inherits commands on detail sub-routes', () => {
    const navigate = vi.fn()
    const cmds = buildContextualCommands('/students/42', navigate)
    expect(cmds.some((c) => c.id === 'ctx-student-add')).toBe(true)
  })

  it('offers finance commands on fee routes', () => {
    const navigate = vi.fn()
    const cmds = buildContextualCommands('/fees', navigate)
    expect(cmds.some((c) => c.id === 'ctx-payment')).toBe(true)
    expect(cmds.some((c) => c.id === 'ctx-fee-summary')).toBe(true)
  })

  it('offers attendance commands on attendance sub-routes', () => {
    const navigate = vi.fn()
    const cmds = buildContextualCommands('/attendance/daily', navigate)
    expect(cmds.some((c) => c.id === 'ctx-attendance-daily')).toBe(true)
  })

  it('offers report commands on the reports hub', () => {
    const navigate = vi.fn()
    const cmds = buildContextualCommands('/reports', navigate)
    expect(cmds.some((c) => c.id === 'ctx-report-attendance')).toBe(true)
    expect(cmds.some((c) => c.id === 'ctx-report-builder')).toBe(true)
  })

  it('stays quiet on overview routes', () => {
    expect(buildContextualCommands('/command-center', vi.fn())).toEqual([])
    expect(buildContextualCommands('/risk', vi.fn())).toEqual([])
    expect(buildContextualCommands('/timeline', vi.fn())).toEqual([])
  })

  it('never registers a command that navigates nowhere', () => {
    const navigate = vi.fn()
    const cmds = buildContextualCommands('/students', navigate)
    for (const cmd of cmds) {
      cmd.action()
      expect(navigate).toHaveBeenCalled()
      navigate.mockClear()
    }
  })
})

/**
 * P8 §9 — the palette's "Recent" group surfaces visited pages as commands.
 */
describe('buildRecentCommands (P8 §9)', () => {
  it('converts visited pages into palette commands', () => {
    const navigate = vi.fn()
    const cmds = buildRecentCommands(
      [
        { path: '/students', label: 'Students' },
        { path: '/fees/payments', label: 'Payments' },
      ],
      '/dashboard',
      navigate
    )
    expect(cmds).toHaveLength(2)
    expect(cmds[0].label).toBe('Students')
    expect(cmds[0].description).toBeUndefined()

    cmds[0].action()
    expect(navigate).toHaveBeenCalledWith('/students')
  })

  it('excludes the current route from the group', () => {
    const cmds = buildRecentCommands(
      [
        { path: '/students', label: 'Students' },
        { path: '/fees', label: 'Fees' },
      ],
      '/students',
      vi.fn()
    )
    expect(cmds.map((c) => c.label)).toEqual(['Fees'])
  })

  it('caps the list to keep the surface scannable', () => {
    const items = Array.from({ length: 20 }, (_, i) => ({ path: `/page-${i}`, label: `Page ${i}` }))
    const cmds = buildRecentCommands(items, '/current', vi.fn())
    expect(cmds).toHaveLength(6)
  })

  it('returns an empty list when history is empty', () => {
    expect(buildRecentCommands([], '/dashboard', vi.fn())).toEqual([])
  })
})
