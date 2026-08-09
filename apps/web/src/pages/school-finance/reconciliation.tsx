import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  reconciliationApi,
  type PaymentReconciliationResponse,
  type SchoolFinanceListParams,
} from '../../api/school-finance/school-finance-api'
import { Button, Badge, Modal, Input, useToast } from '../../components/ui'
import type { Column } from '../../components/ui/table'
import { DataWorkspace, useWorkspace } from '../../components/data-workspace'
import { formatDate } from '../../lib/utils'
import { ReconciliationDetail } from './reconciliation-detail'

/**
 * P13 — Reconciliation workspace. The operational surface for the finance
 * lifecycle's VALIDATION → RECONCILIATION step: the workspace's filter rail
 * maps onto the backend params (status facet / date range / notes search),
 * the state is URL-synced, and the detail inspector exposes every ledger
 * item with its matched / unmatched / discrepancy state. Verify and Approve
 * are audited backend transitions (draft → verified → approved); a rejected
 * reconciliation is terminal on this surface.
 */

function formatKes(amount: number) {
  return (amount / 100).toLocaleString('en-KE', {
    style: 'currency',
    currency: 'KES',
    minimumFractionDigits: 0,
  })
}

const statusBadge: Record<string, 'neutral' | 'info' | 'success' | 'danger'> = {
  draft: 'neutral',
  submitted: 'info',
  verified: 'info',
  approved: 'success',
  rejected: 'danger',
}

export const ReconciliationPage: React.FC = () => {
  const { showToast } = useToast()

  const workspace = useWorkspace<PaymentReconciliationResponse>({
    viewKey: 'reconciliation',
    columns: RECONCILIATION_COLUMNS,
    defaultPageSize: 20,
  })

  const [data, setData] = useState<PaymentReconciliationResponse[]>([])
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
      const result = await reconciliationApi.list(params)
      if (fetchId === fetchIdRef.current) {
        setData(result.items)
        setTotal(result.total)
        setPages(result.pages)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load reconciliations')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [])

  // Server round-trip: map the filter rail onto the backend params
  // (status facet → `status`, reconciliation-date range → from/to, and the
  // search box → `q` over notes / id).
  useEffect(() => {
    const params: SchoolFinanceListParams = { page: workspace.page, size: workspace.size }
    const status = workspace.filters.facets.status
    if (status && status.length > 0) params.status = status[status.length - 1]
    const date = workspace.filters.ranges.reconciliation_date
    if (date?.min) params.from_date = String(date.min)
    if (date?.max) params.to_date = String(date.max)
    const q = workspace.filters.query.trim()
    if (q) params.q = q
    fetch(params, true)
  }, [workspace.page, workspace.size, workspace.filters, fetch])

  // ── create (kept from the legacy page — real functionality) ──
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState({
    reconciliation_date: '',
    total_amount: '',
    total_count: '',
    notes: '',
  })
  const [creating, setCreating] = useState(false)

  const handleCreate = async () => {
    setCreating(true)
    try {
      await reconciliationApi.create({
        reconciliation_date: form.reconciliation_date,
        total_amount: form.total_amount ? Number(form.total_amount) : undefined,
        total_count: form.total_count ? Number(form.total_count) : undefined,
        notes: form.notes || null,
      })
      showToast('Reconciliation created', 'success')
      setShowModal(false)
      setForm({ reconciliation_date: '', total_amount: '', total_count: '', notes: '' })
      fetch({ page: workspace.page, size: workspace.size }, false)
    } catch (err: any) {
      showToast(err?.detail || 'Failed to create reconciliation', 'error')
    } finally {
      setCreating(false)
    }
  }

  // ── verify / approve (audited backend transitions) ──
  const [busyId, setBusyId] = useState<number | null>(null)
  const [detailRefresh, setDetailRefresh] = useState(0)

  const runTransition = async (
    id: number,
    action: 'verify' | 'approve',
    successMessage: string
  ) => {
    setBusyId(id)
    try {
      await (action === 'verify' ? reconciliationApi.verify(id) : reconciliationApi.approve(id))
      showToast(successMessage, 'success')
      // the open drawer must reflect the new state; the list refreshes silently
      setDetailRefresh((k) => k + 1)
      fetch({ page: workspace.page, size: workspace.size }, false)
    } catch (err: any) {
      showToast(err?.detail || `Failed to ${action} reconciliation`, 'error')
      // The transition failed — the drawer's copy may be stale (e.g. the
      // record was verified in another tab and the backend rejected this
      // one). Refetch so the drawer shows the true server state, not the
      // state the user's stale view claimed.
      setDetailRefresh((k) => k + 1)
    } finally {
      setBusyId(null)
    }
  }

  const handleVerify = async (r: PaymentReconciliationResponse) =>
    runTransition(r.id, 'verify', 'Reconciliation verified')
  const handleApprove = async (r: PaymentReconciliationResponse) =>
    runTransition(r.id, 'approve', 'Reconciliation approved')

  // ── detail inspector (URL-backed selection) ──
  const [detailId, setDetailId] = useState<number | null>(null)
  const detailOpen = detailId !== null

  const openDetail = (r: PaymentReconciliationResponse) => {
    const url = new URL(window.location.href)
    url.searchParams.set('rec', String(r.id))
    window.history.pushState(null, '', url)
    setDetailId(r.id)
  }
  const closeDetail = () => {
    const url = new URL(window.location.href)
    url.searchParams.delete('rec')
    window.history.replaceState(null, '', url)
    setDetailId(null)
  }

  // Restore the deep-linked selection on mount, and follow browser
  // back/forward between reconciliations (the P9 workspace contract).
  useEffect(() => {
    const syncFromUrl = () => {
      const rec = new URLSearchParams(window.location.search).get('rec')
      setDetailId(rec && /^\d+$/.test(rec) ? Number(rec) : null)
    }
    syncFromUrl()
    window.addEventListener('popstate', syncFromUrl)
    return () => window.removeEventListener('popstate', syncFromUrl)
  }, [])

  const currentKey = detailId ?? undefined

  return (
    <div className="space-y-4">
      <DataWorkspace
        workspace={workspace}
        title="Reconciliation"
        description={
          total > 0
            ? `${total.toLocaleString('en-KE')} reconciliation${total !== 1 ? 's' : ''} — verify and approve against the ledger.`
            : 'Verify and approve financial reconciliations against the ledger.'
        }
        columns={RECONCILIATION_COLUMNS}
        keyExtractor={(r) => r.id}
        data={data}
        total={total}
        pages={pages}
        loading={loading}
        error={error}
        onRetry={() => fetch({ page: workspace.page, size: workspace.size }, true)}
        onRefresh={() => fetch({ page: workspace.page, size: workspace.size }, false)}
        mode="server"
        filterPlaceholder="Search notes or #id…"
        onRowClick={openDetail}
        currentKey={currentKey}
        toolbarActions={
          <Button onClick={() => setShowModal(true)}>
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            New Reconciliation
          </Button>
        }
        empty={{
          title: 'No reconciliations yet',
          description: 'Create a reconciliation to start matching ledger records against expected totals.',
          actionLabel: 'New Reconciliation',
          onAction: () => setShowModal(true),
        }}
      />

      <ReconciliationDetail
        open={detailOpen}
        reconciliationId={detailId}
        onClose={closeDetail}
        refreshKey={detailRefresh}
        onVerify={handleVerify}
        onApprove={handleApprove}
        busy={busyId !== null}
      />

      <Modal
        open={showModal}
        onClose={() => setShowModal(false)}
        title="New Reconciliation"
        footer={
          <div className="flex gap-2 justify-end">
            <Button variant="outline" onClick={() => setShowModal(false)}>Cancel</Button>
            <Button onClick={handleCreate} loading={creating}>Create</Button>
          </div>
        }
      >
        <div className="space-y-4">
          <Input
            label="Date"
            type="date"
            value={form.reconciliation_date}
            onChange={(e: any) => setForm({ ...form, reconciliation_date: e.target.value })}
            required
          />
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Total Amount (cents)"
              type="number"
              value={form.total_amount}
              onChange={(e: any) => setForm({ ...form, total_amount: e.target.value })}
            />
            <Input
              label="Total Count"
              type="number"
              value={form.total_count}
              onChange={(e: any) => setForm({ ...form, total_count: e.target.value })}
            />
          </div>
          <Input
            label="Notes"
            value={form.notes}
            onChange={(e: any) => setForm({ ...form, notes: e.target.value })}
            placeholder="Optional notes"
          />
        </div>
      </Modal>
    </div>
  )
}

// Server mode: the rail may only offer filters the backend can honor
// (status facet, reconciliation-date range, notes search). The remaining
// columns keep their display types but opt out of the filter rail via
// `filterable: false` (P13) — never a chip that silently does nothing.
const RECONCILIATION_COLUMNS: Column<PaymentReconciliationResponse>[] = [
  { key: 'id', header: 'ID', type: 'numeric', filterable: false, render: (r) => `#${r.id}` },
  {
    key: 'reconciliation_date',
    header: 'Date',
    type: 'date',
    render: (r) => formatDate(r.reconciliation_date),
  },
  {
    key: 'total_amount',
    header: 'Total',
    type: 'amount',
    currency: 'KES',
    filterable: false,
    render: (r) => formatKes(r.total_amount),
  },
  { key: 'total_count', header: 'Count', type: 'numeric', filterable: false },
  {
    key: 'items',
    header: 'Items',
    type: 'numeric',
    filterable: false,
    render: (r) => {
      const flagged = r.items.filter((i) => i.status !== 'matched').length
      return (
        <span className="inline-flex items-center gap-1.5">
          {r.items.length}
          {flagged > 0 && (
            <span
              className="rounded-full bg-[var(--color-warning)]/10 px-1.5 text-[10px] font-semibold text-[var(--color-warning)]"
              title={`${flagged} item${flagged === 1 ? '' : 's'} unmatched or discrepant`}
            >
              {flagged} flagged
            </span>
          )}
        </span>
      )
    },
  },
  {
    key: 'difference',
    header: 'Difference',
    type: 'amount',
    currency: 'KES',
    filterable: false,
    accessor: (r) => r.items.reduce((sum, item) => sum + item.difference, 0),
    render: (r) => {
      const diff = r.items.reduce((sum, item) => sum + item.difference, 0)
      return (
        <span
          className={
            diff !== 0
              ? 'font-semibold text-[var(--color-danger)]'
              : 'text-[var(--color-success-dark)]'
          }
        >
          {diff >= 0 ? '+' : ''}
          {formatKes(Math.abs(diff))}
        </span>
      )
    },
  },
  {
    key: 'status',
    header: 'Status',
    type: 'status',
    render: (r) => (
      <Badge variant={statusBadge[r.status] || 'neutral'}>
        {r.status.charAt(0).toUpperCase() + r.status.slice(1)}
      </Badge>
    ),
  },
  {
    key: 'notes',
    header: 'Notes',
    type: 'text',
    render: (r) => r.notes || '-',
    hideOnMobile: true,
  },
]

export default ReconciliationPage
