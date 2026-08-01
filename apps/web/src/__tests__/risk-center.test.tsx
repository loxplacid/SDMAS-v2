import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ToastProvider } from '../components/ui/toast'
import type { RiskFinding, RiskOverview, RiskFindingPage, RuleConfig } from '../api/risk/risk-api'

// Mock the API client before importing the page
const getOverviewMock = vi.fn()
const listFindingsMock = vi.fn()
const getConfigMock = vi.fn()
const recomputeMock = vi.fn()
const resolveFindingMock = vi.fn()
const acknowledgeFindingMock = vi.fn()
const updateConfigMock = vi.fn()

vi.mock('../api/risk/risk-api', () => ({
  riskApi: {
    getOverview: (...args: unknown[]) => getOverviewMock(...args),
    listFindings: (...args: unknown[]) => listFindingsMock(...args),
    getConfig: (...args: unknown[]) => getConfigMock(...args),
    recompute: (...args: unknown[]) => recomputeMock(...args),
    resolveFinding: (...args: unknown[]) => resolveFindingMock(...args),
    acknowledgeFinding: (...args: unknown[]) => acknowledgeFindingMock(...args),
    updateConfig: (...args: unknown[]) => updateConfigMock(...args),
  },
}))

// Mock auth context (role drives which actions render)
let mockRole = 'principal'
vi.mock('../api/auth/auth-context', () => ({
  useAuth: () => ({
    user: { id: 1, username: 'principal', display_name: 'Priya Sharma', role: mockRole },
    isLoading: false,
    isAuthenticated: true,
    error: null,
    login: vi.fn(),
    logout: vi.fn(),
    updateUser: vi.fn(),
  }),
}))

// Import after mocking
const { RiskCenterPage } = await import('../pages/risk/risk-center')

function makeFinding(overrides: Partial<RiskFinding> = {}): RiskFinding {
  return {
    id: 1,
    campus_id: 1,
    entity_type: 'student',
    entity_id: 101,
    student_id: 101,
    rule_code: 'attendance_below_threshold',
    category: 'attendance',
    severity: 'high',
    score: 74,
    reason: 'Attendance 68% over the last 30 days (below 75%).',
    recommended_action: 'Review attendance; contact parent',
    evidence: { student: 'Rahul Sharma', percentage: 68 },
    status: 'open',
    detected_at: '2026-08-01T09:00:00Z',
    last_verified_at: '2026-08-01T09:00:00Z',
    resolved_at: null,
    resolved_by: null,
    resolved_reason: null,
    ...overrides,
  }
}

function makeOverview(overrides: Partial<RiskOverview> = {}): RiskOverview {
  return {
    critical: 1,
    high: 2,
    medium: 1,
    low: 0,
    total: 4,
    by_category: { attendance: 2, finance: 1, academic: 1 },
    ...overrides,
  }
}

function makePage(items: RiskFinding[] = [makeFinding()], overrides: Partial<RiskFindingPage> = {}): RiskFindingPage {
  return {
    items,
    total: items.length,
    page: 1,
    size: 20,
    pages: 1,
    ...overrides,
  }
}

function makeConfig(overrides: Partial<RuleConfig> = {}): RuleConfig {
  return {
    rule_code: 'attendance_below_threshold',
    category: 'attendance',
    name: 'Low Attendance',
    description: 'Flags students below a percentage over the window',
    entity_type: 'student',
    enabled: true,
    thresholds: { min_percentage: 75, window_days: 30 },
    severity_overrides: null,
    defaults: { min_percentage: 75, window_days: 30 },
    recommended_action: 'Review attendance',
    ...overrides,
  }
}

function renderPage(route = '/risk') {
  return render(
    <ToastProvider>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/risk" element={<RiskCenterPage />} />
          <Route path="/students/:id/360" element={<div>Student 360 Page</div>} />
          <Route path="/admissions/:id" element={<div>Admission Detail Page</div>} />
        </Routes>
      </MemoryRouter>
    </ToastProvider>
  )
}

beforeEach(() => {
  vi.resetAllMocks()
  mockRole = 'principal'
})

describe('Risk Center page', () => {
  it('shows loading skeleton while fetching, then renders overview + findings', async () => {
    let resolveOverview!: (v: RiskOverview) => void
    let resolveFindings!: (v: RiskFindingPage) => void
    getOverviewMock.mockReturnValue(new Promise((res) => { resolveOverview = res }))
    listFindingsMock.mockReturnValue(new Promise((res) => { resolveFindings = res }))
    getConfigMock.mockResolvedValue([makeConfig()])

    renderPage()

    // Skeleton with aria-busy is shown initially
    expect(screen.getByLabelText('Loading risk center')).toBeInTheDocument()

    resolveOverview(makeOverview())
    resolveFindings(makePage())
    await waitFor(() => {
      expect(screen.getByText('Risk & Attention Engine')).toBeInTheDocument()
      expect(screen.getByText('Findings')).toBeInTheDocument()
      expect(screen.getByText(/Rahul Sharma/)).toBeInTheDocument()
    })
    expect(screen.queryByLabelText('Loading risk center')).not.toBeInTheDocument()
  })

  it('renders error state with retry when the API fails completely', async () => {
    getOverviewMock.mockRejectedValueOnce({ detail: 'Service unavailable' })
    listFindingsMock.mockRejectedValueOnce({ detail: 'Service unavailable' })
    getConfigMock.mockRejectedValueOnce({ detail: 'Service unavailable' })

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Failed to load the Risk Center')).toBeInTheDocument()
    })
    expect(screen.getByText('Try Again')).toBeInTheDocument()
  })

  it('gracefully renders partial failure — config failing does not block findings', async () => {
    getOverviewMock.mockResolvedValueOnce(makeOverview())
    listFindingsMock.mockResolvedValueOnce(makePage())
    getConfigMock.mockRejectedValueOnce({ detail: 'Config unavailable' })

    renderPage()

    await waitFor(() => {
      expect(screen.getByText(/Rahul Sharma/)).toBeInTheDocument()
      expect(screen.getByText('Findings')).toBeInTheDocument()
    })
    expect(screen.queryByText('Failed to load the Risk Center')).not.toBeInTheDocument()
  })

  it('drills down from a student finding to the Student 360 page', async () => {
    getOverviewMock.mockResolvedValueOnce(makeOverview())
    listFindingsMock.mockResolvedValueOnce(makePage())
    getConfigMock.mockResolvedValueOnce([makeConfig()])

    renderPage()

    await waitFor(() => expect(screen.getByText(/Rahul Sharma/)).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: /open \/students\/101\/360/i }))
    expect(await screen.findByText('Student 360 Page')).toBeInTheDocument()
  })

  it('filters findings by category, severity and status', async () => {
    getOverviewMock.mockResolvedValueOnce(makeOverview())
    listFindingsMock.mockResolvedValueOnce(makePage())
    getConfigMock.mockResolvedValueOnce([makeConfig()])

    renderPage()

    await waitFor(() => expect(screen.getByText('Findings')).toBeInTheDocument())

    await userEvent.selectOptions(screen.getByLabelText('Filter by category'), 'finance')
    await userEvent.selectOptions(screen.getByLabelText('Filter by severity'), 'critical')
    await userEvent.selectOptions(screen.getByLabelText('Filter by status'), 'resolved')

    await waitFor(() => {
      const lastCall = listFindingsMock.mock.calls[listFindingsMock.mock.calls.length - 1][0]
      expect(lastCall).toMatchObject({ category: 'finance', severity: 'critical', status: 'resolved' })
    })
  })

  it('hides resolve/recompute/config actions for staff but keeps acknowledge + read-only view', async () => {
    mockRole = 'staff'
    getOverviewMock.mockResolvedValueOnce(makeOverview())
    listFindingsMock.mockResolvedValueOnce(makePage())
    getConfigMock.mockResolvedValueOnce([makeConfig()])

    renderPage()

    await waitFor(() => expect(screen.getByText(/Rahul Sharma/)).toBeInTheDocument())

    // Staff cannot run rules, resolve findings, or edit config
    expect(screen.queryByText('Run Rules')).not.toBeInTheDocument()
    expect(screen.queryByText('Resolve')).not.toBeInTheDocument()
    // Staff CAN acknowledge (role policy)
    expect(screen.getByText('Acknowledge')).toBeInTheDocument()
  })

  it('resolves a finding through the audited dialog', async () => {
    getOverviewMock.mockResolvedValueOnce(makeOverview())
    listFindingsMock.mockResolvedValueOnce(makePage())
    getConfigMock.mockResolvedValueOnce([makeConfig()])
    resolveFindingMock.mockResolvedValueOnce(
      makeFinding({ status: 'resolved', resolved_at: '2026-08-01T10:00:00Z', resolved_reason: 'Paid in cash' })
    )

    renderPage()

    await waitFor(() => expect(screen.getByText(/Rahul Sharma/)).toBeInTheDocument())

    await userEvent.click(screen.getByText('Resolve'))
    const dialog = screen.getByRole('dialog')
    expect(dialog).toBeInTheDocument()

    // fireEvent.change is deterministic for controlled inputs (userEvent.type
    // gets interrupted by the Modal's focus management in jsdom).
    fireEvent.change(screen.getByPlaceholderText(/reason/i), { target: { value: 'Paid in cash' } })
    await userEvent.click(within(dialog).getByRole('button', { name: 'Resolve' }))

    await waitFor(() => {
      expect(resolveFindingMock).toHaveBeenCalledWith(1, 'Paid in cash')
      expect(screen.getByText(/Resolved: Paid in cash/)).toBeInTheDocument()
    })
  })

  it('acknowledges a finding and reflects the status change', async () => {
    getOverviewMock.mockResolvedValueOnce(makeOverview())
    listFindingsMock.mockResolvedValueOnce(makePage())
    getConfigMock.mockResolvedValueOnce([makeConfig()])
    acknowledgeFindingMock.mockResolvedValueOnce(makeFinding({ status: 'acknowledged' }))

    renderPage()

    await waitFor(() => expect(screen.getByText(/Rahul Sharma/)).toBeInTheDocument())

    await userEvent.click(screen.getByText('Acknowledge'))

    await waitFor(() => {
      expect(acknowledgeFindingMock).toHaveBeenCalledWith(1)
      expect(screen.getByText('acknowledged')).toBeInTheDocument()
    })
  })
})
