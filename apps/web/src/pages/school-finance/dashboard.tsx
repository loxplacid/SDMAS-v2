import { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { schoolFinanceDashboardApi, type SchoolFinanceDashboard, type TransactionLogResponse } from '../../api/school-finance/school-finance-api'
import { Card, PageHeader, Loading, ErrorState, Badge, Table } from '../../components/ui'
import { formatDate } from '../../lib/utils'

function formatCurrency(amount: number) {
  return (amount / 100).toLocaleString('en-KE', { style: 'currency', currency: 'KES' })
}

export const SchoolFinanceDashboardPage: React.FC = () => {
  const [dashboard, setDashboard] = useState<SchoolFinanceDashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  const fetchData = useCallback(async () => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)
    try {
      const data = await schoolFinanceDashboardApi.getDashboard()
      if (fetchId === fetchIdRef.current) setDashboard(data)
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

        <Card title="Outstanding Balances">
          <div className="flex items-center justify-center py-8">
            <p className="text-sm text-[var(--color-text-tertiary)]">Coming soon</p>
          </div>
        </Card>
      </div>
    </div>
  )
}

export default SchoolFinanceDashboardPage
