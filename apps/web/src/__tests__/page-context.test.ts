import { describe, it, expect } from 'vitest'
import { getPageHierarchy } from '../lib/nav/page-context'

/**
 * P8 §7 — the shell header's contextual breadcrumbs resolve from the pure
 * `getPageHierarchy` registry. These tests lock in the section/page mapping.
 */
describe('getPageHierarchy (P8 §7)', () => {
  it('maps a top-level route to section + page', () => {
    expect(getPageHierarchy('/students')).toEqual([
      { label: 'Records', href: '/students' },
      { label: 'Students' },
    ])
  })

  it('maps sub-routes to their section and leaf page', () => {
    expect(getPageHierarchy('/attendance/records')).toEqual([
      { label: 'Operations', href: '/attendance' },
      { label: 'Records' },
    ])
    expect(getPageHierarchy('/fees/payments')).toEqual([
      { label: 'Finance', href: '/fees' },
      { label: 'Payments' },
    ])
  })

  it('resolves leadership routes to their section', () => {
    expect(getPageHierarchy('/command-center')).toEqual([
      { label: 'Leadership', href: '/command-center' },
      { label: 'Command Center' },
    ])
  })

  it('maps the dashboard to the overview section', () => {
    expect(getPageHierarchy('/dashboard')).toEqual([
      { label: 'Overview', href: '/dashboard' },
      { label: 'Dashboard' },
    ])
  })

  it('resolves detail routes to their entity page', () => {
    expect(getPageHierarchy('/students/42')).toEqual([
      { label: 'Records', href: '/students' },
      { label: 'Students' },
    ])
  })

  it('falls back to a humanized segment for unknown deep routes', () => {
    const crumbs = getPageHierarchy('/reports/builder/new')
    expect(crumbs[crumbs.length - 1].label).toBe('New')
  })

  it('returns a single crumb for unknown top-level routes', () => {
    expect(getPageHierarchy('/some-unknown')).toEqual([{ label: 'Some Unknown' }])
  })

  it('maps workspace dashboards to their section', () => {
    expect(getPageHierarchy('/student')).toEqual([
      { label: 'My Space', href: '/student' },
      { label: 'My Dashboard' },
    ])
  })
})
