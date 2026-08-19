import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../api/auth/auth-context'
import {
  casesApi,
  type CasePriority,
  type CaseSourceType,
} from '../../api/cases/cases-api'
import {
  financialExceptionApi,
  type FinancialException,
  type FinancialExceptionCategory,
  type FinancialExceptionSummary,
} from '../../api/school-finance/school-finance-api'
import { Badge, Button, Card, Skeleton } from '../../components/ui'
import { useToast } from '../../components/ui/toast'
import { cn, formatDateTime } from '../../lib/utils'

/**
 * P13 — Financial Exceptions. The operational surface for the finance
 * lifecycle (TRANSACTION → VALIDATION → RECONCILIATION → EXCEPTION →
 * RESOLUTION → AUDIT): every finding is computed deterministically from
 * real records by the backend, and promoting one opens an operational case
 * through the existing P8/P11 case lifecycle (assignment, SLA, resolution,
 * immutable events — never a second exception system).
 */

const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low'] as const

const severityBadge: Record<string, 'danger' | 'warning' | 'info' | 'success'> = {
  critical: 'danger',
  high: 'danger',
  medium: 'warning',
  low: 'info',
}

const severityDot: Record<string, string> = {
  critical: 'bg-[var(--color-danger)]',
  high: 'bg-[var(--color-danger)]',
  medium: 'bg-[var(--color-warning)]',
  low: 'bg-[var(--color-info)]',
}

const severityTint: Record<string, string> = {
  critical: 'text-[var(--color-danger)] bg-[var(--color-danger)]/10',
  high: 'text-[var(--color-danger)] bg-[var(--color-danger)]/10',
  medium: 'text-[var(--color-warning)] bg-[var(--color-warning)]/10',
  low: 'text-[var(--color-info)] bg-[var(--color-info)]/10',
}

const CATEGORY_LABELS: Record<FinancialExceptionCategory, string> = {
  reconciliation: 'Reconciliation',
  receipts: 'Receipts',
  ledger: 'Ledger',
  duplicates: 'Duplicates',
}

// P11 — linked case status badge colors (a resolved/closed case is done).
const caseStatusBadge: Record<string, 'success' | 'info' | 'warning'> = {
  resolved: 'success',
  closed: 'success',
  in_progress: 'info',
  waiting: 'info',
  acknowledged: 'warning',
  open: 'warning',
}

function formatCurrency(amount: number) {
  return (amount / 100).toLocaleString('en-US', { style: 'currency', currency: 'NGN', minimumFractionDigits: 0 })
}

function EvidenceRow({ finding }: { finding: FinancialException }) {
  const e = finding.evidence
  const parts: string[] = []
  if (finding.category === 'reconciliation') {
    if (e.expected_amount != null && e.actual_amount != null) {
      parts.push(`Expected ${formatCurrency(Number(e.expected_amount))}`)
      parts.push(`Actual ${formatCurrency(Number(e.actual_amount))}`)
    }
    if (e.difference != null && Number(e.difference) !== 0) {
      parts.push(`Difference ${formatCurrency(Number(e.difference))}`)
    }
    if (finding.reconciliation_status) {
      parts.push(`Reconciliation ${finding.reconciliation_status}`)
    }
  } else if (finding.category === 'duplicates') {
    const peers = Array.isArray(e.peer_payment_ids) ? (e.peer_payment_ids as number[]) : []
    if (peers.length > 0) parts.push(`Peers: #${peers.slice(0, 5).join(', #')}`)
    if (e.payment_date) parts.push(`Date ${String(e.payment_date)}`)
    if (e.receipt_number) parts.push(`Receipt ${String(e.receipt_number)}`)
  } else {
    if (e.payment_method) parts.push(String(e.payment_method))
    if (e.payment_date) parts.push(String(e.payment_date))
  }
  if (parts.length === 0) return null
  return (
    <p className="text-xs text-[var(--color-text-secondary)] mt-1.5 leading-relaxed">
      {parts.join(' · ')}
    </p>
  )
}

// ── Exception card ────────────────────────────────────────────────────

function ExceptionCard({
  finding,
  index,
  canCreateCase,
  creating,
  onCreateCase,
}: {
  finding: FinancialException
  index: number
  canCreateCase: boolean
  creating: boolean
  onCreateCase: (f: FinancialException) => void
}) {
  const navigate = useNavigate()
  const caseTone = finding.linked_case
    ? caseStatusBadge[finding.linked_case.status] ?? 'info'
    : 'info'

  return (
    <div
      className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 animate-fade-in-up motion-safe:transition-all motion-safe:duration-[var(--motion-fast)] hover:shadow-sm"
      style={{ animationDelay: `${Math.min(index, 8) * 40}ms`, animationFillMode: 'both' }}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 min-w-0">
          <span className={cn('mt-1.5 inline-block h-2 w-2 rounded-full flex-shrink-0', severityDot[finding.severity])} aria-hidden="true" />
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <p className="text-sm font-semibold text-[var(--color-text-primary)]">{finding.title}</p>
              <Badge variant={severityBadge[finding.severity]} size="sm">{finding.severity}</Badge>
              <Badge variant="neutral" size="sm">
                {CATEGORY_LABELS[finding.category as FinancialExceptionCategory] ?? finding.category}
              </Badge>
              {finding.linked_case && (
                <Badge variant={caseTone} size="sm">
                  Case {finding.linked_case.case_number}
                  {finding.linked_case.status !== 'open'
                    ? ` · ${finding.linked_case.status.replace('_', ' ')}`
                    : ''}
                </Badge>
              )}
            </div>
            <p className="text-xs text-[var(--color-text-tertiary)] mt-1 leading-relaxed">
              {finding.description}
            </p>
            <EvidenceRow finding={finding} />
            <p className="text-[11px] text-[var(--color-text-muted)] mt-1.5">
              {finding.student_name ? `Student · ${finding.student_name}` : `Student #${finding.student_id ?? '—'}`}
              {finding.payment_id ? ` · Payment #${finding.payment_id}` : ''}
              {finding.amount != null ? ` · ${formatCurrency(finding.amount)}` : ''}
              {finding.created_at ? ` · ${formatDateTime(finding.created_at)}` : ''}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {finding.student_id && (
            <button
              type="button"
              onClick={() => navigate(`/students/${finding.student_id}/360`)}
              className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/40 hover:text-[var(--color-brand-accent)] motion-safe:transition-colors"
            >
              Student
            </button>
          )}
          {finding.linked_case ? (
            <button
              type="button"
              onClick={() => navigate(`/cases/${finding.linked_case!.id}`)}
              className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/50 hover:text-[var(--color-brand-accent)] motion-safe:transition-colors"
            >
              Open case
            </button>
          ) : canCreateCase ? (
            <button
              type="button"
              disabled={creating}
              onClick={() => onCreateCase(finding)}
              className="rounded-lg bg-[var(--color-brand-accent)] px-2.5 py-1.5 text-xs font-medium text-white hover:bg-[var(--color-brand-accent-hover)] motion-safe:transition-colors disabled:opacity-50 disabled:pointer-events-none"
            >
              {creating ? 'Creating…' : 'Create case'}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  )
}

// ── Skeleton ──────────────────────────────────────────────────────────

function ExceptionsSkeleton() {
  return (
    <div className="space-y-6 animate-fade-in" aria-busy="true" aria-label="Loading financial exceptions">
      <div className="space-y-3">
        <Skeleton className="h-8 w-72" />
        <Skeleton className="h-4 w-96" />
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-20 rounded-xl" />
        ))}
      </div>
      <div className="space-y-2">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className="h-28 rounded-xl" />
        ))}
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────

export function FinancialExceptionsPage() {
  const { user } = useAuth()
  const { showToast } = useToast()
  const navigate = useNavigate()
  const role = (user?.role as string) || 'staff'
  const canCreateCase = ['admin', 'principal', 'staff'].includes(role)

  const [summary, setSummary] = useState<FinancialExceptionSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [categoryFilter, setCategoryFilter] = useState<string>('')
  const [creatingKey, setCreatingKey] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  const load = useCallback(async () => {
    const fetchId = ++fetchIdRef.current
    setError(null)
    try {
      const data = await financialExceptionApi.list({ page: 1, size: 100 })
      if (fetchId === fetchIdRef.current) setSummary(data)
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load financial exceptions')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  // P13 — promote an exception into an operational case (P8/P11 lifecycle).
  // The case references the underlying entity (payment / reconciliation
  // item) via source_type + source_id, so the ledger stays the source of
  // truth and a second exception system is never created.
  const handleCreateCase = async (finding: FinancialException) => {
    setCreatingKey(finding.key)
    try {
      const sourceId =
        finding.category === 'reconciliation'
          ? finding.reconciliation_item_id
          : finding.payment_id
      const sourceType: CaseSourceType = 'financial_exception'
      const c = await casesApi.create({
        title: finding.title,
        description: `${finding.description} (${finding.key})`,
        case_type: 'finance',
        priority: (finding.severity === 'critical' || finding.severity === 'high'
          ? finding.severity
          : 'medium') as CasePriority,
        source_type: sourceType,
        source_id: sourceId,
        student_id: finding.student_id,
      })
      showToast(`Case ${c.case_number} created for ${finding.title}`, 'success')
      navigate(`/cases/${c.id}`)
    } catch (err: any) {
      if (err?.status === 409) {
        // a case already exists for this exception — refresh to show it
        showToast('A case already exists for this exception', 'info')
        load()
      } else {
        showToast(err?.detail || 'Could not create case', 'error')
      }
    } finally {
      setCreatingKey(null)
    }
  }

  const items = (summary?.items ?? []).filter(
    (f) => !categoryFilter || f.category === categoryFilter
  )

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="space-y-1.5">
        <h1 className="text-2xl font-bold tracking-tight text-[var(--color-text-primary)]">
          Financial Exceptions
        </h1>
        <p className="text-sm text-[var(--color-text-tertiary)]">
          Deterministic anomalies computed from the ledger — reconcile, review and resolve via the work queue.
        </p>
      </div>

      {loading ? (
        <ExceptionsSkeleton />
      ) : error ? (
        <div className="flex flex-col items-center justify-center py-16 text-center animate-fade-in">
          <div className="h-12 w-12 rounded-xl bg-[var(--color-danger)]/10 flex items-center justify-center mb-4">
            <svg className="h-7 w-7 text-[var(--color-danger)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <h3 className="text-sm font-semibold text-[var(--color-danger-dark)]">{error}</h3>
          <Button variant="danger" className="mt-5" onClick={load}>Try Again</Button>
        </div>
      ) : summary && summary.total === 0 ? (
        <div className="rounded-xl border border-[var(--color-success)]/20 bg-[var(--color-success)]/5 p-8 text-center">
          <p className="text-sm font-semibold text-[var(--color-success-dark)]">No financial exceptions</p>
          <p className="text-xs text-[var(--color-success)]/70 mt-1">
            The ledger is clean — no reconciliation discrepancies, missing receipts, ledger gaps or duplicate-looking payments.
          </p>
        </div>
      ) : summary ? (
        <>
          {/* Severity overview */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {SEVERITY_ORDER.map((s) => (
              <div key={s} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className={cn('inline-block h-2 w-2 rounded-full', severityDot[s])} aria-hidden="true" />
                  <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-text-tertiary)]">{s}</p>
                </div>
                <p className={cn('text-2xl font-bold tabular-nums leading-none', severityTint[s])}>
                  {summary.by_severity[s] ?? 0}
                </p>
              </div>
            ))}
          </div>

          {/* Category breakdown */}
          {Object.keys(summary.by_category).length > 0 && (
            <div className="flex flex-wrap gap-2">
              {Object.entries(summary.by_category).map(([cat, count]) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setCategoryFilter(cat === categoryFilter ? '' : cat)}
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium motion-safe:transition-colors',
                    cat === categoryFilter
                      ? 'border-[var(--color-brand-accent)] bg-[var(--color-brand-accent)]/10 text-[var(--color-brand-accent)]'
                      : 'border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/40'
                  )}
                >
                  {CATEGORY_LABELS[cat as FinancialExceptionCategory] ?? cat}
                  <span className="tabular-nums">{count}</span>
                </button>
              ))}
            </div>
          )}

          {/* Findings */}
          {items.length === 0 ? (
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 text-center">
              <p className="text-sm font-medium text-[var(--color-text-secondary)]">
                No {categoryFilter ? CATEGORY_LABELS[categoryFilter as FinancialExceptionCategory]?.toLowerCase() : ''} exceptions for this view.
              </p>
            </div>
          ) : (
            <div className="space-y-2.5">
              {items.map((f, i) => (
                <ExceptionCard
                  key={f.key}
                  finding={f}
                  index={i}
                  canCreateCase={canCreateCase}
                  creating={creatingKey === f.key}
                  onCreateCase={handleCreateCase}
                />
              ))}
            </div>
          )}
        </>
      ) : null}
    </div>
  )
}

export default FinancialExceptionsPage
