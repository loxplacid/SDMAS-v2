import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { ToastProvider } from '../components/ui/toast'
import type { PaymentReconciliationResponse } from '../api/school-finance/school-finance-api'

// Mock the API client before importing the page
const listMock = vi.fn()
const getMock = vi.fn()
const verifyMock = vi.fn()
const approveMock = vi.fn()

vi.mock('../api/school-finance/school-finance-api', () => ({
  reconciliationApi: {
    list: (...args: unknown[]) => listMock(...args),
    get: (...args: unknown[]) => getMock(...args),
    verify: (...args: unknown[]) => verifyMock(...args),
    approve: (...args: unknown[]) => approveMock(...args),
  },
}))

const { ReconciliationPage } = await import('../pages/school-finance/reconciliation')

function makeItem(id: number, paymentId: number, overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id,
    reconciliation_id: 1,
    payment_id: paymentId,
    expected_amount: 10000,
    actual_amount: 10000,
    difference: 0,
    status: 'matched',
    notes: null,
    created_at: '2026-08-01T10:00:00Z',
    ...overrides,
  } as PaymentReconciliationResponse['items'][number]
}

function makeRec(overrides: Partial<PaymentReconciliationResponse> = {}): PaymentReconciliationResponse {
  return {
    id: 1,
    reconciliation_date: '2026-08-01',
    total_amount: 20000,
    total_count: 2,
    status: 'draft',
    notes: 'Term 1 close',
    reconciled_by: 1,
    campus_id: 1,
    created_at: '2026-08-01T10:00:00Z',
    updated_at: '2026-08-01T10:00:00Z',
    items: [
      makeItem(11, 101),
      makeItem(12, 102, { expected_amount: 10000, actual_amount: 8500, difference: -1500, status: 'discrepancy' }),
    ],
    ...overrides,
  }
}

function makePage(items: PaymentReconciliationResponse[]) {
  return { items, total: items.length, page: 1, size: 20, pages: Math.ceil(items.length / 20) }
}

function renderPage() {
  return render(
    <ToastProvider>
      <ReconciliationPage />
    </ToastProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  window.history.replaceState(null, '', '/school-finance/reconciliation')
})

afterEach(async () => {
  window.history.replaceState(null, '', '/')
})

describe('Reconciliation workspace (P13)', () => {
  it('renders reconciliation rows with status badges and flagged items', async () => {
    listMock.mockResolvedValueOnce(
      makePage([
        makeRec({ id: 1, status: 'draft' }),
        makeRec({ id: 2, status: 'verified', items: [], total_amount: 0, total_count: 0, notes: null }),
      ])
    )
    renderPage()

    expect(await screen.findByText('#1')).toBeInTheDocument()
    expect(screen.getByText('#2')).toBeInTheDocument()
    expect(screen.getByText('Draft')).toBeInTheDocument()
    expect(screen.getByText('Verified')).toBeInTheDocument()
    // one discrepancy item → the list flags the count
    expect(screen.getByText('1 flagged')).toBeInTheDocument()
  })

  it('maps a status facet onto the backend filter on refetch', async () => {
    listMock.mockResolvedValueOnce(
      makePage([makeRec({ id: 1, status: 'draft' }), makeRec({ id: 2, status: 'verified', items: [] })])
    )
    renderPage()
    await screen.findByText('#1')

    fireEvent.click(screen.getByLabelText('Add filter'))
    fireEvent.click(await screen.findByRole('checkbox', { name: /verified/ }))

    await waitFor(() =>
      expect(listMock).toHaveBeenLastCalledWith(expect.objectContaining({ status: 'verified' }))
    )
  })

  it('opens the detail inspector showing per-item matched/discrepancy state', async () => {
    listMock.mockResolvedValueOnce(makePage([makeRec({ id: 1, status: 'draft' })]))
    getMock.mockResolvedValueOnce(makeRec({ id: 1, status: 'draft' }))
    renderPage()

    fireEvent.click(await screen.findByText('#1'))

    expect(await screen.findByText('Payment #101')).toBeInTheDocument()
    expect(screen.getByText('Payment #102')).toBeInTheDocument()
    // the two item states are visible, and the difference is signed
    expect(screen.getByText('matched')).toBeInTheDocument()
    expect(screen.getByText('discrepancy')).toBeInTheDocument()
    // 1,500 cents = Ksh 15 — the signed per-item difference
    expect(screen.getByText(/-Ksh\s*15/)).toBeInTheDocument()
    expect(getMock).toHaveBeenCalledWith(1)
    // the deep link is set
    expect(window.location.search).toContain('rec=1')
  })

  it('verifies a draft reconciliation from the drawer footer (audited transition)', async () => {
    listMock.mockResolvedValueOnce(makePage([makeRec({ id: 1, status: 'draft' })]))
    // initial load, then the post-transition refetch (refreshKey bump)
    getMock
      .mockResolvedValueOnce(makeRec({ id: 1, status: 'draft' }))
      .mockResolvedValueOnce(makeRec({ id: 1, status: 'verified', items: [] }))
    verifyMock.mockResolvedValueOnce(makeRec({ id: 1, status: 'verified', items: [] }))
    renderPage()

    fireEvent.click(await screen.findByText('#1'))
    fireEvent.click(await screen.findByRole('button', { name: 'Verify' }))

    await waitFor(() => expect(verifyMock).toHaveBeenCalledWith(1))
    expect(await screen.findByText('Reconciliation verified')).toBeInTheDocument()
    // the drawer refetched and now offers the next transition, not Verify
    expect(await screen.findByRole('button', { name: 'Approve' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Verify' })).not.toBeInTheDocument()
  })

  it('approves a verified reconciliation from the drawer footer', async () => {
    listMock.mockResolvedValueOnce(makePage([makeRec({ id: 1, status: 'verified', items: [] })]))
    getMock
      .mockResolvedValueOnce(makeRec({ id: 1, status: 'verified', items: [] }))
      .mockResolvedValueOnce(makeRec({ id: 1, status: 'approved', items: [] }))
    approveMock.mockResolvedValueOnce(makeRec({ id: 1, status: 'approved', items: [] }))
    renderPage()

    fireEvent.click(await screen.findByText('#1'))
    fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))

    await waitFor(() => expect(approveMock).toHaveBeenCalledWith(1))
    expect(await screen.findByText('Reconciliation approved')).toBeInTheDocument()
    // terminal state — the drawer offers no further transition
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
    )
  })

  it('renders the empty state when no reconciliations exist', async () => {
    listMock.mockResolvedValueOnce(makePage([]))
    renderPage()

    expect(await screen.findByText('No reconciliations yet')).toBeInTheDocument()
    // the toolbar action and the empty-state action both offer creation
    expect(screen.getAllByRole('button', { name: 'New Reconciliation' }).length).toBeGreaterThan(0)
  })

  it('shows an actionable error state and recovers on retry', async () => {
    listMock.mockRejectedValueOnce({ detail: 'Failed to load reconciliations' })
    renderPage()

    expect(await screen.findByText('Failed to load reconciliations')).toBeInTheDocument()

    listMock.mockResolvedValueOnce(makePage([makeRec({ id: 1, status: 'draft' })]))
    fireEvent.click(screen.getByRole('button', { name: /Try Again/i }))

    expect(await screen.findByText('#1')).toBeInTheDocument()
  })
})
