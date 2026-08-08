import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ToastProvider } from '../components/ui/toast'

const getMock = vi.fn()
const assignableMock = vi.fn()
const assignMock = vi.fn()
const transitionMock = vi.fn()
const addCommentMock = vi.fn()
const addEvidenceMock = vi.fn()

vi.mock('../api/cases/cases-api', () => ({
  casesApi: {
    get: (...args: unknown[]) => getMock(...args),
    assignable: (...args: unknown[]) => assignableMock(...args),
    assign: (...args: unknown[]) => assignMock(...args),
    transition: (...args: unknown[]) => transitionMock(...args),
    addComment: (...args: unknown[]) => addCommentMock(...args),
    addEvidence: (...args: unknown[]) => addEvidenceMock(...args),
    changePriority: vi.fn(),
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

const { CaseDetailPage } = await import('../pages/cases/case-detail')

const caseItem = {
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
}

const detail = {
  case: caseItem,
  events: [
    { id: 1, event_seq: 1, event_type: 'CASE_CREATED', actor_id: 1, actor_name: 'Ada Admin', message: 'Case created from risk finding #184', data: null, created_at: '2026-08-08T08:00:00Z' },
    { id: 2, event_seq: 2, event_type: 'ASSIGNED', actor_id: 1, actor_name: 'Ada Admin', message: 'Assigned to Maya Attendance', data: null, created_at: '2026-08-08T09:00:00Z' },
    { id: 3, event_seq: 3, event_type: 'STATUS_CHANGED', actor_id: 2, actor_name: 'Maya Attendance', message: 'Status changed from open to in_progress', data: null, created_at: '2026-08-08T09:30:00Z' },
  ],
  comments: [
    { id: 11, author_id: 2, author_name: 'Maya Attendance', body: 'Contacted the class teacher.', created_at: '2026-08-08T09:15:00Z' },
  ],
  evidence: [
    { id: 21, kind: 'attendance_report', title: 'Attendance report Aug 1-8', summary: '10A weekly export', reference_type: null, reference_id: null, data: null, added_by: 1, created_at: '2026-08-08T09:20:00Z' },
  ],
}

const assignable = [
  { id: 2, name: 'Maya Attendance', role: 'staff' },
  { id: 3, name: 'Firoz Finance', role: 'accountant' },
]

function renderPage(route = '/cases/101') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <ToastProvider>
        <Routes>
          <Route path="/cases/:id" element={<CaseDetailPage />} />
          <Route path="/work" element={<div>Work queue</div>} />
          <Route path="/risk" element={<div>Risk center</div>} />
          <Route path="/data-quality" element={<div>Data quality</div>} />
          <Route path="/students/:id" element={<div>Student detail</div>} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>
  )
}

beforeEach(() => {
  vi.resetAllMocks()
  getMock.mockResolvedValue(detail)
  assignableMock.mockResolvedValue(assignable)
  assignMock.mockResolvedValue({ ...caseItem, assigned_to: 3, assignee_name: 'Firoz Finance', version: 4 })
  transitionMock.mockResolvedValue({ ...caseItem, status: 'resolved', resolved_at: '2026-08-08T10:00:00Z', version: 4 })
  addCommentMock.mockResolvedValue({ id: 12, author_id: 1, author_name: 'Ada Admin', body: 'Done', created_at: '2026-08-08T10:05:00Z' })
  addEvidenceMock.mockResolvedValue({ id: 22, kind: 'administrative_note', title: 'Note', summary: null, reference_type: null, reference_id: null, data: null, added_by: 1, created_at: '2026-08-08T10:10:00Z' })
})

describe('Case Detail page', () => {
  it('shows a skeleton then renders the case with its audit timeline', async () => {
    renderPage()
    expect(screen.getByLabelText('Loading case')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('DMAS-000421')).toBeInTheDocument()
      expect(screen.getByText('Attendance anomaly — Grade 10A')).toBeInTheDocument()
      expect(screen.getAllByText(/Assigned to Maya Attendance/).length).toBeGreaterThan(0)
      expect(screen.getByText('Overdue')).toBeInTheDocument()
    })
    // Immutable events appear newest-first
    expect(screen.getByText('Status changed')).toBeInTheDocument()
    expect(screen.getByText('Assigned')).toBeInTheDocument()
    expect(screen.getAllByText('Created').length).toBeGreaterThan(0)
    expect(screen.queryByLabelText('Loading case')).not.toBeInTheDocument()
  })

  it('links back to the originating P7 finding', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('DMAS-000421')).toBeInTheDocument())

    expect(screen.getByText(/Risk finding/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'View underlying records' }))
    expect(await screen.findByText('Risk center')).toBeInTheDocument()
  })

  it('shows evidence and comments', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('DMAS-000421')).toBeInTheDocument())

    expect(screen.getByText('Attendance report Aug 1-8')).toBeInTheDocument()
    expect(screen.getByText('Contacted the class teacher.')).toBeInTheDocument()
  })

  it('assigns the case to another user with an audited reason', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('DMAS-000421')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Assign' }))
    const dialog = screen.getByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText('Assign to'), { target: { value: '3' } })
    fireEvent.change(within(dialog).getByPlaceholderText(/Reason \(audited\)/), { target: { value: 'Finance escalation' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Apply' }))

    await waitFor(() => {
      expect(assignMock).toHaveBeenCalledWith(101, 3, 'Finance escalation', 3)
    })
  })

  it('resolves the case with a required audited reason', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('DMAS-000421')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Resolve' }))
    const dialog = screen.getByRole('dialog')
    fireEvent.change(within(dialog).getByPlaceholderText(/Reason \(audited\)/), { target: { value: 'Teacher confirmed resolved' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Apply' }))

    await waitFor(() => {
      expect(transitionMock).toHaveBeenCalledWith(101, 'resolved', 'Teacher confirmed resolved', 3)
    })
  })

  it('posts a comment that is recorded immutably', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('DMAS-000421')).toBeInTheDocument())

    fireEvent.change(screen.getByPlaceholderText(/Add a comment/), { target: { value: 'Escalate to principal' } })
    fireEvent.click(screen.getByRole('button', { name: 'Post' }))

    await waitFor(() => {
      expect(addCommentMock).toHaveBeenCalledWith(101, 'Escalate to principal')
    })
  })

  it('shows an error state when the case cannot be loaded', async () => {
    getMock.mockRejectedValueOnce({ detail: 'Not found' })
    renderPage('/cases/999')

    await waitFor(() => {
      expect(screen.getByText('Not found')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /Back to work queue/ })).toBeInTheDocument()
  })
})
