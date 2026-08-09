import { useCallback, useEffect, useRef, useState } from 'react'
import { WorkspaceInspector } from '../../components/data-workspace'
import { Badge, Button } from '../../components/ui'
import {
  reconciliationApi,
  type PaymentReconciliationResponse,
  type ReconciliationItemResponse,
} from '../../api/school-finance/school-finance-api'
import { cn, formatDate } from '../../lib/utils'

/**
 * P13 — Reconciliation detail. The inspection half of the reconciliation
 * workflow (find → inspect → act → resolve): a right-side inspector that
 * lists every ledger item the reconciliation covers with its
 * matched / unmatched / discrepancy state and per-item difference — the
 * "identify unmatched / duplicate-looking transactions" step, driven by the
 * backend's `ReconciliationItem.status` (never a frontend re-computation).
 * Verify / Approve live in the footer and flow through the page (audited
 * backend transitions), never here.
 */

function formatKes(amount: number) {
  return (amount / 100).toLocaleString('en-KE', {
    style: 'currency',
    currency: 'KES',
    minimumFractionDigits: 0,
  })
}

const recStatusBadge: Record<string, 'neutral' | 'info' | 'success' | 'danger'> = {
  draft: 'neutral',
  submitted: 'info',
  verified: 'info',
  approved: 'success',
  rejected: 'danger',
}

const itemStatusBadge: Record<string, 'success' | 'warning' | 'danger'> = {
  matched: 'success',
  discrepancy: 'warning',
  unmatched: 'danger',
}

function ItemRow({ item }: { item: ReconciliationItemResponse }) {
  const tone =
    item.difference === 0
      ? 'text-[var(--color-success-dark)]'
      : 'text-[var(--color-danger)]'
  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-[var(--color-text-primary)]">
              Payment #{item.payment_id}
            </span>
            <Badge variant={itemStatusBadge[item.status] ?? 'neutral'} size="sm">
              {item.status}
            </Badge>
          </div>
          <p className="mt-1 text-xs text-[var(--color-text-tertiary)] leading-relaxed">
            Expected {formatKes(item.expected_amount)} · Actual {formatKes(item.actual_amount)}
            {item.notes ? ` · ${item.notes}` : ''}
          </p>
        </div>
        <span className={cn('text-sm font-semibold tabular-nums', tone)}>
          {/* sign manually, magnitude via Math.abs — currency formatting
              already renders negatives with their own sign, so passing the
              raw value here would double-sign it */}
          {item.difference >= 0 ? '+' : '-'}
          {formatKes(Math.abs(item.difference))}
        </span>
      </div>
    </div>
  )
}

interface ReconciliationDetailProps {
  open: boolean
  reconciliationId: number | null
  onClose: () => void
  /** Bump after a verify/approve mutation so the drawer refetches. */
  refreshKey?: number
  /** Page-owned mutations (audited backend transitions + toasts). */
  onVerify: (r: PaymentReconciliationResponse) => Promise<void>
  onApprove: (r: PaymentReconciliationResponse) => Promise<void>
  busy?: boolean
}

export function ReconciliationDetail({
  open,
  reconciliationId,
  onClose,
  refreshKey = 0,
  onVerify,
  onApprove,
  busy = false,
}: ReconciliationDetailProps) {
  const [data, setData] = useState<PaymentReconciliationResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  const load = useCallback(async () => {
    if (reconciliationId === null) return
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)
    try {
      const d = await reconciliationApi.get(reconciliationId)
      if (fetchId === fetchIdRef.current) setData(d)
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) {
        setError(err?.detail || 'Failed to load reconciliation')
      }
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [reconciliationId])

  useEffect(() => {
    if (!open) return
    setData(null)
    load()
  }, [open, load, refreshKey])

  const flagged = (data?.items ?? []).filter((i) => i.status !== 'matched').length
  const status = data?.status ?? ''

  return (
    <WorkspaceInspector
      open={open}
      onClose={onClose}
      title="Reconciliation detail"
      width="min(34rem, 100vw)"
      header={
        data ? (
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-[var(--color-text-primary)]">
              #{data.id}
            </span>
            <Badge variant={recStatusBadge[data.status] ?? 'neutral'} size="sm">
              {data.status}
            </Badge>
            <span className="text-xs text-[var(--color-text-tertiary)]">
              {formatDate(data.reconciliation_date)}
            </span>
          </div>
        ) : null
      }
      footer={
        data ? (
          <div className="flex items-center gap-2">
            {(status === 'draft' || status === 'submitted') && (
              <Button onClick={() => onVerify(data)} loading={busy}>
                Verify
              </Button>
            )}
            {status === 'verified' && (
              <Button onClick={() => onApprove(data)} loading={busy}>
                Approve
              </Button>
            )}
            <Button variant="outline" onClick={onClose}>
              Close
            </Button>
          </div>
        ) : null
      }
      loading={loading}
      error={error}
      onRetry={load}
      emptyMessage="No reconciliation to preview."
    >
      {data && (
        <div className="space-y-4">
          {/* Summary */}
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
              <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-text-tertiary)]">
                Total
              </p>
              <p className="mt-1 text-base font-bold tabular-nums text-[var(--color-text-primary)]">
                {formatKes(data.total_amount)}
              </p>
            </div>
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
              <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-text-tertiary)]">
                Items
              </p>
              <p className="mt-1 text-base font-bold tabular-nums text-[var(--color-text-primary)]">
                {data.total_count}
              </p>
            </div>
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
              <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-text-tertiary)]">
                Flagged
              </p>
              <p
                className={cn(
                  'mt-1 text-base font-bold tabular-nums',
                  flagged > 0
                    ? 'text-[var(--color-warning)]'
                    : 'text-[var(--color-success-dark)]'
                )}
              >
                {flagged}
              </p>
            </div>
          </div>

          {data.notes && (
            <p className="text-xs text-[var(--color-text-tertiary)] leading-relaxed">
              {data.notes}
            </p>
          )}

          {/* Items */}
          <div>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">
              Ledger items
            </p>
            {data.items.length === 0 ? (
              <p className="rounded-xl border border-dashed border-[var(--color-border)] p-4 text-center text-xs text-[var(--color-text-muted)]">
                No items recorded for this reconciliation.
              </p>
            ) : (
              <div className="space-y-2">
                {data.items.map((item) => (
                  <ItemRow key={item.id} item={item} />
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </WorkspaceInspector>
  )
}
