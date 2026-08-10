import { describe, it, expect } from 'vitest'
import { buildCommandGroups } from '../lib/nav/command-groups'

const navigate = () => {}

function labelsFor(role: string, groupLabel: string): string[] {
  return buildCommandGroups(navigate, role)
    .find((g) => g.label === groupLabel)
    ?.items.map((i) => i.label) ?? []
}

function keywordsFor(role: string, pageLabel: string): string[] {
  const groups = buildCommandGroups(navigate, role)
  const items = groups.flatMap((g) => g.items)
  return items.find((i) => i.label === pageLabel)?.keywords ?? []
}

describe('buildCommandGroups — role filtering (D1 §3)', () => {
  it('admin sees the full page set including system surfaces', () => {
    const pages = labelsFor('admin', 'Pages')
    expect(pages).toContain('Command Center')
    expect(pages).toContain('Students')
    expect(pages).toContain('Users')
    expect(pages).toContain('Audit Logs')
    expect(pages).toContain('Data Ops')
  })

  it('teacher sees only teacher-scoped pages', () => {
    const pages = labelsFor('teacher', 'Pages')
    expect(pages).toContain('Dashboard')
    expect(pages).toContain('My Classes')
    expect(pages).not.toContain('Users')
    expect(pages).not.toContain('Data Ops')
    expect(pages).not.toContain('Command Center')
  })

  it('accountant sees finance-scoped pages but no system surfaces', () => {
    const pages = labelsFor('accountant', 'Pages')
    expect(pages).toContain('Fee Structures')
    expect(pages).toContain('Payments')
    expect(pages).not.toContain('Users')
    expect(pages).not.toContain('Students')
  })

  it('student sees portal pages only', () => {
    const pages = labelsFor('student', 'Pages')
    expect(pages).toContain('Timetable')
    expect(pages).toContain('My Fees')
    expect(pages).not.toContain('Users')
    expect(pages).not.toContain('Command Center')
  })

  it('never returns a Pages group with zero items', () => {
    for (const role of ['admin', 'principal', 'accountant', 'staff', 'teacher', 'student', 'parent']) {
      const pages = labelsFor(role, 'Pages')
      expect(pages.length).toBeGreaterThan(0)
    }
  })

  it('actions are gated by route access', () => {
    const adminActions = labelsFor('admin', 'Actions')
    expect(adminActions).toContain('Add Student')
    expect(adminActions).toContain('Record Payment')

    const accountantActions = labelsFor('accountant', 'Actions')
    expect(accountantActions).toContain('Record Payment')
    expect(accountantActions).not.toContain('Add Student')

    const studentActions = labelsFor('student', 'Actions')
    expect(studentActions.length).toBe(0)

    const teacherActions = labelsFor('teacher', 'Actions')
    expect(teacherActions).toContain('Record Attendance')
    expect(teacherActions).not.toContain('Record Payment')

    // Principal mirrors its nav (Attendance/Communications are leadership ops).
    const principalActions = labelsFor('principal', 'Actions')
    expect(principalActions).toContain('Record Attendance')
  })

  it('keeps natural command phrases searchable via keywords', () => {
    // "health" must still surface Command Center; "export" must surface Data Ops.
    expect(keywordsFor('admin', 'Command Center')).toContain('health')
    expect(keywordsFor('admin', 'Command Center')).toContain('home')
    expect(keywordsFor('admin', 'Data Ops')).toContain('export')
    expect(keywordsFor('admin', 'Work Queue')).toContain('overdue')
  })
})
