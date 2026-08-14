import { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { schoolFinanceDashboardApi, outstandingBalanceApi, financialExceptionApi, type SchoolFinanceDashboard, type TransactionLogResponse } from '../../api/school-finance/school-finance-api'
import { Card, PageHeader, Loading, ErrorState, Badge, Table, Button } from '../../components/ui'
import { formatDate } from '../../lib/utils'

function formatCurrency(amount: number) {
  return (amount / 100).toLocaleString('en-KE', { style: 'currency', currency: 'KES' })
}

export const SchoolFinanceDashboardPage: React.FC = () => {
  const [dashboard, setDashboard] = useState<SchoolFinanceDashboard | null>(null)
  const [topOutstanding, setTopOutstanding] = useState<{ student_name: string | null; class_name: string | null; outstanding: number; overdue_count: number }[]>([])
  const [exceptionCounts, setExceptionCounts] = useState<{ critical: number; high: number }>({ critical: 0, high: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  const fetchData = useCallback(async () => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)
    try {
      const [dash, outstanding, exceptions] = await Promise.all([
        schoolFinanceDashboardApi.getDashboard(),
        outstandingBalanceApi.getOutstanding({ size: 5 }),
        financialExceptionApi.list({ page: 1, size: 1 }),
      ])
      if (fetchId === fetchIdRef.current) {
        setDashboard(dash)
        setTopOutstanding(outstanding.items.map((i) => ({
          student_name: i.student_name,
          class_name: i.class_name,
          outstanding: i.outstanding,
          overdue_count: i.overdue_count,
        })))
        setExceptionCounts({
          critical: exceptions.by_severity.critical ?? 0,
          high: exceptions.by_severity.high ?? 0,
        })
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load dashboard')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  if (loading) return <Loading text="Loading finance dashboard..." />
  if (error) return <ErrorState message={error} onRetry={fetchData} />
  if (!dashboard) return null

  const kpiCards = [
    { label: 'Total Collected', value: formatCurrency(dashboard.total_collected), color: 'from-emerald-500 to-emerald-600' },
    { label: 'Total Outstanding', value: formatCurrency(dashboard.total_outstanding), color: 'from-red-500 to-red-600' },
    { label: 'Collection Rate', value: `${dashboard.collection_rate}%`, color: 'from-blue-500 to-blue-600' },
    { label: 'Payment Count', value: dashboard.payment_count.toLocaleString(), color: 'from-indigo-500 to-indigo-600' },
    { label: 'Today Collection', value: formatCurrency(dashboard.today_collection), color: 'from-amber-500 to-amber-600' },
  ]

  const attentionItems = [
    ...(exceptionCounts.critical > 0 ? [{ label: `${exceptionCounts.critical} critical financial exceptions`, to: '/school-finance/exceptions', tone: 'danger' as const }] : []),
    ...(exceptionCounts.high > 0 ? [{ label: `${exceptionCounts.high} high financial exceptions`, to: '/school-finance/exceptions', tone: 'warning' as const }] : []),
    ...(dashboard.pending_reconciliation > 0 ? [{ label: `${dashboard.pending_reconciliation} pending reconciliations`, to: '/school-finance/reconciliation', tone: 'warning' as const }] : []),
  ]

  const recentColumns = [
    { key: 'id', header: 'ID', render: (r: TransactionLogResponse) => `#${r.id}` },
    { key: 'transaction_type', header: 'Type' },
    { key: 'amount', header: 'Amount', render: (r: TransactionLogResponse) => <span className={r.amount >= 0 ? 'text-green-500' : 'text-red-500'}>{formatCurrency(r.amount)}</span> },
    { key: 'description', header: 'Description', render: (r: TransactionLogResponse) => r.description || '-' },
    { key: 'reference_number', header: 'Reference', render: (r: TransactionLogResponse) => r.reference_number || '-' },
    { key: 'created_at', header: 'Date', render: (r: TransactionLogResponse) => formatDate(r.created_at) },
  ]

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        title="Finance Dashboard"
        subtitle="Real-time finance KPIs, collection rates, and outstanding balances"
        actions={
          <div className="flex gap-2">
            <Link to="/school-finance" className="px-3 py-1.5 text-sm rounded-lg bg-[var(--color-surface-hover)] hover:bg-[var(--color-surface-active)] transition-colors">Hub</Link>
          </div>
        }
      />

      {/* P13 — what needs attention, straight from the exceptions engine */}
      {attentionItems.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">
            Attention
          </span>
          {attentionItems.map((item) => (
            <Link
              key={item.label}
              to={item.to}
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium motion-safe:transition-colors ${
                item.tone === 'danger'
                  ? 'border-[var(--color-danger)]/30 bg-[var(--color-danger)]/5 text-[var(--color-danger)] hover:bg-[var(--color-danger)]/10'
                  : 'border-[var(--color-warning)]/30 bg-[var(--color-warning)]/5 text-[var(--color-warning)] hover:bg-[var(--color-warning)]/10'
              }`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${item.tone === 'danger' ? 'bg-[var(--color-danger)]' : 'bg-[var(--color-warning)]'}`} aria-hidden="true" />
              {item.label}
            </Link>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        {kpiCards.map((kpi) => (
          <Card key={kpi.label} className="text-center">
            <p className="text-xs font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider">{kpi.label}</p>
            <p className={`text-2xl font-bold mt-1 bg-gradient-to-br ${kpi.color} bg-clip-text text-transparent`}>{kpi.value}</p>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Recent Transactions">
          {dashboard.recent_transactions.length === 0 ? (
            <p className="text-sm text-[var(--color-text-tertiary)] py-4 text-center">No recent transactions</p>
          ) : (
            <Table data={dashboard.recent_transactions} columns={recentColumns} keyExtractor={(r: TransactionLogResponse) => r.id} compact />
          )}
        </Card>

        {/* P13 — the real outstanding balances, not a placeholder */}
        <Card
          title="Outstanding Balances"
          actions={
            <Link to="/school-finance/outstanding" className="text-xs font-medium text-[var(--color-brand-accent)] hover:underline">
              View all
            </Link>
          }
        >
          {topOutstanding.length === 0 ? (
            <div className="py-8 text-center">
              <p className="text-sm text-[var(--color-success-dark)] font-medium">No outstanding balances</p>
              <p className="text-xs text-[var(--color-text-tertiary)] mt-1">All assigned fees are paid up.</p>
            </div>
          ) : (
            <div className="space-y-0 divide-y divide-[var(--color-border)]">
              {topOutstanding.map((row, i) => (
                <div key={i} className="flex items-center justify-between py-2.5">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-[var(--color-text-primary)] truncate">
                      {row.student_name || 'Unknown student'}
                    </p>
                    <p className="text-xs text-[var(--color-text-tertiary)]">
                      {row.class_name || '—'}
                      {row.overdue_count > 0 && (
                        <span className="ml-1.5 text-[var(--color-danger)] font-medium">
                          {row.overdue_count} overdue
                        </span>
                      )}
                    </p>
                  </div>
                  <span className="text-sm font-semibold tabular-nums text-[var(--color-danger)]">
                    {formatCurrency(row.outstanding)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}

export default SchoolFinanceDashboardPage
