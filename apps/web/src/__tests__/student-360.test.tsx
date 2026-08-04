import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import type { Student360Response } from '../api/student-360/student-360-api'

// Mock the API client before importing the page
const getMock = vi.fn()
const transitionMock = vi.fn()

vi.mock('../api/student-360/student-360-api', () => ({
  student360Api: {
    get: (...args: unknown[]) => getMock(...args),
    getLifecycle: vi.fn(),
    transition: (...args: unknown[]) => transitionMock(...args),
  },
}))

const { mockUser } = vi.hoisted(() => ({
  mockUser: { id: 1, username: 'admin', display_name: 'Test Admin', email: 'admin@test.local', role: 'admin' },
}))

vi.mock('../api/auth/auth-context', () => ({
  useAuth: () => ({
    user: mockUser,
    isLoading: false,
    isAuthenticated: true,
    error: null,
    login: vi.fn(),
    logout: vi.fn(),
    updateUser: vi.fn(),
  }),
}))

// Permission hook — admin has all permissions
vi.mock('../hooks/use-permission', () => ({
  usePermission: () => ({
    can: () => true,
  }),
}))

// Import after mocking
const { Student360Page } = await import('../pages/students/student-360')

function make360(overrides: Partial<Student360Response> = {}): Student360Response {
  return {
    identity: {
      id: 101,
      first_name: 'Rahul',
      last_name: 'Sharma',
      student_number: 'A001',
      email: 'rahul@test.local',
      date_of_birth: '2010-01-01',
      status: 'active',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
    guardians: [],
    contacts: [],
    enrollments: [],
    current_enrollment: null,
    attendance: { total: 0, present: 0, absent: 0, late: 0, excused: 0, percentage: 0 },
    attendance_records: [],
    financial: { total_fees_assigned: 0, total_paid: 0, total_outstanding: 0, unpaid_count: 0, partially_paid_count: 0, paid_count: 0 },
    fee_dues: [],
    payments: [],
    academic_history: [],
    health: { blood_group: null, allergies: null, medical_conditions: null, emergency_contact: null },
    transport: null,
    hostel: null,
    achievements: [],
    behavior: [],
    communications: [],
    risk_findings: [],
    lifecycle: {
      current_status: 'active',
      allowed_transitions: ['enrolled', 'graduated', 'transferred', 'withdrawn'],
      lifecycle_order: ['prospective', 'admitted', 'enrolled', 'active', 'transferred', 'withdrawn', 'graduated', 'alumni'],
      recent_events: [
        { id: 1, from_status: 'enrolled', to_status: 'active', reason: 'Term started', created_at: '2026-07-01T00:00:00Z' },
      ],
    },
    documents: [
      { id: 11, title: 'Birth Certificate.pdf', category: 'Identity', mime_type: 'application/pdf', file_size: 204800, uploaded_at: '2026-06-01T00:00:00Z', lifecycle_state: 'active' },
    ],
    ...overrides,
  }
}

function renderPage(route = '/students/101/360') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/students/:id/360" element={<Student360Page />} />
        <Route path="/students" element={<div>Students List</div>} />
        <Route path="/students/:id" element={<div>Standard View</div>} />
      </Routes>
    </MemoryRouter>
  )
}

beforeEach(() => {
  vi.resetAllMocks()
})

describe('Student 360 page — lifecycle & documents', () => {
  it('renders the lifecycle card with current status, transitions and history', async () => {
    getMock.mockResolvedValueOnce(make360())

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Lifecycle')).toBeInTheDocument()
      expect(screen.getByText('Active')).toBeInTheDocument()
      expect(screen.getByText('Enrolled')).toBeInTheDocument() // allowed transition chip
      expect(screen.getByText(/Term started/)).toBeInTheDocument()
    })
  })

  it('performs a lifecycle transition and refetches the 360', async () => {
    // First fetch loads the page; the post-transition refetch returns the
    // updated 360 (status graduated + new event).
    getMock
      .mockResolvedValueOnce(make360())
      .mockResolvedValueOnce(make360({
        identity: { ...make360().identity, status: 'graduated' },
        lifecycle: {
          current_status: 'graduated',
          allowed_transitions: ['alumni'],
          lifecycle_order: ['prospective', 'admitted', 'enrolled', 'active', 'transferred', 'withdrawn', 'graduated', 'alumni'],
          recent_events: [
            { id: 2, from_status: 'active', to_status: 'graduated', reason: 'Completed', created_at: '2026-08-01T00:00:00Z' },
          ],
        },
      }))
    transitionMock.mockResolvedValueOnce({
      student_id: 101,
      current_status: 'graduated',
      allowed_transitions: ['alumni'],
      lifecycle_order: ['prospective', 'admitted', 'enrolled', 'active', 'transferred', 'withdrawn', 'graduated', 'alumni'],
      recent_events: [
        { id: 2, from_status: 'active', to_status: 'graduated', reason: 'Completed', created_at: '2026-08-01T00:00:00Z' },
      ],
    })

    renderPage()

    await waitFor(() => expect(screen.getByText('Lifecycle')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: /Graduated/ }))

    await waitFor(() => {
      expect(transitionMock).toHaveBeenCalledWith(101, { to_status: 'graduated', reason: null })
      // Refetch happened after the transition.
      expect(getMock).toHaveBeenCalledTimes(2)
      // The refetched 360 now shows the new lifecycle event.
      expect(screen.getByText(/Completed/)).toBeInTheDocument()
    })
  })

  it('shows an error message when a transition fails and does not refetch', async () => {
    getMock.mockResolvedValueOnce(make360())
    transitionMock.mockRejectedValueOnce({ detail: 'Invalid transition' })

    renderPage()

    await waitFor(() => expect(screen.getByText('Lifecycle')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: /Enrolled/ }))

    await waitFor(() => {
      expect(screen.getByText('Invalid transition')).toBeInTheDocument()
      expect(getMock).toHaveBeenCalledTimes(1)
    })
  })

  it('renders real documents in the Documents tab', async () => {
    getMock.mockResolvedValueOnce(make360())

    renderPage()

    await waitFor(() => expect(screen.getByText('Lifecycle')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('tab', { name: /Documents/i }))

    await waitFor(() => {
      expect(screen.getByText('Birth Certificate.pdf')).toBeInTheDocument()
      expect(screen.getByText(/Identity/)).toBeInTheDocument()
    })
  })

  it('renders an empty state when no documents exist', async () => {
    getMock.mockResolvedValueOnce(make360({ documents: [] }))

    renderPage()

    await waitFor(() => expect(screen.getByText('Lifecycle')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('tab', { name: /Documents/i }))

    await waitFor(() => {
      expect(screen.getByText('No documents uploaded for this student')).toBeInTheDocument()
    })
  })

  it('hides transition controls for a terminal status (no allowed transitions)', async () => {
    getMock.mockResolvedValueOnce(make360({
      lifecycle: {
        current_status: 'alumni',
        allowed_transitions: [],
        lifecycle_order: ['prospective', 'admitted', 'enrolled', 'active', 'transferred', 'withdrawn', 'graduated', 'alumni'],
        recent_events: [],
      },
    }))

    renderPage()

    await waitFor(() => expect(screen.getByText('Lifecycle')).toBeInTheDocument())
    // Terminal status: no transition buttons rendered.
    expect(screen.queryByRole('button', { name: /Graduated/ })).not.toBeInTheDocument()
  })

  it('shows a loading skeleton while fetching, then the page', async () => {
    let resolveFn!: (v: Student360Response) => void
    getMock.mockReturnValue(new Promise((res) => { resolveFn = res }))

    renderPage()

    // While pending, the page renders the skeleton (no lifecycle card yet).
    await waitFor(() => {
      expect(screen.queryByText('Lifecycle')).not.toBeInTheDocument()
    })
    resolveFn(make360())
    await waitFor(() => {
      expect(screen.getByText('Lifecycle')).toBeInTheDocument()
    })
  })

  it('shows an error state when the 360 fetch fails', async () => {
    getMock.mockRejectedValueOnce({ detail: 'Student 360 unavailable' })

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Student 360 unavailable')).toBeInTheDocument()
    })
  })
})
