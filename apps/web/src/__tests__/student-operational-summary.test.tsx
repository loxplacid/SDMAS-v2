import type React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import type { Student360Response } from '../api/student-360/student-360-api'
import type { CaseItem } from '../api/cases/cases-api'

const listMock = vi.fn()
const createMock = vi.fn()
const showToastMock = vi.fn()

const { mockUser } = vi.hoisted(() => ({
  mockUser: { id: 1, username: 'admin', display_name: 'Test Admin', email: 'admin@test.local', role: 'admin' as string },
}))

vi.mock('../api/cases/cases-api', () => ({
  casesApi: {
    list: (...args: unknown[]) => listMock(...args),
    create: (...args: unknown[]) => createMock(...args),
  },
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

// can() decides finance visibility; default allows everything.
let canFn: (p: string) => boolean = () => true
vi.mock('../hooks/use-permission', () => ({
  usePermission: () => ({ can: (p: string) => canFn(p) }),
}))

vi.mock('../components/ui/toast', () => ({
  useToast: () => ({ showToast: showToastMock }),
  // The ui barrel re-exports ToastProvider; keep it harmless for imports.
  ToastProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

const { OperationalSummary } = await import('../pages/students/operational-summary')

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
    current_enrollment: {
      id: 1,
      academic_year_id: 2026,
      academic_year_name: '2026-27',
      class_id: 3,
      class_name: 'Grade 10',
      section_id: 9,
      section_name: 'A',
      status: 'active',
      enrolled_at: '2026-04-01',
    },
    attendance: { total: 40, present: 38, absent: 1, late: 1, excused: 0, percentage: 95 },
    attendance_records: [],
    financial: { total_fees_assigned: 500000, total_paid: 450000, total_outstanding: 50000, unpaid_count: 1, partially_paid_count: 0, paid_count: 3 },
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
    lifecycle: null,
    documents: [],
    ...overrides,
  }
}

function makeCase(id: number, overrides: Partial<CaseItem> = {}): CaseItem {
  return {
    id,
    case_number: `DMAS-${String(id).padStart(6, '0')}`,
    campus_id: 1,
    title: 'Attendance anomaly — Grade 10A',
    description: null,
    case_type: 'attendance',
    priority: 'high',
    original_priority: 'high',
    status: 'open',
    source_type: 'risk_finding',
    source_id: 5,
    student_id: 101,
    created_by: 1,
    assigned_to: null,
    assigned_at: null,
    due_at: null,
    escalated_at: null,
    resolved_at: null,
    resolved_by: null,
    resolved_reason: null,
    closed_at: null,
    closed_by: null,
    version: 1,
    created_at: '2026-08-01T00:00:00Z',
    updated_at: '2026-08-01T00:00:00Z',
    sla_state: 'ON_TRACK',
    assignee_name: null,
    ...overrides,
  }
}

function renderSummary(data: Student360Response = make360(), route = '/students/101/360') {
  const onOpenTab = vi.fn()
  const utils = render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route
          path="/students/:id/360"
          element={<OperationalSummary data={data} onOpenTab={onOpenTab} />}
        />
        <Route path="/cases/:id" element={<div>Case detail page</div>} />
        <Route path="/work" element={<div>Work queue</div>} />
        <Route path="/students/:id" element={<div>Standard view</div>} />
      </Routes>
    </MemoryRouter>
  )
  return { ...utils, onOpenTab }
}

beforeEach(() => {
  vi.resetAllMocks()
  canFn = () => true
  mockUser.role = 'admin'
  listMock.mockResolvedValue({ items: [], total: 0, page: 1, size: 3, pages: 0 })
})

describe('OperationalSummary — signals', () => {
  it('renders the identity strip with status, class/section and student number', async () => {
    renderSummary()
    expect(screen.getByText('Operational Status')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByText(/Grade 10 - A/)).toBeInTheDocument()
    expect(screen.getByText('Student #A001')).toBeInTheDocument()
  })

  it('derives an attendance signal from the real percentage', () => {
    renderSummary(make360())
    expect(screen.getByText('95%')).toBeInTheDocument()
    // Healthy attendance: no review action offered.
    expect(screen.queryByRole('button', { name: /Review attendance/ })).not.toBeInTheDocument()
  })

  it('flags at-risk attendance (<75%) and offers a review action', () => {
    renderSummary(make360({ attendance: { total: 40, present: 30, absent: 8, late: 2, excused: 0, percentage: 75 } }))
    // 75 is the product threshold — at or above it, no warning.
    expect(screen.queryByRole('button', { name: /Review attendance/ })).not.toBeInTheDocument()
  })

  it('flags at-risk attendance below the threshold and the action opens the attendance tab', async () => {
    const { onOpenTab } = renderSummary(make360({ attendance: { total: 40, present: 29, absent: 9, late: 2, excused: 0, percentage: 72.5 } }))
    const btn = screen.getByRole('button', { name: /Review attendance/ })
    await userEvent.click(btn)
    expect(onOpenTab).toHaveBeenCalledWith('attendance')
  })

  it('shows the outstanding balance and a fee action when the role has finance access', async () => {
    const { onOpenTab } = renderSummary()
    expect(screen.getByText('$50,000')).toBeInTheDocument()
    const btn = screen.getByRole('button', { name: /View fee issue/ })
    await userEvent.click(btn)
    expect(onOpenTab).toHaveBeenCalledWith('finance')
  })

  it('hides finance data and actions from roles without FEES_VIEW', () => {
    canFn = (p) => p !== 'fees.view'
    renderSummary()
    expect(screen.getByText('No finance access')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /View fee issue/ })).not.toBeInTheDocument()
  })

  it('shows open findings from the risk engine and links to the risk tab', async () => {
    const { onOpenTab } = renderSummary(make360({
      risk_findings: [
        { id: 1, rule_code: 'attendance_below_threshold', category: 'attendance', severity: 'high', score: 0.8, reason: 'Below threshold', recommended_action: 'Review', detected_at: '2026-08-01T00:00:00Z' },
      ],
    }))
    expect(screen.getByText('Open findings')).toBeInTheDocument()
    const btn = screen.getByRole('button', { name: /Review findings \(1\)/ })
    await userEvent.click(btn)
    expect(onOpenTab).toHaveBeenCalledWith('risk')
  })
})

describe('OperationalSummary — active cases', () => {
  it('loads cases scoped to the student with view=open and priority sort', async () => {
    renderSummary()
    await waitFor(() => {
      expect(listMock).toHaveBeenCalledWith({ student_id: 101, view: 'open', sort: 'priority', size: 3 })
    })
  })

  it('does not fetch cases for roles the backend excludes from the queue', async () => {
    mockUser.role = 'accountant'
    renderSummary()
    await new Promise((r) => setTimeout(r, 10))
    expect(listMock).not.toHaveBeenCalled()
    expect(screen.getByText('Work queue restricted')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Create case/ })).not.toBeInTheDocument()
  })

  it('renders the active case count and opens the top case', async () => {
    listMock.mockResolvedValue({
      items: [makeCase(421, { priority: 'critical', sla_state: 'OVERDUE' }), makeCase(422)],
      total: 2, page: 1, size: 3, pages: 1,
    })
    renderSummary()
    await waitFor(() => {
      expect(screen.getByText('2')).toBeInTheDocument()
    })
    await userEvent.click(screen.getByRole('button', { name: /Open case DMAS-000421/ }))
    expect(await screen.findByText('Case detail page')).toBeInTheDocument()
  })

  it('shows a loading state while cases are in flight', () => {
    listMock.mockReturnValue(new Promise(() => {}))
    renderSummary()
    expect(screen.getByText('Active cases')).toBeInTheDocument()
    expect(screen.getByText('…')).toBeInTheDocument()
  })

  it('degrades gracefully when the cases fetch fails', async () => {
    listMock.mockRejectedValue({ detail: 'boom' })
    renderSummary()
    await waitFor(() => {
      expect(screen.getByText('Unavailable')).toBeInTheDocument()
    })
  })
})

describe('OperationalSummary — create case', () => {
  it('creates a case linked to the student and navigates to it', async () => {
    createMock.mockResolvedValue(makeCase(999, { case_number: 'DMAS-000999' }))
    renderSummary()

    await userEvent.click(screen.getByRole('button', { name: /Create case/ }))
    await userEvent.type(screen.getByLabelText('Title'), 'Phone number missing on record')

    await userEvent.click(screen.getByRole('button', { name: /Create case for Rahul/ }))

    await waitFor(() => {
      expect(createMock).toHaveBeenCalledWith(expect.objectContaining({
        title: 'Phone number missing on record',
        student_id: 101,
      }))
    })
    expect(showToastMock).toHaveBeenCalledWith('Case DMAS-000999 created', 'success')
    expect(await screen.findByText('Case detail page')).toBeInTheDocument()
  })

  it('does not submit an empty title', async () => {
    renderSummary()
    await userEvent.click(screen.getByRole('button', { name: /Create case/ }))
    const submit = screen.getByRole('button', { name: /Create case for Rahul/ })
    expect(submit).toBeDisabled()
    fireEvent.click(submit)
    expect(createMock).not.toHaveBeenCalled()
  })

  it('shows a toast when creation fails', async () => {
    createMock.mockRejectedValue({ detail: 'SLA config missing' })
    renderSummary()
    await userEvent.click(screen.getByRole('button', { name: /Create case/ }))
    await userEvent.type(screen.getByLabelText('Title'), 'Overdue fee escalation')
    await userEvent.click(screen.getByRole('button', { name: /Create case for Rahul/ }))
    await waitFor(() => {
      expect(showToastMock).toHaveBeenCalledWith('SLA config missing', 'error')
    })
  })
})

describe('OperationalSummary — navigation & partial data', () => {
  it('shows a placeholder attendance signal when no records exist yet', () => {
    renderSummary(make360({ attendance: { total: 0, present: 0, absent: 0, late: 0, excused: 0, percentage: 0 } }))
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('links to the full profile while preserving the student identity', async () => {
    renderSummary()
    await userEvent.click(screen.getByRole('button', { name: /Full profile/ }))
    expect(await screen.findByText('Standard view')).toBeInTheDocument()
  })

  it('does not render a case preview list when there are no cases', async () => {
    renderSummary()
    await waitFor(() => expect(listMock).toHaveBeenCalled())
    // The active-cases signal cell shows 0 and no preview list block.
    const cell = screen.getByText('Active cases').closest('[data-signal]') as HTMLElement | null
    expect(cell).not.toBeNull()
    expect(within(cell!).queryByText('DMAS-')).not.toBeInTheDocument()
  })

  it('degrades without crashing when the 360 response omits aggregate modules', () => {
    const sparse = make360() as Partial<Student360Response>
    delete sparse.attendance
    delete sparse.financial
    delete sparse.risk_findings
    renderSummary(sparse as Student360Response)
    // Attendance + finance show honest placeholders instead of throwing.
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('No finance data')).toBeInTheDocument()
    // Identity strip still renders; open findings counts zero modules safely.
    expect(screen.getByText('Operational Status')).toBeInTheDocument()
    expect(screen.getByText('0')).toBeInTheDocument()
  })
})
