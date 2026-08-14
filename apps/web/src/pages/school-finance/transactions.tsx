import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  transactionLogApi,
  type SchoolFinanceListParams,
  type TransactionLogResponse,
} from '../../api/school-finance/school-finance-api'
import { Button, Badge, useToast } from '../../components/ui'
import type { Column } from '../../components/ui/table'
import { DataWorkspace, useWorkspace } from '../../components/data-workspace'
import { formatCurrency, plural } from '../../lib/utils'

/**
 * P13 — Transaction workspace. The ledger's filter rail maps onto the
 * server params (student id / type / date / amount range / `q` text search),
 * the workspace state is URL-synced (deep-linkable, refresh-safe), and the
 * Finance-tab of Student 360 deep-links here with `?student_id=` — which
 * this page keeps as part of its canonical URL while the filter is active.
 */

const typeBadge: Record<string, 'info' | 'success' | 'danger' | 'warning' | 'neutral'> = {
  payment: 'success', refund: 'danger', waiver: 'warning', adjustment: 'info', reversal: 'neutral', fine: 'danger', discount: 'info',
}

// Server mode: the rail only offers filters the backend honors — type facet,
// created_at/amount ranges and `q` search. The remaining numeric columns keep
// their display types but opt out of the rail (P13 `filterable: false`).
const TRANSACTION_COLUMNS: Column<TransactionLogResponse>[] = [
  { key: 'id', header: 'ID', type: 'numeric', filterable: false, render: (r) => `#${r.id}` },
  {
    key: 'transaction_type',
    header: 'Type',
    type: 'status',
    render: (r) => (
      <Badge variant={typeBadge[r.transaction_type] || 'neutral'}>
        {r.transaction_type.replace('_', ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}
      </Badge>
    ),
  },
  {
    key: 'amount',
    header: 'Amount',
    type: 'amount',
    currency: 'KES',
    render: (r) => (
      <span className={r.amount >= 0 ? 'text-[var(--color-success-dark)]' : 'text-[var(--color-danger)]'}>
        {formatCurrency(r.amount)}
      </span>
    ),
  },
  { key: 'student_id', header: 'Student', type: 'numeric', filterable: false, render: (r) => `#${r.student_id}` },
  { key: 'balance_before', header: 'Balance Before', type: 'amount', currency: 'KES', filterable: false, render: (r) => formatCurrency(r.balance_before), hideOnMobile: true },
  { key: 'balance_after', header: 'Balance After', type: 'amount', currency: 'KES', filterable: false, render: (r) => formatCurrency(r.balance_after), hideOnMobile: true },
  { key: 'reference_number', header: 'Reference', type: 'text', render: (r) => r.reference_number || '-', hideOnMobile: true },
  { key: 'description', header: 'Description', type: 'text', render: (r) => r.description || '-', hideOnMobile: true },
  { key: 'created_at', header: 'Date', type: 'date', render: (r) => r.created_at ? new Date(r.created_at).toLocaleDateString('en-KE') : '-' },
]

export const TransactionsPage: React.FC = () => {
  const { showToast } = useToast()

  const workspace = useWorkspace<TransactionLogResponse>({
    viewKey: 'transactions',
    columns: TRANSACTION_COLUMNS,
    defaultPageSize: 20,
  })

  const [data, setData] = useState<TransactionLogResponse[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  const fetch = useCallback(async (params: SchoolFinanceListParams, showLoading: boolean) => {
    const fetchId = ++fetchIdRef.current
    if (showLoading) setLoading(true)
    setError(null)
    try {
      const result = await transactionLogApi.list(params)
      if (fetchId === fetchIdRef.current) {
        setData(result.items); setTotal(result.total); setPages(result.pages)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load transactions')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [])

  // Server round-trip: map the filter rail onto the backend params.
  // `q` is the ledger free-text search; a bare numeric query additionally
  // resolves as a student id on the backend.
  const buildParams = useCallback((): SchoolFinanceListParams => {
    const params: SchoolFinanceListParams = {}
    const q = workspace.filters.query.trim()
    if (q) params.q = q
    const t = workspace.filters.facets.transaction_type
    if (t && t.length > 0) params.transaction_type = t[t.length - 1]
    const date = workspace.filters.ranges.created_at
    if (date?.min) params.from_date = String(date.min)
    if (date?.max) params.to_date = String(date.max)
    const amount = workspace.filters.ranges.amount
    if (amount?.min !== undefined) params.min_amount = Number(amount.min)
    if (amount?.max !== undefined) params.max_amount = Number(amount.max)
    return params
  }, [workspace.filters])

  useEffect(() => {
    const params = { ...buildParams(), page: workspace.page, size: workspace.size }
    const q = workspace.filters.query.trim()

    // `?student_id=` deep-link (from Student 360's ledger link): kept in the
    // canonical URL while active, dropped when the query no longer matches.
    const studentParam = new URLSearchParams(window.location.search).get('student_id')
    const numericQuery = Number(q)
    if (q && Number.isFinite(numericQuery)) {
      params.student_id = numericQuery
      if (studentParam !== q) {
        const url = new URL(window.location.href)
        url.searchParams.set('student_id', q)
        window.history.replaceState(null, '', url)
      }
    } else if (studentParam) {
      const url = new URL(window.location.href)
      url.searchParams.delete('student_id')
      window.history.replaceState(null, '', url)
    }

    fetch(params, true)
  }, [workspace.page, workspace.size, workspace.filters, buildParams, fetch])

  const [exporting, setExporting] = useState(false)
  const handleExport = async () => {
    setExporting(true)
    try {
      const blob = await transactionLogApi.exportCsv(buildParams())
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'transactions.csv'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
      showToast('Ledger export downloaded', 'success')
    } catch (err: any) {
      showToast(err?.detail || 'Export failed', 'error')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="space-y-4">
      <DataWorkspace
        workspace={workspace}
        title="Transactions"
        description={plural(total, 'ledger entry', 'ledger entries', 'en-KE')}
        columns={TRANSACTION_COLUMNS}
        keyExtractor={(r) => r.id}
        data={data}
        total={total}
        pages={pages}
        loading={loading}
        error={error}
        onRetry={() => fetch({ page: workspace.page, size: workspace.size }, true)}
        onRefresh={() => fetch({ page: workspace.page, size: workspace.size }, false)}
        mode="server"
        filterPlaceholder="Search reference, description, or student #…"
        toolbarActions={
          <Button variant="secondary" onClick={handleExport} loading={exporting}>
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Export
          </Button>
        }
      />

      <div className="text-xs text-[var(--color-text-tertiary)]">
        <Link to="/school-finance" className="font-medium text-[var(--color-brand-accent)] hover:underline">
          Finance hub
        </Link>
      </div>
    </div>
  )
}

export default TransactionsPage
