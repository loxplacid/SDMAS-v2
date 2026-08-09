import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { WorkflowStatus, type WorkflowStatusInstance } from '../components/workflow/workflow-status'

// ── Fixtures ──

const STEP_IDS = { submitted: 1, hod: 2, hr: 3, approved: 4 }

function makeInstance(
  overrides: Partial<WorkflowStatusInstance> = {}
): WorkflowStatusInstance {
  return {
    id: 42,
    status: 'active',
    current_step_id: STEP_IDS.hod,
    entity_type: 'leave_request',
    entity_id: 7,
    created_by: 1,
    created_at: '2026-08-01T08:00:00Z',
    workflow: {
      id: 1,
      name: 'Leave Request',
      code: 'LEAVE_REQUEST',
      steps: [
        { id: 1, name: 'submitted', label: 'Submitted', step_order: 1, is_initial: true, is_final: false, assigned_role: null },
        { id: 2, name: 'hod_approval', label: 'HOD Approval', step_order: 2, is_initial: false, is_final: false, assigned_role: 'hod' },
        { id: 3, name: 'hr_approval', label: 'HR Approval', step_order: 3, is_initial: false, is_final: false, assigned_role: 'hr' },
        { id: 4, name: 'approved', label: 'Approved', step_order: 4, is_initial: false, is_final: true, assigned_role: null },
      ],
    },
    history: [
      { id: 1, action: 'submit', actor_id: 1, comment: 'Workflow instance started', created_at: '2026-08-01T08:00:00Z' },
    ],
    ...overrides,
  }
}

// ── Tests ──

describe('WorkflowStatus stepper', () => {
  it('marks steps before the current one as completed', () => {
    render(<WorkflowStatus instance={makeInstance()} />)

    // Steps 1–3 exist plus terminal step 4.
    expect(screen.getByText('Submitted')).toBeTruthy()
    expect(screen.getByText('HOD Approval')).toBeTruthy()
    expect(screen.getByText('HR Approval')).toBeTruthy()
    expect(screen.getByText('Approved')).toBeTruthy()

    // Current step (id 2, "HOD Approval") shows an in-progress badge.
    expect(screen.getAllByText('In progress').length).toBe(1)

    // Steps carrying an assigned role surface the responsible role.
    expect(screen.getAllByText('Responsible:').length).toBe(2) // hod + hr
    expect(screen.getAllByText('hod').length).toBeGreaterThan(0)
  })

  it('shows the pending action from role-filtered transitions', () => {
    render(
      <WorkflowStatus
        instance={makeInstance()}
        availableTransitions={[
          { label: 'Approve', to_step_id: 3, to_step_name: 'hr_approval', required_role: 'hod' },
          { label: 'Reject', to_step_id: 5, to_step_name: 'rejected', required_role: null },
        ]}
      />
    )

    // Pending action joins labels; requires the current step role.
    expect(screen.getByText(/Approve \/ Reject/)).toBeTruthy()
    expect(screen.getByText(/requires/)).toBeTruthy()
    expect(screen.getAllByText('hod').length).toBeGreaterThan(0)
  })

  it('shows a neutral awaiting state when no transitions are available', () => {
    render(<WorkflowStatus instance={makeInstance()} />)
    expect(screen.getByText('Awaiting approval')).toBeTruthy()
  })

  it('renders terminal instances with every step resolved', () => {
    const completed = makeInstance({
      status: 'completed',
      current_step_id: STEP_IDS.approved,
      history: [
        { id: 1, action: 'submit', actor_id: 1, comment: null, created_at: '2026-08-01T08:00:00Z' },
        { id: 2, action: 'approve', actor_id: 2, comment: 'OK', created_at: '2026-08-01T09:00:00Z' },
        { id: 3, action: 'approve', actor_id: 3, comment: null, created_at: '2026-08-01T10:00:00Z' },
      ],
    })
    render(<WorkflowStatus instance={completed} />)

    // Terminal → no "In progress" badge and no pending-action block.
    expect(screen.queryByText('In progress')).toBeNull()
    expect(screen.queryByText('Awaiting approval')).toBeNull()
    // "Approved" appears as the final step label AND the status badge.
    expect(screen.getAllByText('Approved').length).toBeGreaterThan(0)

    // History timeline shows the approval trail.
    expect(screen.getByText('History (3)')).toBeTruthy()
  })

  it('renders cancelled instances distinctly', () => {
    const cancelled = makeInstance({
      status: 'cancelled',
      history: [
        { id: 1, action: 'submit', actor_id: 1, comment: null, created_at: '2026-08-01T08:00:00Z' },
        { id: 2, action: 'cancel', actor_id: 1, comment: 'Withdrawn', created_at: '2026-08-01T11:00:00Z' },
      ],
    })
    render(<WorkflowStatus instance={cancelled} />)

    expect(screen.getByText('Cancelled')).toBeTruthy()
    expect(screen.getByText(/Withdrawn/)).toBeTruthy()
    expect(screen.queryByText('In progress')).toBeNull()
  })

  it('handles a workflow with no steps honestly', () => {
    const noSteps = makeInstance({
      workflow: { id: 1, name: 'Empty', code: 'EMPTY', steps: [] },
    })
    render(<WorkflowStatus instance={noSteps} />)
    expect(screen.getByText(/No steps are defined/)).toBeTruthy()
  })

  it('flags a stale current step honestly instead of silently guessing', () => {
    const stale = makeInstance({ current_step_id: 999 })
    render(<WorkflowStatus instance={stale} />)
    expect(screen.getByText(/current step no longer defined/)).toBeTruthy()
  })

  it('hides the history timeline in compact mode', () => {
    render(<WorkflowStatus instance={makeInstance()} compact />)
    expect(screen.queryByText(/History/)).toBeNull()
  })

  it('renders an empty history gracefully', () => {
    render(<WorkflowStatus instance={makeInstance({ history: [] })} />)
    expect(screen.queryByText(/History/)).toBeNull()
  })
})
