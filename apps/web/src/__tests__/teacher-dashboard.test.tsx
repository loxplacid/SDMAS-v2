import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import type { TeacherRiskSummary } from '../api/risk/risk-api'

// Mock the API clients before importing the page
const teacherListMock = vi.fn()
const assignmentListMock = vi.fn()
const getTeacherFindingsMock = vi.fn()

vi.mock('../api/academic/teacher-api', () => ({
  teacherApi: { list: (...args: unknown[]) => teacherListMock(...args) },
}))

vi.mock('../api/academic/teacher-assignment-api', () => ({
  teacherAssignmentApi: { list: (...args: unknown[]) => assignmentListMock(...args) },
}))

vi.mock('../api/risk/risk-api', () => ({
  riskApi: { getTeacherFindings: (...args: unknown[]) => getTeacherFindingsMock(...args) },
}))

// Stable user identity — the dashboard's useEffect depends on [user], so the
// object reference must stay the same across renders or the effect re-runs
// on every state update (re-fetching the teacher and consuming once-mocks).
const { mockUser } = vi.hoisted(() => ({
  mockUser: { id: 1, username: 'ravi', display_name: 'Ravi Kumar', email: 'ravi@test.local', role: 'teacher' },
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

// Import after mocking
const { TeacherDashboardPage } = await import('../pages/teacher/teacher-dashboard')

function makeSummary(overrides: Partial<TeacherRiskSummary> = {}): TeacherRiskSummary {
  return {
    total: 2,
    by_severity: { critical: 1, high: 1, medium: 0, low: 0 },
    findings: [
      {
        id: 1,
        student_id: 101,
        student_name: 'Rahul Sharma',
        student_number: 'A001',
        class_id: 5,
        class_name: 'Grade 10',
        rule_code: 'attendance_below_threshold',
        category: 'attendance',
        severity: 'high',
        score: 74,
        reason: 'Attendance 68% over the last 30 days (below 75%).',
        recommended_action: 'Review attendance; contact parent',
        detected_at: '2026-08-01T09:00:00Z',
        evidence: null,
      },
      {
        id: 2,
        student_id: 102,
        student_name: 'Meera Nair',
        student_number: 'A002',
        class_id: 5,
        class_name: 'Grade 10',
        rule_code: 'attendance_consecutive_absences',
        category: 'attendance',
        severity: 'critical',
        score: 88,
        reason: '6 consecutive absent days recorded (threshold 5).',
        recommended_action: 'Contact parent immediately',
        detected_at: '2026-08-01T08:00:00Z',
        evidence: null,
      },
    ],
    ...overrides,
  }
}

function renderPage(route = '/teacher') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/teacher" element={<TeacherDashboardPage />} />
        <Route path="/students/:id/360" element={<div>Student 360 Page</div>} />
        <Route path="/attendance/daily" element={<div>Daily Attendance Page</div>} />
      </Routes>
    </MemoryRouter>
  )
}

beforeEach(() => {
  vi.resetAllMocks()
  teacherListMock.mockResolvedValue({
    items: [
      { id: 7, first_name: 'Ravi', last_name: 'Kumar', email: 'ravi@test.local', status: 'active' },
    ],
    total: 1,
  })
  assignmentListMock.mockResolvedValue({
    items: [{ id: 1, teacher_id: 7, class_id: 5, subject_id: 2, status: 'active' }],
    total: 1,
  })
})

describe('Teacher dashboard — Student Risk section', () => {
  it('loads risk findings for the matched teacher and renders severity chips + findings', async () => {
    getTeacherFindingsMock.mockResolvedValueOnce(makeSummary())

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Student Risk')).toBeInTheDocument()
      expect(screen.getByText('Rahul Sharma')).toBeInTheDocument()
      expect(screen.getByText('Meera Nair')).toBeInTheDocument()
    })

    // Severity chips render (labels unique; counts collide with hero stats)
    expect(screen.getByText('critical')).toBeInTheDocument()
    expect(screen.getByText('high')).toBeInTheDocument()
    expect(screen.getByText('2 open')).toBeInTheDocument()
    // Findings show reasons + recommendations
    expect(screen.getByText(/Attendance 68%/)).toBeInTheDocument()
    expect(screen.getByText(/Contact parent immediately/)).toBeInTheDocument()
  })

  it('shows a loading skeleton while the risk fetch is in flight', async () => {
    let resolveFn!: (v: TeacherRiskSummary) => void
    getTeacherFindingsMock.mockReturnValue(new Promise((res) => { resolveFn = res }))

    renderPage()

    await waitFor(() => {
      expect(screen.getByLabelText('Loading student risk')).toBeInTheDocument()
    })

    resolveFn(makeSummary())
    await waitFor(() => {
      expect(screen.getByText('Rahul Sharma')).toBeInTheDocument()
    })
    expect(screen.queryByLabelText('Loading student risk')).not.toBeInTheDocument()
  })

  it('gracefully degrades when the risk fetch fails — dashboard still renders', async () => {
    getTeacherFindingsMock.mockRejectedValueOnce({ detail: 'Risk service down' })

    renderPage()

    await waitFor(() => {
      // The rest of the dashboard renders (assignments), and a non-blocking note appears
      expect(screen.getByText('Student Risk')).toBeInTheDocument()
      expect(screen.getByText(/Risk data is temporarily unavailable/)).toBeInTheDocument()
    })
    // Other sections still present
    expect(screen.getByText('My Assigned Classes')).toBeInTheDocument()
  })

  it('renders an empty state when the teacher has no open findings', async () => {
    getTeacherFindingsMock.mockResolvedValueOnce(
      makeSummary({ total: 0, by_severity: { critical: 0, high: 0, medium: 0, low: 0 }, findings: [] })
    )

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('No open risk findings')).toBeInTheDocument()
    })
  })

  it('drills down from a finding to the Student 360 page', async () => {
    getTeacherFindingsMock.mockResolvedValueOnce(makeSummary())

    renderPage()

    await waitFor(() => expect(screen.getByText('Rahul Sharma')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: /Open Student 360 for Rahul Sharma/i }))
    expect(await screen.findByText('Student 360 Page')).toBeInTheDocument()
  })

  it('does not render the risk section when no teacher match is found', async () => {
    teacherListMock.mockResolvedValueOnce({ items: [], total: 0 })
    getTeacherFindingsMock.mockResolvedValueOnce(makeSummary())

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Your teaching workspace')).toBeInTheDocument()
    })
    expect(screen.queryByText('Student Risk')).not.toBeInTheDocument()
    expect(getTeacherFindingsMock).not.toHaveBeenCalled()
  })
})
