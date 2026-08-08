import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { useDelight, DelightProvider } from '../components/delight/delight-provider'
import {
  MILESTONE_MAP,
  milestoneScopeKey,
  milestoneCount,
  tryFireMilestone,
  type MilestoneContext,
} from '../components/delight/registry'

// DelightProvider derives the campus scope from the auth user — mock the
// hook so the provider mounts without an AuthProvider in these tests.
vi.mock('../api/auth/auth-context', () => ({
  useAuth: () => ({ user: { campus_id: 7 } }),
}))

/**
 * Milestone registry (Glint §5/§10): first-of-kind moments fire once per
 * campus and persist; the provider renders one AchievementToast at a time
 * (replace, never stack). localStorage is real in jsdom — the tests clear it
 * so each case starts with a fresh quota book.
 */

const ctx: MilestoneContext = { campusId: 7 }

beforeEach(() => {
  localStorage.clear()
})

describe('milestone registry — quota & persistence (Glint §5.1)', () => {
  it('fires a once-milestone the first time, then never again (per campus)', () => {
    const milestone = MILESTONE_MAP.get('first-student')!

    expect(tryFireMilestone(milestone, ctx)).toBe(true)
    expect(milestoneCount('first-student', ctx)).toBe(1)

    // Second attempt — same campus: quota exhausted.
    expect(tryFireMilestone(milestone, ctx)).toBe(false)
    expect(milestoneCount('first-student', ctx)).toBe(1)
  })

  it('scopes bookkeeping per campus', () => {
    const milestone = MILESTONE_MAP.get('first-student')!

    tryFireMilestone(milestone, { campusId: 1 })
    // A different campus still gets its own first-of-kind.
    expect(tryFireMilestone(milestone, { campusId: 2 })).toBe(true)
    expect(milestoneCount('first-student', { campusId: 2 })).toBe(1)
  })

  it('persists across reloads (localStorage)', () => {
    const milestone = MILESTONE_MAP.get('first-class')!

    tryFireMilestone(milestone, ctx)
    // Simulate a reload: the state is re-read from storage.
    expect(milestoneCount('first-class', ctx)).toBe(1)
    expect(tryFireMilestone(milestone, ctx)).toBe(false)
  })

  it('never fires a milestone that is not in the registry', () => {
    expect(MILESTONE_MAP.has('invented-milestone')).toBe(false)
  })

  it('builds a school-year-scoped key when a year is provided', () => {
    expect(milestoneScopeKey({ campusId: 7, schoolYear: '2026-27' })).toBe('7::2026-27')
    expect(milestoneScopeKey({ campusId: 7 })).toBe('7')
  })
})

function Trigger({ id, ctx }: { id: string; ctx?: MilestoneContext }) {
  const { celebrate } = useDelight()
  return <button onClick={() => celebrate(id, ctx)}>Celebrate</button>
}

function renderProvider(ui: React.ReactNode) {
  return render(<DelightProvider>{ui}</DelightProvider>)
}

describe('DelightProvider — the L4 moment (Glint §5.2/§10)', () => {
  it('renders the achievement toast for a due milestone', async () => {
    renderProvider(<Trigger id="first-student" ctx={ctx} />)

    fireEvent.click(screen.getByText('Celebrate'))

    // Own role=status region (never the shared toast live region).
    expect(await screen.findByRole('status')).toBeInTheDocument()
    expect(screen.getByText('First student enrolled')).toBeInTheDocument()
  })

  it('does not stack — a second milestone replaces the first', async () => {
    renderProvider(
      <>
        <Trigger id="first-student" ctx={ctx} />
        <Trigger id="first-teacher" ctx={ctx} />
      </>
    )

    fireEvent.click(screen.getAllByText('Celebrate')[0])
    fireEvent.click(screen.getAllByText('Celebrate')[1])

    await waitFor(() => expect(screen.getByText('First teacher added')).toBeInTheDocument())
    // Exactly one achievement toast is mounted (the first was replaced).
    expect(screen.getAllByRole('status')).toHaveLength(1)
  })

  it('is a quiet no-op once the quota is exhausted', async () => {
    const milestone = MILESTONE_MAP.get('first-student')!
    tryFireMilestone(milestone, ctx) // already fired (once)

    renderProvider(<Trigger id="first-student" ctx={ctx} />)
    fireEvent.click(screen.getByText('Celebrate'))

    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument())
    expect(screen.queryByText('First student enrolled')).not.toBeInTheDocument()
  })

  it('does nothing for unknown milestone ids', () => {
    renderProvider(<Trigger id="not-a-milestone" />)
    fireEvent.click(screen.getByText('Celebrate'))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
