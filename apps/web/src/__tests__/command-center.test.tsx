import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import type { CommandCenterOverview } from '../api/command-center/command-center-api'

// Mock the API clients before importing the page
const getOverviewMock = vi.fn()
vi.mock('../api/command-center/command-center-api', () => ({
  commandCenterApi: { getOverview: (...args: unknown[]) => getOverviewMock(...args) },
}))

// The Recent Activity section embeds the unified Timeline component
const getTimelineMock = vi.fn()
vi.mock('../api/timeline/timeline-api', () => ({
  timelineApi: { get: (...args: unknown[]) => getTimelineMock(...args) },
}))

// Mock auth context
vi.mock('../api/auth/auth-context', () => ({
  useAuth: () => ({
    user: { id: 1, username: 'principal', display_name: 'Priya Sharma', role: 'principal' },
    isLoading: false,
    isAuthenticated: true,
    error: null,
    login: vi.fn(),
    logout: vi.fn(),
    updateUser: vi.fn(),
  }),
}))

// Import after mocking
const { CommandCenterPage } = await import('../pages/command-center/command-center')

function makeOverview(overrides: Partial<CommandCenterOverview> = {}): CommandCenterOverview {
  return {
    generated_at: '2026-08-01T09:30:00Z',
    role: 'principal',
    campus_id: 1,
    academic_year: '2026-27',
    sections: {
      school_health: true,
      needs_attention: true,
      today: true,
      quick_actions: true,
    },
    school_health: {
      available: true,
      metrics: [
        { key: 'students', label: 'Total Students', value: 640, display: '640', status: 'good', drill_down: '/students' },
        { key: 'attendance', label: 'Attendance Rate', value: 92, display: '92%', status: 'good', drill_down: '/attendance' },
        { key: 'fee_collection', label: 'Fee Collection', value: 78, display: '78%', status: 'info', drill_down: '/fees/summary' },
        { key: 'outstanding', label: 'Outstanding', value: 1240000, display: '₹12.4L', status: 'warn', drill_down: '/fees/dues' },
        { key: 'admissions', label: 'Active Admissions', value: 18, display: '18', status: 'info', drill_down: '/admissions' },
        { key: 'approvals', label: 'Pending Approvals', value: 5, display: '5', status: 'warn', drill_down: '/admin/approvals' },
      ],
      trends: { attendance: [{ label: 'D1', value: 90 }, { label: 'D2', value: 92 }] },
    },
    needs_attention: {
      available: true,
      alerts: [
        { id: 'a1', severity: 'critical', category: 'attendance', title: 'Low attendance', message: '37 students below 75% attendance', count: 37, action_label: 'View students', drill_down: '/attendance-intelligence/dashboard' },
        { id: 'a2', severity: 'warning', category: 'fees', title: 'Overdue fees', message: '₹12.4L overdue', count: 12, action_label: 'View outstanding', drill_down: '/fees/dues' },
        { id: 'a3', severity: 'info', category: 'admissions', title: 'Awaiting review', message: '18 applications awaiting review', count: 18, action_label: 'Open admissions', drill_down: '/admissions/applications' },
      ],
    },
    today: {
      available: true,
      events: [
        { id: 't1', type: 'attendance', title: 'Attendance recorded', description: '540 of 640 students present', drill_down: '/attendance/daily' },
        { id: 't2', type: 'payment', title: '6 payments collected', description: '₹84,500 collected today', drill_down: '/fees/payments' },
        { id: 't3', type: 'admission', title: '3 new applications', description: '2 pending review', drill_down: '/admissions' },
      ],
    },
    quick_actions: [
      { id: 'q1', label: 'Add Student', description: 'Register a new student', route: '/students', icon: 'user-plus' },
      { id: 'q2', label: 'Record Attendance', description: 'Mark daily attendance', route: '/attendance/daily', icon: 'check-square' },
    ],
    ...overrides,
  }
}

function renderPage(route = '/command-center') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/command-center" element={<CommandCenterPage />} />
        <Route path="/students" element={<div>Students Page</div>} />
        <Route path="/fees/dues" element={<div>Fee Dues Page</div>} />
        <Route path="/attendance/daily" element={<div>Daily Attendance Page</div>} />
      </Routes>
    </MemoryRouter>
  )
}

beforeEach(() => {
  vi.resetAllMocks()
  getTimelineMock.mockResolvedValue({
    items: [
      { id: 'fees:1', event_type: 'fees.payment', timestamp: '2026-08-01T09:00:00Z', actor: 'Ravi Kumar', entity: 'Rahul Sharma', description: 'Payment of ₹50,000 recorded', severity: 'success', source: 'fees', metadata: {}, deep_link: '/students/101/360' },
    ],
    total: 1,
    page: 1,
    page_size: 10,
    sources: [{ key: 'fees', label: 'Payments', count: 1, available: true }],
    degraded: false,
  })
})

describe('Command Center page', () => {
  it('shows loading skeleton while fetching, then renders dashboard', async () => {
    let resolveFn!: (v: CommandCenterOverview) => void
    getOverviewMock.mockReturnValue(new Promise((res) => { resolveFn = res }))

    renderPage()

    // Skeleton with aria-busy is shown initially
    expect(screen.getByLabelText('Loading command center')).toBeInTheDocument()

    resolveFn(makeOverview())
    await waitFor(() => {
      expect(screen.getByText('School Command Center')).toBeInTheDocument()
      expect(screen.getByText('Total Students')).toBeInTheDocument()
      expect(screen.getByText('School Health')).toBeInTheDocument()
      expect(screen.getByText('Needs Attention')).toBeInTheDocument()
    })
    expect(screen.queryByLabelText('Loading command center')).not.toBeInTheDocument()
  })

  it('renders error state with retry when the API fails completely', async () => {
    getOverviewMock.mockRejectedValueOnce({ detail: 'Service unavailable' })

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Service unavailable')).toBeInTheDocument()
    })
    expect(screen.getByText('Try Again')).toBeInTheDocument()
  })

  it('gracefully renders partial failure — one unavailable section shows fallback while others render', async () => {
    getOverviewMock.mockResolvedValueOnce(
      makeOverview({
        sections: { ...makeOverview().sections, school_health: false, today: false },
        school_health: { available: false, metrics: [], trends: {} },
        today: { available: false, events: [] },
      })
    )

    renderPage()

    await waitFor(() => {
      // Healthy sections still render
      expect(screen.getByText('Needs Attention')).toBeInTheDocument()
      expect(screen.getByText('Quick Actions')).toBeInTheDocument()
      expect(screen.getByText('Recent Activity')).toBeInTheDocument()
      // Unavailable sections show the fallback message
      expect(screen.getByText('School health unavailable')).toBeInTheDocument()
      expect(screen.getByText("Today's activity unavailable")).toBeInTheDocument()
    })
  })

  it('drills down from a health metric to its target route', async () => {
    getOverviewMock.mockResolvedValueOnce(makeOverview())

    renderPage()

    await waitFor(() => expect(screen.getByText('Total Students')).toBeInTheDocument())

    await userEvent.click(screen.getByText('Total Students'))
    expect(await screen.findByText('Students Page')).toBeInTheDocument()
  })

  it('drills down from an alert action button to its target route', async () => {
    getOverviewMock.mockResolvedValueOnce(makeOverview())

    renderPage()

    await waitFor(() => expect(screen.getByText('Overdue fees')).toBeInTheDocument())

    await userEvent.click(screen.getByText('View outstanding'))
    expect(await screen.findByText('Fee Dues Page')).toBeInTheDocument()
  })

  it('drills down from a Today event row to its target route', async () => {
    getOverviewMock.mockResolvedValueOnce(makeOverview())

    renderPage()

    await waitFor(() => expect(screen.getByText('Attendance recorded')).toBeInTheDocument())

    await userEvent.click(screen.getByText('Attendance recorded'))
    expect(await screen.findByText('Daily Attendance Page')).toBeInTheDocument()
  })

  it('renders the deterministic composite School Health Score with explainable dimensions', async () => {
    getOverviewMock.mockResolvedValueOnce(
      makeOverview({
        school_health: {
          available: true,
          metrics: [],
          trends: {},
          score: {
            available: true,
            overall: 87.2,
            weights: { attendance: 0.3, fees: 0.25, academic: 0.2, retention: 0.15, data_quality: 0.1 },
            dimensions: [
              { key: 'attendance', label: 'Attendance', score: 91, weight: 0.3, status: 'good', available: true, metrics: [], drill_down: '/attendance' },
              { key: 'fees', label: 'Fees', score: 82, weight: 0.25, status: 'warn', available: true, metrics: [], drill_down: '/fees' },
              { key: 'academic', label: 'Academics', score: 89, weight: 0.2, status: 'good', available: true, metrics: [], drill_down: '/academic' },
              { key: 'retention', label: 'Retention', score: 94, weight: 0.15, status: 'good', available: true, metrics: [], drill_down: '/students' },
              { key: 'data_quality', label: 'Data Quality', score: 88, weight: 0.1, status: 'good', available: true, metrics: [], drill_down: '/data-quality' },
            ],
          },
        },
      })
    )

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('School Health Score')).toBeInTheDocument()
      // Composite rounds to 87
      expect(screen.getByText('87')).toBeInTheDocument()
    })
    // Every dimension is visible with its explainable score
    expect(screen.getByText('Attendance 91')).toBeInTheDocument()
    expect(screen.getByText('Fees 82')).toBeInTheDocument()
    expect(screen.getByText('Academics 89')).toBeInTheDocument()
    expect(screen.getByText('Retention 94')).toBeInTheDocument()
    expect(screen.getByText('Data Quality 88')).toBeInTheDocument()
  })

  it('hides the composite score when it is unavailable (graceful degradation)', async () => {
    getOverviewMock.mockResolvedValueOnce(
      makeOverview({
        school_health: { available: true, metrics: [], trends: {}, score: null },
      })
    )

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('School Health')).toBeInTheDocument()
    })
    expect(screen.queryByText('School Health Score')).not.toBeInTheDocument()
  })

  it('renders role-specific quick actions without financial data leakage for staff', async () => {
    getOverviewMock.mockResolvedValueOnce(
      makeOverview({
        role: 'staff',
        school_health: {
          available: true,
          metrics: [
            { key: 'students', label: 'Total Students', value: 640, display: '640', status: 'good', drill_down: '/students' },
            { key: 'attendance', label: 'Attendance Rate', value: 92, display: '92%', status: 'good', drill_down: '/attendance' },
          ],
          trends: {},
        },
        quick_actions: [
          { id: 'q1', label: 'Record Attendance', description: 'Mark daily attendance', route: '/attendance/daily', icon: 'check-square' },
        ],
      })
    )

    renderPage()

    await waitFor(() => {
      // Staff sees attendance-focused metrics
      expect(screen.getByText('Attendance Rate')).toBeInTheDocument()
      // Staff quick actions are role-appropriate
      expect(screen.getByText('Record Attendance')).toBeInTheDocument()
    })

    // Financial data must NOT be shown to staff
    expect(screen.queryByText('Outstanding')).not.toBeInTheDocument()
    expect(screen.queryByText('Fee Collection')).not.toBeInTheDocument()
  })
})
