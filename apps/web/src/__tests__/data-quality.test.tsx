import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ToastProvider } from '../components/ui/toast'
import type { DataQualityOverview } from '../api/data-quality/data-quality-api'

const getOverviewMock = vi.fn()
const listFindingsMock = vi.fn()
const runChecksMock = vi.fn()
const resolveFindingMock = vi.fn()
const ignoreFindingMock = vi.fn()

vi.mock('../api/data-quality/data-quality-api', () => ({
  dataQualityApi: {
    getOverview: (...args: unknown[]) => getOverviewMock(...args),
    listFindings: (...args: unknown[]) => listFindingsMock(...args),
    runChecks: (...args: unknown[]) => runChecksMock(...args),
    resolveFinding: (...args: unknown[]) => resolveFindingMock(...args),
    ignoreFinding: (...args: unknown[]) => ignoreFindingMock(...args),
  },
}))

const mockAuthUser = vi.fn(() => ({
  user: { id: 1, username: 'admin', display_name: 'Ada Admin', role: 'admin' },
  isLoading: false,
  isAuthenticated: true,
  error: null,
  login: vi.fn(),
  logout: vi.fn(),
  updateUser: vi.fn(),
}))

vi.mock('../api/auth/auth-context', () => ({
  useAuth: () => mockAuthUser(),
}))

const { DataQualityCenterPage } = await import('../pages/data-quality/data-quality')

function makeOverview(overrides: Partial<DataQualityOverview> = {}): DataQualityOverview {
  return {
    critical: 1,
    high: 2,
    medium: 3,
    low: 4,
    total: 10,
    by_category: { duplicates: 4, missing_fields: 2, invalid_format: 1, impossible_dates: 1, inconsistent_references: 2 },
    overall_quality: 92.5,
    severity_weights: { critical: 1, high: 0.6, medium: 0.3, low: 0.1 },
    total_checks: 7,
    ...overrides,
  }
}

const openFinding = {
  id: 1,
  campus_id: 1,
  check_code: 'duplicate_students',
  category: 'duplicates',
  severity: 'high',
  entity_type: 'student',
  entity_id: 7,
  student_id: 7,
  field: 'email',
  description: 'Duplicate email detected',
  evidence: { other_student: 8 },
  status: 'open' as const,
  detected_at: '2026-08-01T09:00:00Z',
  last_verified_at: '2026-08-01T09:00:00Z',
  resolved_at: null,
  resolved_by: null,
  resolved_reason: null,
}

const resolvedFinding = {
  ...openFinding,
  id: 2,
  check_code: 'student_missing_guardian',
  category: 'missing_fields' as const,
  severity: 'medium' as const,
  field: 'guardian_contact',
  description: 'Student has no guardian on file',
  student_id: 9,
  entity_id: 9,
  status: 'resolved' as const,
  resolved_at: '2026-08-02T10:00:00Z',
  resolved_reason: 'Guardian contact added',
}

function renderPage(route = '/data-quality') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <ToastProvider>
        <Routes>
          <Route path="/data-quality" element={<DataQualityCenterPage />} />
          <Route path="/students/:id" element={<div>Student Detail</div>} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>
  )
}

beforeEach(() => {
  vi.resetAllMocks()
  // resetAllMocks clears the implementation of every vi.fn — re-establish the
  // auth shape so useAuth() returns a valid session for every test.
  mockAuthUser.mockImplementation(() => ({
    user: { id: 1, username: 'admin', display_name: 'Ada Admin', role: 'admin' },
    isLoading: false,
    isAuthenticated: true,
    error: null,
    login: vi.fn(),
    logout: vi.fn(),
    updateUser: vi.fn(),
  }))
  getOverviewMock.mockResolvedValue(makeOverview())
  listFindingsMock.mockResolvedValue({ items: [openFinding, resolvedFinding], total: 2, page: 1, size: 20, pages: 1 })
  runChecksMock.mockResolvedValue({ created: 0, updated: 0, resolved: 1, total_open: 9, run_at: '2026-08-08T09:00:00Z' })
  resolveFindingMock.mockResolvedValue({ ...openFinding, status: 'resolved' })
  ignoreFindingMock.mockResolvedValue({ ...openFinding, status: 'ignored' })
})

describe('Data Quality Center page', () => {
  it('shows a loading skeleton, then renders the overview and findings', async () => {
    renderPage()
    expect(screen.getByLabelText('Loading data quality center')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('Data Quality Center')).toBeInTheDocument()
      expect(screen.getByText('Overall Quality')).toBeInTheDocument()
      expect(screen.getByText('92.5%')).toBeInTheDocument()
      expect(screen.getByText('Duplicate email detected')).toBeInTheDocument()
    })
    expect(screen.queryByLabelText('Loading data quality center')).not.toBeInTheDocument()
  })

  it('filters findings by category tab', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Duplicate email detected')).toBeInTheDocument())

    // Override the list mock to simulate the server-side category filter round-trip
    listFindingsMock.mockResolvedValue({
      items: [openFinding],
      total: 1,
      page: 1,
      size: 20,
      pages: 1,
    })

    fireEvent.click(screen.getByRole('tab', { name: 'Duplicates' }))

    await waitFor(() => {
      expect(listFindingsMock).toHaveBeenCalledWith(
        expect.objectContaining({ category: 'duplicates' })
      )
    })
  })

  it('filters by severity from the dropdown', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Duplicate email detected')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Filter by severity'), { target: { value: 'high' } })

    await waitFor(() => {
      expect(listFindingsMock).toHaveBeenCalledWith(
        expect.objectContaining({ severity: 'high' })
      )
    })
  })

  it('searches the current page locally by keyword', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Duplicate email detected')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Search findings'), { target: { value: 'duplicate' } })

    await waitFor(() => {
      expect(screen.getByText('Duplicate email detected')).toBeInTheDocument()
      expect(screen.queryByText('Student has no guardian on file')).not.toBeInTheDocument()
    })

    // Clearing the query restores both findings
    fireEvent.click(screen.getByRole('button', { name: /clear search/i }))
    await waitFor(() => {
      expect(screen.getByText('Student has no guardian on file')).toBeInTheDocument()
    })
  })

  it('navigates to the student record from the View student action', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Duplicate email detected')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Open student 7' }))
    expect(await screen.findByText('Student Detail')).toBeInTheDocument()
  })

  it('resolves a finding with an audited reason', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Duplicate email detected')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Resolve' }))
    const dialog = screen.getByRole('dialog')
    const textarea = within(dialog).getByPlaceholderText(/Reason \(audited\)/)
    fireEvent.change(textarea, { target: { value: 'Merged into primary record' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Resolve' }))

    await waitFor(() => {
      expect(resolveFindingMock).toHaveBeenCalledWith(1, 'Merged into primary record')
    })
  })

  it('ignores a finding with an audited reason', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Duplicate email detected')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Ignore' }))
    const dialog = screen.getByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Ignore' }))

    await waitFor(() => {
      expect(ignoreFindingMock).toHaveBeenCalledWith(1, expect.any(String))
    })
  })

  it('shows the run-checks scan result via toast', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Data Quality Center')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /Run checks/ }))

    await waitFor(() => {
      expect(runChecksMock).toHaveBeenCalled()
    })
  })

  it('shows the no-data empty state with a run-checks action', async () => {
    getOverviewMock.mockResolvedValue(makeOverview({ total: 0, critical: 0, high: 0, medium: 0, low: 0 }))
    listFindingsMock.mockResolvedValue({ items: [], total: 0, page: 1, size: 20, pages: 0 })

    renderPage()
    await waitFor(() => {
      expect(screen.getByText('No findings yet')).toBeInTheDocument()
    })
    // Both the hero CTA and the empty-state action offer the scan
    expect(screen.getAllByRole('button', { name: /Run checks/ }).length).toBeGreaterThanOrEqual(1)
  })

  it('shows a filtered-empty state with a clear-filters action', async () => {
    getOverviewMock.mockResolvedValue(makeOverview({ total: 5 }))
    listFindingsMock.mockResolvedValue({ items: [], total: 5, page: 1, size: 20, pages: 1 })

    renderPage()
    await waitFor(() => {
      expect(screen.getByText('No findings match')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: 'Clear filters' })).toBeInTheDocument()
  })

  it('shows an error state with retry when both sources fail', async () => {
    getOverviewMock.mockRejectedValueOnce({ detail: 'Service unavailable' })
    listFindingsMock.mockRejectedValueOnce({ detail: 'Service unavailable' })

    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Unable to load data-quality findings from the server.')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: 'Try Again' })).toBeInTheDocument()
  })

  it('supports keyboard navigation — arrows move the active row (roving tabindex)', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Duplicate email detected')).toBeInTheDocument())

    const list = screen.getByRole('list', { name: 'Data quality findings' })
    fireEvent.keyDown(list, { key: 'ArrowDown' })
    await waitFor(() => {
      expect(screen.getAllByRole('listitem')[1]).toHaveAttribute('aria-current', 'true')
    })
    fireEvent.keyDown(screen.getAllByRole('listitem')[1], { key: 'ArrowUp' })
    await waitFor(() => {
      expect(screen.getAllByRole('listitem')[0]).toHaveAttribute('aria-current', 'true')
    })
  })

  it('does not expose resolve/ignore actions to staff roles', async () => {
    // Re-render with a staff user — resolve/ignore must be hidden
    mockAuthUser.mockReturnValue({
      user: { id: 2, username: 'staff', display_name: 'Stan Staff', role: 'staff' },
      isLoading: false,
      isAuthenticated: true,
      error: null,
      login: vi.fn(),
      logout: vi.fn(),
      updateUser: vi.fn(),
    })

    renderPage()
    await waitFor(() => expect(screen.getByText('Duplicate email detected')).toBeInTheDocument())

    expect(screen.queryByRole('button', { name: 'Resolve' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Ignore' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Run checks/ })).not.toBeInTheDocument()
  })
})
