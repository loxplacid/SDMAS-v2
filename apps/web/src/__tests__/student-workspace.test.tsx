import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useLocation, useNavigate } from 'react-router-dom'
import { ToastProvider } from '../components/ui/toast'
import type { Student360Response } from '../api/student-360/student-360-api'

/**
 * P9 — Students workspace integration: list → inspector with URL selection,
 * back/forward, Escape, keyboard navigation, inspector async states, and
 * responsive + reduced-motion behavior.
 */

const listMock = vi.fn()
const getMock = vi.fn()

vi.mock('../api/student/student-api', () => ({
  studentApi: {
    list: (...args: unknown[]) => listMock(...args),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}))

vi.mock('../api/student-360/student-360-api', () => ({
  student360Api: {
    get: (...args: unknown[]) => getMock(...args),
    getLifecycle: vi.fn(),
    transition: vi.fn(),
  },
}))

vi.mock('../api/reports/export-api', () => ({
  exportApi: { students: vi.fn() },
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

vi.mock('../hooks/use-permission', () => ({
  usePermission: () => ({ can: () => true }),
}))

vi.mock('../components/delight/delight-provider', () => ({
  useDelight: () => ({ celebrate: vi.fn() }),
}))

const { StudentListPage } = await import('../pages/students/student-list')

const students = [
  { id: 1, first_name: 'Amina', last_name: 'Yusuf', student_number: 'S-001', email: 'amina@school.edu.ng', date_of_birth: '2010-01-01', status: 'active', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' },
  { id: 2, first_name: 'Bello', last_name: 'Musa', student_number: 'S-002', email: 'bello@school.edu.ng', date_of_birth: '2010-02-02', status: 'inactive', created_at: '2026-01-02T00:00:00Z', updated_at: '2026-01-02T00:00:00Z' },
]

function make360(id: number, overrides: Partial<Student360Response> = {}): Student360Response {
  const student = students.find((s) => s.id === id)!
  return {
    identity: { ...student },
    guardians: [],
    contacts: [],
    enrollments: [],
    current_enrollment: null,
    attendance: { total: 10, present: 9, absent: 1, late: 0, excused: 0, percentage: 90 },
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
      current_status: student.status,
      allowed_transitions: [],
      lifecycle_order: ['prospective', 'admitted', 'enrolled', 'active', 'transferred', 'withdrawn', 'graduated', 'alumni'],
      recent_events: [],
    },
    documents: [],
    ...overrides,
  }
}

let currentSearch = ''
let nav!: (delta: number) => void

function UrlProbe() {
  currentSearch = useLocation().search
  return null
}
function NavProbe() {
  nav = useNavigate()
  return null
}

function renderPage(initial = '/students') {
  currentSearch = ''
  render(
    <MemoryRouter initialEntries={[initial]}>
      <ToastProvider>
        <UrlProbe />
        <NavProbe />
        <Routes>
          <Route path="/students" element={<StudentListPage />} />
          <Route path="/students/:id" element={<div>Standard profile</div>} />
          <Route path="/students/:id/360" element={<div>Student 360</div>} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>
  )
}

function stubMatchMedia(queries: Record<string, boolean>) {
  vi.stubGlobal(
    'matchMedia',
    (query: string) =>
      ({
        matches: queries[query] ?? false,
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      }) as MediaQueryList
  )
}

beforeEach(() => {
  vi.resetAllMocks()
  listMock.mockResolvedValue({ items: students, total: students.length, pages: 1, page: 1 })
  getMock.mockImplementation((id: number) => Promise.resolve(make360(id)))
})

afterEach(() => {
  vi.unstubAllGlobals()
  document.body.style.overflow = ''
})

describe('Students workspace — selection & URL sync', () => {
  it('clicking a row opens the inspector and deep-links the URL', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('S-001')).toBeInTheDocument())

    fireEvent.click(screen.getByText('Amina'))

    await waitFor(() => expect(getMock).toHaveBeenCalledWith(1))
    const panel = screen.getByRole('complementary')
    expect(within(panel).getByText('Amina Yusuf')).toBeInTheDocument()
    expect(within(panel).getByText('90%')).toBeInTheDocument()
    expect(currentSearch).toContain('student=1')
    // The row is marked as the current row.
    expect(document.querySelector('tr[aria-current="true"]')?.textContent).toContain('Amina')
  })

  it('a refreshed page with ?student= restores the selection', async () => {
    renderPage('/students?student=2')
    await waitFor(() => expect(getMock).toHaveBeenCalledWith(2))
    const panel = screen.getByRole('complementary')
    expect(within(panel).getByText('Bello Musa')).toBeInTheDocument()
  })

  it('Escape closes the inspector and clears the URL param', async () => {
    renderPage('/students?student=1')
    await waitFor(() => expect(getMock).toHaveBeenCalledWith(1))
    expect(screen.getByRole('complementary')).toBeInTheDocument()

    fireEvent.keyDown(document, { key: 'Escape' })

    await waitFor(() => expect(screen.queryByRole('complementary')).not.toBeInTheDocument())
    expect(currentSearch).not.toContain('student=')
  })

  it('browser back navigates through selections and returns to the plain list', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Amina')).toBeInTheDocument())

    fireEvent.click(screen.getByText('Amina'))
    await waitFor(() => expect(within(screen.getByRole('complementary')).getByText('Amina Yusuf')).toBeInTheDocument())

    fireEvent.click(screen.getByText('Bello'))
    await waitFor(() => expect(getMock).toHaveBeenCalledWith(2))
    await waitFor(() => expect(within(screen.getByRole('complementary')).getByText('Bello Musa')).toBeInTheDocument())

    act(() => nav(-1))
    await waitFor(() => expect(within(screen.getByRole('complementary')).getByText('Amina Yusuf')).toBeInTheDocument())

    act(() => nav(-1))
    await waitFor(() => expect(screen.queryByRole('complementary')).not.toBeInTheDocument())
  })

  it('opens the 360 page from the inspector footer action', async () => {
    renderPage('/students?student=1')
    await waitFor(() => expect(within(screen.getByRole('complementary')).getByText('Amina Yusuf')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Open 360/i }))
    expect(await screen.findByText('Student 360')).toBeInTheDocument()
  })

  it('keeps the workspace filter while the inspector is open and after closing (detail continuity)', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('S-001')).toBeInTheDocument())

    // Filter the workspace down to Bello.
    fireEvent.change(screen.getByLabelText('Filter table'), { target: { value: 'bello' } })
    await waitFor(() => expect(screen.queryByText('S-001')).not.toBeInTheDocument())

    // Open the inspector on the filtered row.
    fireEvent.click(screen.getByText('Bello'))
    await waitFor(() => expect(getMock).toHaveBeenCalledWith(2))
    expect(within(screen.getByRole('complementary')).getByText('Bello Musa')).toBeInTheDocument()
    // The inspector must not reset the workspace filter.
    expect(screen.queryByText('S-001')).not.toBeInTheDocument()

    // Close the inspector — the filter still applies.
    fireEvent.keyDown(document, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByRole('complementary')).not.toBeInTheDocument())
    expect(screen.queryByText('S-001')).not.toBeInTheDocument()
    expect((screen.getByLabelText('Filter table') as HTMLInputElement).value).toBe('bello')
  })
})

describe('Students workspace — keyboard navigation', () => {
  it('ArrowDown moves the selection to the next row; Enter opens', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Amina')).toBeInTheDocument())

    const row1 = screen.getByText('Amina').closest('tr')!
    fireEvent.keyDown(row1, { key: 'ArrowDown' })

    // Selection follows keyboard focus → inspector previews Bello.
    await waitFor(() => expect(getMock).toHaveBeenCalledWith(2))
    expect(within(screen.getByRole('complementary')).getByText('Bello Musa')).toBeInTheDocument()

    // Enter activates the currently focused row (still opens the inspector).
    const row2 = screen.getByText('Bello').closest('tr')!
    fireEvent.keyDown(row2, { key: 'Enter' })
    await waitFor(() => expect(getMock).toHaveBeenCalledWith(2))
  })
})

describe('Students workspace — inspector async states', () => {
  it('shows a skeleton while the 360 loads, then the preview', async () => {
    let resolveFn!: (v: Student360Response) => void
    getMock.mockReturnValue(new Promise((res) => { resolveFn = res }))

    renderPage('/students?student=1')
    await waitFor(() => expect(screen.getByRole('status')).toBeInTheDocument())

    resolveFn(make360(1))
    await waitFor(() => expect(within(screen.getByRole('complementary')).getByText('Amina Yusuf')).toBeInTheDocument())
  })

  it('shows an error state with retry when the preview fails', async () => {
    getMock
      .mockRejectedValueOnce({ detail: 'Student 360 unavailable' })
      .mockImplementation((id: number) => Promise.resolve(make360(id)))

    renderPage('/students?student=1')
    await waitFor(() => expect(screen.getByText('Student 360 unavailable')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /Try Again/i }))
    await waitFor(() => expect(within(screen.getByRole('complementary')).getByText('Amina Yusuf')).toBeInTheDocument())
  })
})

describe('Students workspace — motion & responsive', () => {
  it('renders without a spatial slide under reduced motion', async () => {
    renderPage('/students?student=1')
    await waitFor(() => expect(getMock).toHaveBeenCalledWith(1))
    const panel = screen.getByRole('complementary')
    expect(panel.style.transition).toBe('none')
    expect(panel.style.transform).toBe('translateX(0)')
  })

  it('becomes a full-screen sheet on mobile (list → detail)', async () => {
    stubMatchMedia({
      '(min-width: 1024px)': false,
      '(prefers-reduced-motion: reduce)': false,
      '(prefers-reduced-transparency: reduce)': false,
    })
    renderPage('/students?student=1')
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())
    expect(document.body.style.overflow).toBe('hidden')
    expect(within(screen.getByRole('dialog')).getByText('Amina Yusuf')).toBeInTheDocument()

    fireEvent.keyDown(document, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitFor(() => expect(document.body.style.overflow).toBe(''))
  })
})
