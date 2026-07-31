import { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { transactionLogApi, type TransactionLogResponse } from '../../api/school-finance/school-finance-api'
import { Card, Table, PageHeader, Button, Badge, Pagination, Loading, ErrorState, Input, Select } from '../../components/ui'
import { formatDate } from '../../lib/utils'

function formatCurrency(amount: number) {
  return (amount / 100).toLocaleString('en-KE', { style: 'currency', currency: 'KES' })
}

const typeBadge: Record<string, 'info' | 'success' | 'danger' | 'warning' | 'neutral'> = {
  payment: 'success', refund: 'danger', waiver: 'warning', adjustment: 'info', reversal: 'neutral',
}

const columns = [
  { key: 'id', header: 'ID', render: (r: TransactionLogResponse) => `#${r.id}` },
  { key: 'transaction_type', header: 'Type', render: (r: TransactionLogResponse) => <Badge variant={typeBadge[r.transaction_type] || 'neutral'}>{r.transaction_type.replace('_', ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}</Badge> },
  { key: 'amount', header: 'Amount', render: (r: TransactionLogResponse) => <span className={r.amount >= 0 ? 'text-green-500' : 'text-red-500'}>{formatCurrency(r.amount)}</span> },
  { key: 'balance_before', header: 'Balance Before', render: (r: TransactionLogResponse) => formatCurrency(r.balance_before) },
  { key: 'balance_after', header: 'Balance After', render: (r: TransactionLogResponse) => formatCurrency(r.balance_after) },
  { key: 'reference_number', header: 'Reference', render: (r: TransactionLogResponse) => r.reference_number || '-' },
  { key: 'description', header: 'Description', render: (r: TransactionLogResponse) => r.description || '-' },
  { key: 'created_at', header: 'Date', render: (r: TransactionLogResponse) => formatDate(r.created_at) },
]

export const TransactionsPage: React.FC = () => {
  const [data, setData] = useState<TransactionLogResponse[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [size] = useState(20)
  const [studentFilter, setStudentFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  const fetch = useCallback(async () => {
    const fetchId = ++fetchIdRef.current
    setLoading(true); setError(null)
    try {
      const params: any = { page, size }
      if (studentFilter) params.student_id = Number(studentFilter)
      if (typeFilter) params.transaction_type = typeFilter
      if (dateFrom) params.from_date = dateFrom
      if (dateTo) params.to_date = dateTo
      const result = await transactionLogApi.list(params)
      if (fetchId === fetchIdRef.current) { setData(result.items); setTotal(result.total); setPage(result.page) }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load transactions')
    } finally { if (fetchId === fetchIdRef.current) setLoading(false) }
  }, [page, size, studentFilter, typeFilter, dateFrom, dateTo])

  useEffect(() => { fetch() }, [fetch])

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        title="Transactions"
        subtitle="View and filter transaction logs"
        actions={
          <div className="flex gap-2">
            <Link to="/school-finance" className="px-3 py-1.5 text-sm rounded-lg bg-[var(--color-surface-hover)] hover:bg-[var(--color-surface-active)] transition-colors">Hub</Link>
          </div>
        }
      />

      <Card>
        <div className="flex flex-wrap gap-4 mb-4">
          <Input placeholder="Student ID..." value={studentFilter} onChange={(e: any) => { setStudentFilter(e.target.value); setPage(1) }} className="w-40" />
          <Select
            value={typeFilter}
            onChange={(e: any) => { setTypeFilter(e.target.value); setPage(1) }}
            options={[
              { value: '', label: 'All Types' },
              { value: 'payment', label: 'Payment' },
              { value: 'refund', label: 'Refund' },
              { value: 'waiver', label: 'Waiver' },
              { value: 'adjustment', label: 'Adjustment' },
              { value: 'reversal', label: 'Reversal' },
            ]}
            className="w-40"
          />
          <Input type="date" value={dateFrom} onChange={(e: any) => { setDateFrom(e.target.value); setPage(1) }} className="w-44" placeholder="From date" />
          <Input type="date" value={dateTo} onChange={(e: any) => { setDateTo(e.target.value); setPage(1) }} className="w-44" placeholder="To date" />
        </div>

        {error && <ErrorState message={error} />}
        {loading ? <Loading /> : (
          <>
            <Table data={data} columns={columns} keyExtractor={(r) => r.id} />
            <Pagination page={page} size={size} total={total} pages={Math.ceil(total / size)} onPageChange={setPage} onSizeChange={() => {}} />
          </>
        )}
      </Card>
    </div>
  )
}

export default TransactionsPage
