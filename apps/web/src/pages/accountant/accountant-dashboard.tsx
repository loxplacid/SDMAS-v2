import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../api/auth/auth-context'
import { analyticsApi } from '../../api/analytics/analytics-api'
import { financeAnalyticsApi } from '../../api/analytics/finance-analytics-api'
import type { AnalyticsOverview, FinanceOverview, FeeTypeCollection } from '../../api/analytics/types'
import { Loading, ErrorState, AnimatedCount } from '../../components/ui'
import { formatCurrency } from '../../lib/utils'

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
        if (fetchId === fetchIdRef.current) {
          setOverview(ov)
          setFinanceOverview(fin)
          setFeeTypeCollections(ftc)
        }
      })
      .catch((err: any) => {
        if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load dashboard')
      })
      .finally(() => {
        if (fetchId === fetchIdRef.current) setLoading(false)
      })
  }, [])

  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'

  if (loading) {
    return (
      <div className="space-y-8 animate-fade-in">
        <div className="space-y-3">
          <div className="h-8 w-72 rounded-lg bg-[var(--color-border)] animate-skeleton" />
          <div className="h-5 w-96 rounded bg-[var(--color-border)] animate-skeleton" />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 rounded-2xl bg-[var(--color-border)] animate-skeleton" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 h-64 rounded-2xl bg-[var(--color-border)] animate-skeleton" />
          <div className="h-64 rounded-2xl bg-[var(--color-border)] animate-skeleton" />
        </div>
      </div>
    )
  }

  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />
  if (!overview) return <ErrorState message="Unable to load dashboard data." />

  const collectionPct = financeOverview?.collection_percentage ?? overview.collection_percentage ?? 0
  const isCollectionGood = collectionPct >= 80
  const totalOutstanding = financeOverview?.total_outstanding ?? overview.total_outstanding ?? 0
  const totalCollected = financeOverview?.total_collected ?? overview.total_collected ?? 0

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-blue-800 via-blue-700 to-teal-700 p-8 lg:p-10">
        <div className="absolute inset-0 opacity-[0.04]"
          style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.3) 1px, transparent 1px)', backgroundSize: '40px 40px' }}
        />
        <div className="relative">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            <div className="space-y-2">
              <p className="text-sm font-medium text-blue-200 tracking-wide">
                {greeting}, {user?.display_name || user?.username || 'Accountant'}
              </p>
              <h1 className="text-3xl lg:text-4xl font-extrabold text-white leading-tight tracking-tight">
                Financial overview
              </h1>
              <p className="text-white/60 text-base max-w-xl leading-relaxed">
                {overview.total_students} student{overview.total_students !== 1 ? 's' : ''} enrolled.
                {financeOverview
                  ? ` ${formatCurrency(totalCollected)} collected of ${formatCurrency(totalCollected + totalOutstanding)} total fees.`
                  : ` Fee data available from overview.`}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => navigate('/fees/payments')}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white text-blue-700 text-sm font-semibold hover:bg-blue-50 transition-colors shadow-lg"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
                Payments
              </button>
              <button
                onClick={() => navigate('/reports')}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white/15 text-white text-sm font-medium hover:bg-white/25 transition-colors"
              >
                Reports
              </button>
            </div>
          </div>

          {/* KPI Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-8">
            {[
              { label: 'Total Collected', value: totalCollected, isCurrency: true, accent: 'text-blue-200' },
              { label: 'Outstanding', value: totalOutstanding, isCurrency: true, accent: 'text-amber-300' },
              { label: 'Collection Rate', value: collectionPct, suffix: '%', accent: 'text-teal-300' },
              { label: 'Outstanding Students', value: financeOverview?.students_with_outstanding ?? overview.unpaid_count, accent: 'text-rose-300' },
            ].map((m, i) => (
              <div
                key={m.label}
                className="bg-white/5 rounded-xl p-4 border border-white/[0.06] animate-fade-in-up"
                style={{ animationDelay: `${i * 80}ms`, animationFillMode: 'both' }}
              >
                <p className="text-xs text-white/40 font-medium tracking-wide uppercase">{m.label}</p>
                <p className={`text-2xl font-bold text-white mt-1 ${m.accent} tabular-nums`}>
                  {m.isCurrency
                    ? formatCurrency(typeof m.value === 'number' ? m.value : 0)
                    : <><AnimatedCount value={typeof m.value === 'number' ? m.value : 0} duration={1000 + i * 200} />{m.suffix || ''}</>
                  }
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Fee Type Breakdown */}
        <div className="lg:col-span-2 bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-6">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-base font-semibold text-[var(--color-text-primary)]">Fee Type Collection</h2>
              <p className="text-sm text-[var(--color-text-tertiary)] mt-0.5">Breakdown by fee category</p>
            </div>
          </div>

          {feeTypeCollections.length > 0 ? (
            <div className="space-y-3">
              {feeTypeCollections.slice(0, 8).map((ftc, i) => (
                <div
                  key={ftc.fee_type_id}
                  className="p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)] animate-fade-in-up"
                  style={{ animationDelay: `${i * 50}ms`, animationFillMode: 'both' }}
                >
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm font-semibold text-[var(--color-text-primary)]">{ftc.fee_type_name}</p>
                    <span className={`text-xs font-semibold ${ftc.collection_percentage >= 80 ? 'text-[var(--color-success)]' : 'text-[var(--color-warning)]'}`}>
                      {ftc.collection_percentage}%
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-[var(--color-border)] overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${ftc.collection_percentage >= 80 ? 'bg-[var(--color-success)]' : ftc.collection_percentage >= 50 ? 'bg-[var(--color-warning)]' : 'bg-[var(--color-danger)]'}`}
                      style={{ width: `${Math.min(ftc.collection_percentage, 100)}%` }}
                    />
                  </div>
                  <div className="flex justify-between mt-1.5">
                    <p className="text-xs text-[var(--color-text-tertiary)]">{formatCurrency(ftc.total_collected)} collected</p>
                    <p className="text-xs text-[var(--color-text-tertiary)]">{formatCurrency(ftc.outstanding)} outstanding</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8">
              <p className="text-sm text-[var(--color-text-tertiary)]">No fee type data available.</p>
              <button onClick={() => navigate('/fees/structures')} className="text-sm text-[var(--color-brand-accent)] hover:underline mt-2">
                View fee structures &rarr;
              </button>
            </div>
          )}
        </div>

        {/* Quick Actions & Summary */}
        <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-6">
          <h2 className="text-base font-semibold text-[var(--color-text-primary)] mb-5">Quick Actions</h2>
          <div className="space-y-3">
            <button
              onClick={() => navigate('/fees/payments')}
              className="w-full flex items-center gap-3 p-4 rounded-xl bg-[var(--color-brand-accent)]/5 border border-[var(--color-brand-accent)]/15 text-left hover:shadow-sm hover:-translate-y-0.5 transition-all duration-[var(--motion-fast)] motion-reduce:transition-none motion-reduce:hover:translate-y-0"
            >
              <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-brand-accent)]/10">
                <svg className="h-4.5 w-4.5 text-[var(--color-brand-accent)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2z" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-[var(--color-text-primary)]">Record Payment</p>
                <p className="text-xs text-[var(--color-text-tertiary)]">Enter a new fee payment</p>
              </div>
            </button>

            <button
              onClick={() => navigate('/fees/dues')}
              className="w-full flex items-center gap-3 p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)] text-left hover:shadow-sm hover:-translate-y-0.5 transition-all duration-[var(--motion-fast)] motion-reduce:transition-none motion-reduce:hover:translate-y-0"
            >
              <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-bg)]">
                <svg className="h-4.5 w-4.5 text-[var(--color-text-secondary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-[var(--color-text-primary)]">View Fee Dues</p>
                <p className="text-xs text-[var(--color-text-tertiary)]">Track outstanding fee dues</p>
              </div>
            </button>

            <button
              onClick={() => navigate('/fees/summary')}
              className="w-full flex items-center gap-3 p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)] text-left hover:shadow-sm hover:-translate-y-0.5 transition-all duration-[var(--motion-fast)] motion-reduce:transition-none motion-reduce:hover:translate-y-0"
            >
              <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-bg)]">
                <svg className="h-4.5 w-4.5 text-[var(--color-text-secondary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-[var(--color-text-primary)]">Financial Summary</p>
                <p className="text-xs text-[var(--color-text-tertiary)]">View class-level fee summaries</p>
              </div>
            </button>

            <button
              onClick={() => navigate('/reports/fees/collection')}
              className="w-full flex items-center gap-3 p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)] text-left hover:shadow-sm hover:-translate-y-0.5 transition-all duration-[var(--motion-fast)] motion-reduce:transition-none motion-reduce:hover:translate-y-0"
            >
              <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-bg)]">
                <svg className="h-4.5 w-4.5 text-[var(--color-text-secondary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-[var(--color-text-primary)]">Collection Report</p>
                <p className="text-xs text-[var(--color-text-tertiary)]">Generate fee collection reports</p>
              </div>
            </button>

            <button
              onClick={() => navigate('/profile')}
              className="w-full flex items-center gap-3 p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)] text-left hover:shadow-sm hover:-translate-y-0.5 transition-all duration-[var(--motion-fast)] motion-reduce:transition-none motion-reduce:hover:translate-y-0"
            >
              <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-bg)]">
                <svg className="h-4.5 w-4.5 text-[var(--color-text-secondary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-[var(--color-text-primary)]">My Profile</p>
                <p className="text-xs text-[var(--color-text-tertiary)]">View your account details</p>
              </div>
            </button>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {[
          {
            label: 'Fully Paid',
            value: financeOverview?.fully_paid_students ?? 0,
            color: 'text-[var(--color-success)]',
            bg: 'bg-[var(--color-success)]/5',
            icon: 'M5 13l4 4L19 7',
          },
          {
            label: 'Partially Paid',
            value: financeOverview?.partially_paid_students ?? overview.partially_paid_count ?? 0,
            color: 'text-[var(--color-warning)]',
            bg: 'bg-[var(--color-warning)]/5',
            icon: 'M13 16h-1v-4h-1m1-4h.01',
          },
          {
            label: 'Unpaid',
            value: financeOverview?.unpaid_students ?? overview.unpaid_count ?? 0,
            color: 'text-[var(--color-danger)]',
            bg: 'bg-[var(--color-danger)]/5',
            icon: 'M12 9v2m0 4h.01',
          },
        ].map((s, i) => (
          <div
            key={s.label}
            className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-5 animate-fade-in-up"
            style={{ animationDelay: `${i * 80}ms`, animationFillMode: 'both' }}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`flex items-center justify-center h-10 w-10 rounded-xl ${s.bg}`}>
                  <svg className={`h-5 w-5 ${s.color}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={s.icon} />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-medium text-[var(--color-text-secondary)]">{s.label}</p>
                  <p className={`text-xl font-bold ${s.color}`}>
                    <AnimatedCount value={typeof s.value === 'number' ? s.value : 0} duration={800} />
                  </p>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
