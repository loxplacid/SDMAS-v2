import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ToastProvider } from '../components/ui/toast'
import type { CommandCenterOverview } from '../api/command-center/command-center-api'

const getOverviewMock = vi.fn()
const listFindingsMock = vi.fn()
const resolveFindingMock = vi.fn()
const acknowledgeFindingMock = vi.fn()

vi.mock('../api/command-center/command-center-api', () => ({
  commandCenterApi: { getOverview: (...args: unknown[]) => getOverviewMock(...args) },
}))

vi.mock('../api/risk/risk-api', () => ({
  riskApi: {
    listFindings: (...args: unknown[]) => listFindingsMock(...args),
    resolveFinding: (...args: unknown[]) => resolveFindingMock(...args),
    acknowledgeFinding: (...args: unknown[]) => acknowledgeFindingMock(...args),
  },
}))

vi.mock('../api/auth/auth-context', () => ({
  useAuth: () => ({
    user: { id: 1, username: 'admin', display_name: 'Ada Admin', role: 'admin' },
    isLoading: false,
    isAuthenticated: true,
    error: null,
    login: vi.fn(),
    logout: vi.fn(),
    updateUser: vi.fn(),
  }),
}))

const { ActionCenterPage } = await import('../pages/action-center/action-center')

function makeOverview(overrides: Partial<CommandCenterOverview> = {}): CommandCenterOverview {
  return {
    generated_at: '2026-08-01T09:30:00Z',
    role: 'admin',
    campus_id: 1,
    academic_year: '2026-27',
    sections: { school_health: true, needs_attention: true, today: true, quick_actions: true },
    school_health: { available: true, metrics: [], trends: {} },
    needs_attention: {
      available: true,
      alerts: [
        { id: 'a1', severity: 'critical', category: 'attendance', title: '37 students below 75% attendance', message: 'Students are flagged after 5+ recorded days', count: 37, action_label: 'View students', drill_down: '/attendance-intelligence/dashboard' },
        { id: 'a2', severity: 'warning', category: 'fees', title: 'Overdue fees', message: '₹12.4L overdue across 12 students', count: 12, action_label: 'View outstanding', drill_down: '/fees/dues' },
        { id: 'a3', severity: 'info', category: 'jobs', title: 'Failed jobs', message: '3 background jobs failed', count: 3, action_label: 'View jobs', drill_down: '/operations' },
      ],
    },
    today: { available: true, events: [] },
    quick_actions: [],
    ...overrides,
  }
}

const openFinding = {
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
}

const resolvedFinding = {
  ...openFinding,
  id: 39,
  status: 'resolved',
  resolved_at: '2026-08-02T10:00:00Z',
  resolved_reason: 'Paid in cash',
  last_verified_at: '2026-08-02T10:00:00Z',
}

function renderPage(route = '/action-center') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <ToastProvider>
        <Routes>
          <Route path="/action-center" element={<ActionCenterPage />} />
          <Route path="/students/:id/360" element={<div>Student 360</div>} />
          <Route path="/fees/dues" element={<div>Fee Dues</div>} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>
  )
}

beforeEach(() => {
  vi.resetAllMocks()
  getOverviewMock.mockResolvedValue(makeOverview())
  listFindingsMock.mockResolvedValue({ items: [openFinding], total: 1, page: 1, size: 50, pages: 1 })
  resolveFindingMock.mockResolvedValue({ ...openFinding, status: 'resolved' })
  acknowledgeFindingMock.mockResolvedValue({ ...openFinding, status: 'acknowledged' })
})

describe('Action Center page', () => {
  it('shows a loading skeleton, then renders real alerts and risk findings', async () => {
    renderPage()
    expect(screen.getByLabelText('Loading action center')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('37 students below 75% attendance')).toBeInTheDocument()
      expect(screen.getByText('Overdue fees')).toBeInTheDocument()
      expect(screen.getByText('Attendance below threshold')).toBeInTheDocument()
    })
    expect(screen.queryByLabelText('Loading action center')).not.toBeInTheDocument()
  })

  it('filters actions by domain tab (Financial)', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Overdue fees')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('tab', { name: 'Financial' }))

    await waitFor(() => {
      expect(screen.getByText('Overdue fees')).toBeInTheDocument()
      expect(screen.queryByText('37 students below 75% attendance')).not.toBeInTheDocument()
      expect(screen.queryByText('Attendance below threshold')).not.toBeInTheDocument()
    })
  })

  it('filters by severity from the dropdown', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Overdue fees')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Filter by severity'), { target: { value: 'critical' } })

    await waitFor(() => {
      expect(screen.getByText('37 students below 75% attendance')).toBeInTheDocument()
      expect(screen.queryByText('Overdue fees')).not.toBeInTheDocument()
    })
  })

  it('searches actions by keyword', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Overdue fees')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Search actions'), { target: { value: 'overdue' } })

    await waitFor(() => {
      expect(screen.getByText('Overdue fees')).toBeInTheDocument()
      expect(screen.queryByText('37 students below 75% attendance')).not.toBeInTheDocument()
    })
  })

  it('navigates to a drill-down target from an action button', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Overdue fees')).toBeInTheDocument())

    fireEvent.click(screen.getByText('View outstanding'))
    expect(await screen.findByText('Fee Dues')).toBeInTheDocument()
  })

  it('resolves a risk finding with an audited reason', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Attendance below threshold')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /^Resolve$/ }))
    const dialog = screen.getByRole('dialog')
    const textarea = within(dialog).getByPlaceholderText(/Reason \(audited\)/)
    fireEvent.change(textarea, { target: { value: 'Family contacted and paid' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Resolve' }))

    await waitFor(() => {
      expect(resolveFindingMock).toHaveBeenCalledWith(41, 'Family contacted and paid')
    })
  })

  it('acknowledges a risk finding', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Attendance below threshold')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Acknowledge' }))
    await waitFor(() => {
      expect(acknowledgeFindingMock).toHaveBeenCalledWith(41)
    })
  })

  it('bulk-resolves selected risk findings', async () => {
    listFindingsMock.mockResolvedValue({
      items: [openFinding, { ...openFinding, id: 42, reason: 'Fee overdue' }],
      total: 2,
      page: 1,
      size: 50,
      pages: 1,
    })
    renderPage()
    await waitFor(() => expect(screen.getByText('Attendance below threshold')).toBeInTheDocument())

    fireEvent.click(screen.getByLabelText('Select Attendance below threshold'))
    fireEvent.click(screen.getByRole('button', { name: 'Resolve selected' }))
    const dialog = screen.getByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Resolve' }))

    await waitFor(() => {
      expect(resolveFindingMock).toHaveBeenCalledWith(41, expect.any(String))
    })
  })

  it('shows resolved findings in the Recently Resolved section', async () => {
    getOverviewMock.mockResolvedValue(makeOverview())
    listFindingsMock
      .mockResolvedValueOnce({ items: [openFinding], total: 1, page: 1, size: 50, pages: 1 })
      .mockResolvedValueOnce({ items: [resolvedFinding], total: 1, page: 1, size: 10, pages: 1 })

    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Recently Resolved')).toBeInTheDocument()
    })
    expect(screen.getByText(/Paid in cash/)).toBeInTheDocument()
  })

  it('shows the all-clear empty state when nothing needs attention', async () => {
    getOverviewMock.mockResolvedValue(makeOverview({ needs_attention: { available: true, alerts: [] } }))
    listFindingsMock.mockResolvedValue({ items: [], total: 0, page: 1, size: 50, pages: 0 })

    renderPage()
    await waitFor(() => {
      expect(screen.getByText('All clear')).toBeInTheDocument()
    })
  })

  it('shows the filtered-empty state with a clear-filters action', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Overdue fees')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Search actions'), { target: { value: 'zzz-no-match' } })

    await waitFor(() => {
      expect(screen.getByText('No actions match')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
    await waitFor(() => {
      expect(screen.getByText('Overdue fees')).toBeInTheDocument()
    })
  })

  it('shows an error state with retry when all primary sources fail', async () => {
    getOverviewMock.mockRejectedValueOnce({ detail: 'Service unavailable' })
    listFindingsMock.mockRejectedValueOnce({ detail: 'Service unavailable' })

    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Unable to load actions from the server.')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: 'Try Again' })).toBeInTheDocument()
  })

  it('supports keyboard navigation — arrows move the ring AND focus (roving tabindex)', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('37 students below 75% attendance')).toBeInTheDocument())

    const list = screen.getByRole('list', { name: 'Attention actions' })
    fireEvent.keyDown(list, { key: 'ArrowDown' })
    await waitFor(() => {
      // Roving active index moves to the second row
      expect(screen.getAllByRole('listitem')[1]).toHaveAttribute('aria-current', 'true')
      // And DOM focus follows the ring, so Enter on the focused row targets
      // the active item (true roving tabindex, not just a visual ring).
      expect(document.activeElement).toBe(screen.getAllByRole('listitem')[1])
    })
    fireEvent.keyDown(screen.getAllByRole('listitem')[1], { key: 'ArrowUp' })
    await waitFor(() => {
      expect(screen.getAllByRole('listitem')[0]).toHaveAttribute('aria-current', 'true')
      expect(document.activeElement).toBe(screen.getAllByRole('listitem')[0])
    })
  })
})
