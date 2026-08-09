import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ToastProvider } from '../components/ui/toast'

const listMock = vi.fn()
const overviewMock = vi.fn()
const assignableMock = vi.fn()
const createMock = vi.fn()
const bulkAssignMock = vi.fn()

vi.mock('../api/cases/cases-api', () => ({
  casesApi: {
    list: (...args: unknown[]) => listMock(...args),
    overview: (...args: unknown[]) => overviewMock(...args),
    assignable: (...args: unknown[]) => assignableMock(...args),
    create: (...args: unknown[]) => createMock(...args),
    bulkAssign: (...args: unknown[]) => bulkAssignMock(...args),
    bulkPriority: vi.fn(),
    bulkStatus: vi.fn(),
    bulkDueDate: vi.fn(),
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

const { WorkQueuePage } = await import('../pages/work/work-queue')

function makeCase(overrides: Record<string, unknown> = {}) {
  return {
    id: 101,
    case_number: 'DMAS-000421',
    campus_id: 1,
    title: 'Attendance anomaly — Grade 10A',
    description: 'Attendance dropped below threshold',
    case_type: 'attendance',
    priority: 'high',
    original_priority: 'high',
    status: 'in_progress',
    source_type: 'risk_finding',
    source_id: 184,
    student_id: 7,
    created_by: 1,
    assigned_to: 2,
    assigned_at: '2026-08-08T09:00:00Z',
    due_at: '2026-08-08T17:00:00Z',
    escalated_at: null,
    resolved_at: null,
    resolved_by: null,
    resolved_reason: null,
    closed_at: null,
    closed_by: null,
    version: 3,
    created_at: '2026-08-08T08:00:00Z',
    updated_at: '2026-08-08T09:30:00Z',
    sla_state: 'OVERDUE',
    assignee_name: 'Maya Attendance',
    ...overrides,
  }
}

const overview = {
  open: 42,
  critical: 3,
  overdue: 7,
  due_today: 11,
  my_open: 5,
  unassigned: 4,
  by_status: { open: 42 },
  generated_at: '2026-08-08T09:30:00Z',
}

const assignable = [
  { id: 2, name: 'Maya Attendance', role: 'staff' },
  { id: 3, name: 'Firoz Finance', role: 'accountant' },
]

function renderPage(route = '/work') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <ToastProvider>
        <Routes>
          <Route path="/work" element={<WorkQueuePage />} />
          <Route path="/cases/:id" element={<div>Case detail</div>} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>
  )
}

beforeEach(() => {
  vi.resetAllMocks()
  listMock.mockResolvedValue({ items: [makeCase()], total: 1, page: 1, size: 20, pages: 1 })
  overviewMock.mockResolvedValue(overview)
  assignableMock.mockResolvedValue(assignable)
  createMock.mockResolvedValue(makeCase({ id: 102, case_number: 'DMAS-000422', status: 'open' }))
  bulkAssignMock.mockResolvedValue({ updated: [101], skipped: 0 })
})

describe('Work Queue page', () => {
  it('shows a skeleton then renders cases with SLA state and source', async () => {
    renderPage()
    expect(screen.getByLabelText('Loading work queue')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('DMAS-000421')).toBeInTheDocument()
      expect(screen.getByText('Attendance anomaly — Grade 10A')).toBeInTheDocument()
      expect(screen.getByText('OVERDUE')).toBeInTheDocument()
      expect(screen.getByText(/From risk finding/)).toBeInTheDocument()
      // P11 — the queue exposes case age alongside priority/due/SLA/assignee.
      expect(screen.getByText(/Created .* ago/)).toBeInTheDocument()
    })
    expect(screen.queryByLabelText('Loading work queue')).not.toBeInTheDocument()
  })

  it('renders overview count cards and navigates on click', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Attendance anomaly — Grade 10A')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /Open 42/ }))
    expect(listMock).toHaveBeenCalledWith(
      expect.objectContaining({ view: 'open' })
    )
  })

  it('filters by priority from the dropdown', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Attendance anomaly — Grade 10A')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Filter by priority'), { target: { value: 'critical' } })

    await waitFor(() => {
      expect(listMock).toHaveBeenLastCalledWith(
        expect.objectContaining({ priority: 'critical' })
      )
    })
  })

  it('searches cases by keyword', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Attendance anomaly — Grade 10A')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Search cases'), { target: { value: 'Grade 10' } })

    await waitFor(() => {
      expect(listMock).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: 'Grade 10' })
      )
    })
  })

  it('navigates to the case detail when a row is clicked', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Attendance anomaly — Grade 10A')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /DMAS-000421/ }))
    expect(await screen.findByText('Case detail')).toBeInTheDocument()
  })

  it('creates a case from the New Case modal', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Attendance anomaly — Grade 10A')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /New Case/ }))
    const dialog = screen.getByRole('dialog')
    fireEvent.change(
      within(dialog).getByPlaceholderText('What needs attention?'),
      { target: { value: 'New admissions backlog' } }
    )
    fireEvent.click(within(dialog).getByRole('button', { name: 'Create case' }))

    await waitFor(() => {
      expect(createMock).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'New admissions backlog', case_type: 'administrative' })
      )
    })
    expect(await screen.findByText('Case detail')).toBeInTheDocument()
  })

  it('supports bulk selection and assignment for administrators', async () => {
    listMock.mockResolvedValue({
      items: [makeCase(), makeCase({ id: 102, case_number: 'DMAS-000422', status: 'open' })],
      total: 2,
      page: 1,
      size: 20,
      pages: 1,
    })
    renderPage()
    await waitFor(() => expect(screen.getByText('DMAS-000421')).toBeInTheDocument())

    fireEvent.click(screen.getByLabelText('Select DMAS-000421'))
    await waitFor(() => expect(screen.getByText('1 selected')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Assign' }))
    const dialog = screen.getByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText('Assign to'), { target: { value: '3' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Apply' }))

    await waitFor(() => {
      expect(bulkAssignMock).toHaveBeenCalledWith([101], 3)
    })
  })

  it('shows the empty state for a filtered search with a clear action', async () => {
    listMock.mockResolvedValue({ items: [], total: 0, page: 1, size: 20, pages: 0 })
    renderPage('/work?q=zzz')
    await waitFor(() => expect(screen.getByText('No cases match these filters')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
    await waitFor(() => {
      expect(listMock).toHaveBeenLastCalledWith(expect.objectContaining({ search: null }))
    })
  })

  it('shows an error state with retry when the primary sources fail', async () => {
    overviewMock.mockRejectedValueOnce({ detail: 'Service unavailable' })
    listMock.mockRejectedValueOnce({ detail: 'Service unavailable' })

    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Unable to load the work queue from the server.')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: 'Try Again' })).toBeInTheDocument()
  })
})
