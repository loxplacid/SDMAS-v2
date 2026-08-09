import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ToastProvider } from '../components/ui/toast'
import type { FinancialException, FinancialExceptionSummary } from '../api/school-finance/school-finance-api'

// Mock the API client before importing the page
const listMock = vi.fn()
const casesApiCreateMock = vi.fn()

vi.mock('../api/school-finance/school-finance-api', () => ({
  financialExceptionApi: {
    list: (...args: unknown[]) => listMock(...args),
  },
}))

vi.mock('../api/cases/cases-api', () => ({
  casesApi: { create: (...args: unknown[]) => casesApiCreateMock(...args) },
}))

// Mock auth context (role drives who can create cases)
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
const { FinancialExceptionsPage } = await import('../pages/school-finance/exceptions')

function makeException(overrides: Partial<FinancialException> = {}): FinancialException {
  return {
    key: 'reconciliation-discrepancy:9',
    category: 'reconciliation',
    severity: 'high',
    title: 'Reconciliation discrepancy',
    description: 'Payment #91 in reconciliation #3 (draft): expected 10000, actual 8500, difference 1500.',
    student_id: 101,
    student_name: 'Rahul Sharma',
    payment_id: 91,
    amount: 8500,
    reconciliation_item_id: 9,
    reconciliation_status: 'draft',
    evidence: { expected_amount: 10000, actual_amount: 8500, difference: 1500 },
    created_at: '2026-08-01T09:00:00Z',
    linked_case: null,
    ...overrides,
  }
}

function makeSummary(items: FinancialException[] = [makeException()]): FinancialExceptionSummary {
  const bySeverity = { critical: 0, high: 0, medium: 0, low: 0 }
  const byCategory: Record<string, number> = {}
  for (const f of items) {
    bySeverity[f.severity as keyof typeof bySeverity] =
      (bySeverity[f.severity as keyof typeof bySeverity] ?? 0) + 1
    byCategory[f.category] = (byCategory[f.category] ?? 0) + 1
  }
  return { total: items.length, by_category: byCategory, by_severity: bySeverity, items }
}

function renderPage(route = '/school-finance/exceptions') {
  return render(
    <ToastProvider>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/school-finance/exceptions" element={<FinancialExceptionsPage />} />
          <Route path="/cases/:id" element={<div>Case Detail Page</div>} />
          <Route path="/students/:id/360" element={<div>Student 360 Page</div>} />
        </Routes>
      </MemoryRouter>
    </ToastProvider>
  )
}

beforeEach(() => {
  vi.resetAllMocks()
  mockRole = 'principal'
})

describe('Financial Exceptions page (P13)', () => {
  it('shows the skeleton while loading, then renders severity counts + findings', async () => {
    let resolve!: (v: FinancialExceptionSummary) => void
    listMock.mockReturnValue(new Promise((res) => { resolve = res }))

    renderPage()

    expect(screen.getByLabelText('Loading financial exceptions')).toBeInTheDocument()

    resolve(makeSummary())
    await waitFor(() => {
      expect(screen.getByText('Financial Exceptions')).toBeInTheDocument()
      expect(screen.getByText('Reconciliation discrepancy')).toBeInTheDocument()
    })
    expect(screen.queryByLabelText('Loading financial exceptions')).not.toBeInTheDocument()
  })

  it('renders an error state with retry when the API fails', async () => {
    listMock.mockRejectedValueOnce({ detail: 'Service unavailable' })

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Service unavailable')).toBeInTheDocument()
    })
    expect(screen.getByText('Try Again')).toBeInTheDocument()
  })

  it('shows a clean-ledger empty state when there are no findings', async () => {
    listMock.mockResolvedValueOnce(makeSummary([]))

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('No financial exceptions')).toBeInTheDocument()
    })
  })

  it('promotes an exception into an operational case and opens it', async () => {
    listMock.mockResolvedValueOnce(makeSummary([makeException()]))
    casesApiCreateMock.mockResolvedValueOnce({ id: 77, case_number: 'DMAS-000077' })

    renderPage()

    await waitFor(() => expect(screen.getByText('Reconciliation discrepancy')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: /Create case/ }))

    await waitFor(() => {
      expect(casesApiCreateMock).toHaveBeenCalledWith({
        title: 'Reconciliation discrepancy',
        description: expect.stringContaining('Payment #91'),
        case_type: 'finance',
        priority: 'high',
        source_type: 'financial_exception',
        source_id: 9,
        student_id: 101,
      })
      expect(screen.getByText('Case Detail Page')).toBeInTheDocument()
    })
  })

  it('surfaces a 409 (case already exists) without creating a duplicate', async () => {
    listMock.mockResolvedValueOnce(makeSummary([makeException()]))
    casesApiCreateMock.mockRejectedValueOnce({ status: 409 })
    // refresh after the conflict — returns the finding WITH a linked case
    listMock.mockResolvedValueOnce(makeSummary([
      makeException({ linked_case: { id: 42, case_number: 'DMAS-000042', status: 'in_progress' } }),
    ]))

    renderPage()

    await waitFor(() => expect(screen.getByText('Reconciliation discrepancy')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: /Create case/ }))

    await waitFor(() => {
      // the refresh re-fetch now shows the linked case instead of create
      expect(screen.getByText(/Case DMAS-000042/)).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Create case/ })).not.toBeInTheDocument()
    })
  })

  it('shows Open case for a finding that already has a linked case', async () => {
    listMock.mockResolvedValueOnce(makeSummary([
      makeException({ linked_case: { id: 42, case_number: 'DMAS-000042', status: 'open' } }),
    ]))

    renderPage()

    await waitFor(() => expect(screen.getByText('Reconciliation discrepancy')).toBeInTheDocument())

    expect(screen.getByRole('button', { name: /Open case/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Create case/ })).not.toBeInTheDocument()
    expect(casesApiCreateMock).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('button', { name: /Open case/ }))
    expect(await screen.findByText('Case Detail Page')).toBeInTheDocument()
  })

  it('filters findings by category chips', async () => {
    const both = makeSummary([
      makeException(),
      makeException({
        key: 'payment-no-receipt:5',
        category: 'receipts',
        severity: 'medium',
        title: 'Payment without receipt',
        description: 'Payment #5 has no generated receipt.',
        payment_id: 5,
        reconciliation_item_id: null,
        evidence: {},
      }),
    ])

    listMock.mockResolvedValueOnce(both)

    renderPage()

    await waitFor(() => expect(screen.getByText('Payment without receipt')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: /Reconciliation/ }))
    expect(screen.queryByText('Payment without receipt')).not.toBeInTheDocument()
    expect(screen.getByText('Reconciliation discrepancy')).toBeInTheDocument()
  })

  it('hides Create case for roles without case-create permission', async () => {
    mockRole = 'teacher'
    listMock.mockResolvedValueOnce(makeSummary([makeException()]))

    renderPage()

    await waitFor(() => expect(screen.getByText('Reconciliation discrepancy')).toBeInTheDocument())

    expect(screen.queryByRole('button', { name: /Create case/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Open case/ })).not.toBeInTheDocument()
  })
})
