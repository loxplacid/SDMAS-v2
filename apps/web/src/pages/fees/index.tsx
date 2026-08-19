import { useCallback, useEffect, useRef, useState } from 'react'
import { feeTypeApi } from '../../api/fees/fee-type-api'
import { feeDueApi } from '../../api/fees/fee-due-api'
import { paymentApi } from '../../api/fees/payment-api'
import { HubPage, HubSectionHeading } from '../../components/ui/hub-page'
import { Badge, Skeleton } from '../../components/ui'
import { formatDateTime, plural } from '../../lib/utils'

const feeLinks = [
  { label: 'Fee Types', description: 'Manage fee categories', route: '/fees/fee-types', icon: 'M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10' },
  { label: 'Fee Structures', description: 'Configure amounts by class and year', route: '/fees/structures', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01' },
  { label: 'Fee Dues', description: 'View and manage student fee dues', route: '/fees/dues', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
  { label: 'Payments', description: 'Record and view student payments', route: '/fees/payments', icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z' },
  { label: 'Financial Summary', description: 'View summaries by student or class', route: '/fees/summary', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
  { label: 'School Finance', description: 'Payment methods, schedules, receipts', route: '/school-finance', icon: 'M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z' },
]

export function FeesPage() {
  const [feeTypeCount, setFeeTypeCount] = useState(0)
  const [dueCount, setDueCount] = useState(0)
  const [paymentCount, setPaymentCount] = useState(0)
  const [recentPayments, setRecentPayments] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const fetchIdRef = useRef(0)

  const load = useCallback(async () => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    try {
      const [ftRes, dueRes, payRes] = await Promise.all([
        feeTypeApi.list({ page: 1, size: 1 }),
        feeDueApi.list({ page: 1, size: 1 }),
        paymentApi.list({ page: 1, size: 1 }),
      ])
      if (fetchId !== fetchIdRef.current) return
      setFeeTypeCount(ftRes.total)
      setDueCount(dueRes.total)
      setPaymentCount(payRes.total)

      // Fetch recent payments for the activity feed
      const recent = await paymentApi.list({ page: 1, size: 5 })
      if (fetchId === fetchIdRef.current) {
        setRecentPayments(recent.items)
      }
    } catch {
      // Silent — stats will show 0
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    return () => { fetchIdRef.current++ }
  }, [load])

  const stats = [
    { label: 'Fee Types', value: feeTypeCount, route: '/fees/fee-types' },
    { label: 'Fee Dues', value: dueCount, route: '/fees/dues' },
    { label: 'Payments', value: paymentCount, route: '/fees/payments', accent: 'text-[var(--color-success)]' },
  ]

  const recentSection = (
    <div>
      <HubSectionHeading title="Recent Payments" subtitle={plural(paymentCount, 'payment total')} />
      <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
        {loading ? (
          <div className="p-4 space-y-3">
            {Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-10 w-full" />)}
          </div>
        ) : recentPayments.length === 0 ? (
          <div className="p-6 text-center">
            <p className="text-xs text-[var(--color-text-tertiary)]">No payments recorded yet.</p>
          </div>
        ) : (
          <table className="min-w-full">
            <thead>
              <tr className="border-b border-[var(--color-divider)]">
                <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">Amount</th>
                <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">Method</th>
                <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">Status</th>
                <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-divider)]">
              {recentPayments.map((p: any) => (
                <tr key={p.id} className="hover:bg-[var(--color-surface-hover)] motion-safe:transition-colors">
                  <td className="px-4 py-2.5 text-sm font-medium text-[var(--color-text-primary)] tabular-nums">
                    ₹{(p.amount_inr / 100).toLocaleString()}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-[var(--color-text-secondary)] capitalize">
                    {p.payment_method?.replace(/_/g, ' ') || '-'}
                  </td>
                  <td className="px-4 py-2.5">
                    <Badge variant={p.status === 'completed' ? 'success' : p.status === 'pending' ? 'warning' : 'neutral'} size="sm">
                      {p.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-[var(--color-text-tertiary)]">
                    {formatDateTime(p.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )

  return (
    <HubPage
      eyebrow="Finance"
      title="Fees & Payments"
      subtitle="Manage fee types, structures, dues, and payment records"
      stats={stats}
      links={feeLinks}
      recentContent={recentSection}
      loading={loading}
    />
  )
}

export default FeesPage
