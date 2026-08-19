import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../api/auth/auth-context'
import { analyticsApi } from '../../api/analytics/analytics-api'
import { financeAnalyticsApi } from '../../api/analytics/finance-analytics-api'
import type { AnalyticsOverview, FinanceOverview, FeeTypeCollection } from '../../api/analytics/types'
import { ErrorState, PageHeader, Skeleton } from '../../components/ui'
import { formatCurrency, cn } from '../../lib/utils'

export function AccountantDashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null)
  const [financeOverview, setFinanceOverview] = useState<FinanceOverview | null>(null)
  const [feeTypeCollections, setFeeTypeCollections] = useState<FeeTypeCollection[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  useEffect(() => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)
    Promise.all([
      analyticsApi.getOverview(),
      financeAnalyticsApi.getOverview().catch(() => null),
      financeAnalyticsApi.getFeeTypeCollection().catch(() => [] as FeeTypeCollection[]),
    ])
      .then(([ov, fin, ftc]) => {
        if (fetchId === fetchIdRef.current) { setOverview(ov); setFinanceOverview(fin); setFeeTypeCollections(ftc) }
      })
      .catch((err: any) => { if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load dashboard') })
      .finally(() => { if (fetchId === fetchIdRef.current) setLoading(false) })
  }, [])

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="space-y-2"><Skeleton className="h-4 w-24" /><Skeleton className="h-7 w-56" /><Skeleton className="h-3 w-80" /></div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-20 rounded-xl" />)}</div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4"><Skeleton className="h-48 rounded-xl lg:col-span-2" /><Skeleton className="h-48 rounded-xl" /></div>
      </div>
    )
  }

  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />
  if (!overview) return <ErrorState message="Unable to load dashboard data." />

  const collectionPct = financeOverview?.collection_percentage ?? overview.collection_percentage ?? 0
  const totalOutstanding = financeOverview?.total_outstanding ?? overview.total_outstanding ?? 0
  const totalCollected = financeOverview?.total_collected ?? overview.total_collected ?? 0

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <PageHeader
          eyebrow="Finance"
          title={`Good ${new Date().getHours() < 12 ? 'morning' : new Date().getHours() < 17 ? 'afternoon' : 'evening'}, ${user?.display_name || 'Accountant'}`}
          subtitle={`${overview.total_students} students · ${formatCurrency(totalCollected)} collected of ${formatCurrency(totalCollected + totalOutstanding)} total`}
          compact
        />
        <div className="flex items-center gap-2 flex-shrink-0">
          <button onClick={() => navigate('/fees/payments')} className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--color-brand-accent)] px-3 py-1.5 text-xs font-medium text-white hover:bg-[var(--color-brand-accent-hover)] motion-safe:transition-colors">Payments</button>
          <button onClick={() => navigate('/reports')} className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/30 hover:text-[var(--color-brand-accent)] motion-safe:transition-colors">Reports</button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Collected', value: formatCurrency(totalCollected), accent: 'text-[var(--color-success)]' },
          { label: 'Outstanding', value: formatCurrency(totalOutstanding), accent: totalOutstanding > 0 ? 'text-[var(--color-warning)]' : undefined },
          { label: 'Collection Rate', value: `${collectionPct}%`, accent: collectionPct >= 80 ? 'text-[var(--color-success)]' : 'text-[var(--color-warning)]' },
          { label: 'Outstanding Students', value: financeOverview?.students_with_outstanding ?? overview.unpaid_count, accent: 'text-[var(--color-danger)]' },
        ].map((m) => (
          <div key={m.label} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3.5">
            <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-text-tertiary)]">{m.label}</p>
            <p className={cn('mt-1.5 text-xl font-bold tabular-nums leading-none', m.accent || 'text-[var(--color-text-primary)]')}>{m.value}</p>
          </div>
        ))}
      </div>

      {/* Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Fee Type Collection */}
        <div className="lg:col-span-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <h2 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">Fee Type Collection</h2>
          {feeTypeCollections.length > 0 ? (
            <div className="space-y-2">
              {feeTypeCollections.slice(0, 6).map((ftc) => (
                <div key={ftc.fee_type_id} className="p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
                  <div className="flex items-center justify-between mb-1.5">
                    <p className="text-xs font-semibold text-[var(--color-text-primary)]">{ftc.fee_type_name}</p>
                    <span className={cn('text-[11px] font-semibold', ftc.collection_percentage >= 80 ? 'text-[var(--color-success)]' : 'text-[var(--color-warning)]')}>{ftc.collection_percentage}%</span>
                  </div>
                  <div className="h-1 rounded-full bg-[var(--color-border)] overflow-hidden">
                    <div className={cn('h-full rounded-full', ftc.collection_percentage >= 80 ? 'bg-[var(--color-success)]' : ftc.collection_percentage >= 50 ? 'bg-[var(--color-warning)]' : 'bg-[var(--color-danger)]')} style={{ width: `${Math.min(ftc.collection_percentage, 100)}%` }} />
                  </div>
                  <div className="flex justify-between mt-1">
                    <p className="text-[10px] text-[var(--color-text-tertiary)]">{formatCurrency(ftc.total_collected)} collected</p>
                    <p className="text-[10px] text-[var(--color-text-tertiary)]">{formatCurrency(ftc.outstanding)} outstanding</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="py-6 text-center">
              <p className="text-xs text-[var(--color-text-tertiary)]">No fee type data available.</p>
              <button onClick={() => navigate('/fees/structures')} className="text-xs text-[var(--color-brand-accent)] hover:underline mt-1">View fee structures →</button>
            </div>
          )}
        </div>

        {/* Quick Actions */}
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <h2 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">Quick Actions</h2>
          <div className="space-y-1.5">
            {[
              { label: 'Record Payment', desc: 'Enter a new fee payment', route: '/fees/payments', icon: 'M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2z' },
              { label: 'View Fee Dues', desc: 'Track outstanding fee dues', route: '/fees/dues', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2' },
              { label: 'Financial Summary', desc: 'View class-level summaries', route: '/fees/summary', icon: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6' },
              { label: 'Collection Report', desc: 'Generate fee reports', route: '/reports/fees/collection', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10' },
              { label: 'My Profile', desc: 'View your account details', route: '/profile', icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z' },
            ].map((a) => (
              <button key={a.route} onClick={() => navigate(a.route)} className="w-full flex items-center gap-3 p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-left motion-safe:transition-colors motion-safe:duration-[var(--motion-fast)] hover:border-[var(--color-brand-accent)]/30">
                <svg className="h-4 w-4 text-[var(--color-text-tertiary)] flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={a.icon} /></svg>
                <div className="min-w-0">
                  <p className="text-xs font-medium text-[var(--color-text-primary)]">{a.label}</p>
                  <p className="text-[11px] text-[var(--color-text-tertiary)]">{a.desc}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Payment Status Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {[
          { label: 'Fully Paid', value: financeOverview?.fully_paid_students ?? 0, color: 'text-[var(--color-success)]', bg: 'bg-[var(--color-success)]/5', icon: 'M5 13l4 4L19 7' },
          { label: 'Partially Paid', value: financeOverview?.partially_paid_students ?? overview.partially_paid_count ?? 0, color: 'text-[var(--color-warning)]', bg: 'bg-[var(--color-warning)]/5', icon: 'M13 16h-1v-4h-1m1-4h.01' },
          { label: 'Unpaid', value: financeOverview?.unpaid_students ?? overview.unpaid_count ?? 0, color: 'text-[var(--color-danger)]', bg: 'bg-[var(--color-danger)]/5', icon: 'M12 9v2m0 4h.01' },
        ].map((s) => (
          <div key={s.label} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
            <div className="flex items-center gap-3">
              <div className={cn('flex items-center justify-center h-9 w-9 rounded-lg', s.bg)}>
                <svg className={cn('h-4 w-4', s.color)} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={s.icon} /></svg>
              </div>
              <div>
                <p className="text-[11px] text-[var(--color-text-tertiary)]">{s.label}</p>
                <p className={cn('text-lg font-bold tabular-nums', s.color)}>{s.value}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
