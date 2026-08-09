import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ToastProvider } from '../components/ui/toast'
import type { TransactionLogResponse } from '../api/school-finance/school-finance-api'

// Mock the API clients before importing the page
const listMock = vi.fn()
const exportMock = vi.fn()

vi.mock('../api/school-finance/school-finance-api', () => ({
  transactionLogApi: {
    list: (...args: unknown[]) => listMock(...args),
    get: vi.fn(),
    getStudentBalance: vi.fn(),
  },
}))

vi.mock('../api/reports/export-api', () => ({
  exportApi: { payments: (...args: unknown[]) => exportMock(...args) },
}))

const { TransactionsPage } = await import('../pages/school-finance/transactions')

function makeTx(overrides: Partial<TransactionLogResponse> = {}): TransactionLogResponse {
  return {
    id: 1,
    transaction_type: 'payment',
    payment_id: 10,
    fee_due_id: null,
    student_id: 5,
    amount: 5000,
    balance_before: 0,
    balance_after: 5000,
    reference_number: 'RCP-1001',
    idempotency_key: null,
    description: 'Term 1 fees',
    campus_id: 1,
    recorded_by: 1,
    created_at: '2026-08-01T09:00:00Z',
    ...overrides,
  }
}

function makePage(items: TransactionLogResponse[]) {
  return { items, total: items.length, page: 1, size: 20, pages: Math.ceil(items.length / 20) }
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <TransactionsPage />
      </ToastProvider>
    </MemoryRouter>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  window.history.replaceState(null, '', '/school-finance/transactions')
})

afterEach(() => {
  window.history.replaceState(null, '', '/')
})

describe('Transactions workspace (P13)', () => {
  it('renders ledger rows with type badges and reference numbers', async () => {
    listMock.mockResolvedValueOnce(
      makePage([
        makeTx({ id: 1, transaction_type: 'payment' }),
        makeTx({ id: 2, transaction_type: 'refund', amount: -2000, balance_after: 3000, reference_number: 'RCP-2002' }),
      ])
    )
    renderPage()

    expect(await screen.findByText('#1')).toBeInTheDocument()
    expect(screen.getByText('#2')).toBeInTheDocument()
    expect(screen.getByText('Payment')).toBeInTheDocument()
    expect(screen.getByText('Refund')).toBeInTheDocument()
    expect(screen.getByText('RCP-1001')).toBeInTheDocument()
  })

  it('maps a transaction_type facet onto the backend filter on refetch', async () => {
    listMock.mockResolvedValueOnce(
      makePage([
        makeTx({ id: 1, transaction_type: 'payment' }),
        makeTx({ id: 2, transaction_type: 'refund', amount: -2000 }),
      ])
    )
    renderPage()
    await screen.findByText('#1')

    fireEvent.click(screen.getByLabelText('Add filter'))
    fireEvent.click(await screen.findByRole('checkbox', { name: /refund/ }))

    await waitFor(() =>
      expect(listMock).toHaveBeenLastCalledWith(expect.objectContaining({ transaction_type: 'refund' }))
    )
  })

  it('maps an amount range onto min_amount/max_amount on refetch', async () => {
    listMock.mockResolvedValueOnce(makePage([makeTx()]))
    renderPage()
    await screen.findByText('#1')

    fireEvent.click(screen.getByLabelText('Add filter'))
    fireEvent.change(await screen.findByLabelText('Amount minimum'), { target: { value: '1000' } })

    await waitFor(() =>
      expect(listMock).toHaveBeenLastCalledWith(expect.objectContaining({ min_amount: 1000 }))
    )
  })

  it('maps the search box onto the backend q parameter', async () => {
    listMock.mockResolvedValueOnce(makePage([makeTx()]))
    renderPage()
    await screen.findByText('#1')

    fireEvent.change(screen.getByLabelText('Filter table'), { target: { value: 'amina' } })

    await waitFor(() =>
      expect(listMock).toHaveBeenLastCalledWith(expect.objectContaining({ q: 'amina' }))
    )
  })

  it('does not offer range filters the backend cannot honor (P13 filterable opt-out)', async () => {
    listMock.mockResolvedValueOnce(makePage([makeTx()]))
    renderPage()
    await screen.findByText('#1')

    fireEvent.click(screen.getByLabelText('Add filter'))
    // balance_before / balance_after / id / student_id are display-only:
    // no min/max inputs, no dead chips
    expect(await screen.findByLabelText('Amount minimum')).toBeInTheDocument()
    expect(screen.queryByLabelText('Balance Before minimum')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Student minimum')).not.toBeInTheDocument()
  })
})
