import { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { outstandingBalanceApi, type OutstandingBalanceItem } from '../../api/school-finance/school-finance-api'
import { Card, Table, PageHeader, Badge, Pagination, Loading, ErrorState, Input, Select } from '../../components/ui'
import { formatDate } from '../../lib/utils'

function formatCurrency(amount: number) {
  return (amount / 100).toLocaleString('en-KE', { style: 'currency', currency: 'KES' })
}

const columns = [
  { key: 'student_name', header: 'Student' },
  { key: 'class_name', header: 'Class' },
  { key: 'student_number', header: 'Admission No.' },
  { key: 'total_assigned', header: 'Total Fees', render: (r: OutstandingBalanceItem) => formatCurrency(r.total_assigned) },
  { key: 'total_paid', header: 'Paid', render: (r: OutstandingBalanceItem) => formatCurrency(r.total_paid) },
  { key: 'outstanding', header: 'Balance', render: (r: OutstandingBalanceItem) => <span className="font-semibold text-red-500">{formatCurrency(r.outstanding)}</span> },
  { key: 'due_count', header: 'Due Count' },
  { key: 'overdue_count', header: 'Overdue', render: (r: OutstandingBalanceItem) => <span className={r.overdue_count > 0 ? 'text-red-500 font-semibold' : ''}>{r.overdue_count}</span> },
]

export const OutstandingBalancesPage: React.FC = () => {
  const [data, setData] = useState<OutstandingBalanceItem[]>([])
  const [total, setTotal] = useState(0)
  const [totalOutstanding, setTotalOutstanding] = useState(0)
  const [page, setPage] = useState(1)
  const [size] = useState(20)
  const [classFilter, setClassFilter] = useState('')
  const [academicYearFilter, setAcademicYearFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  const fetch = useCallback(async () => {
    const fetchId = ++fetchIdRef.current
    setLoading(true); setError(null)
    try {
      const params: any = {}
      if (classFilter) params.class_id = Number(classFilter)
      const result = await outstandingBalanceApi.getOutstanding(params)
      if (fetchId === fetchIdRef.current) {
        setData(result.items)
        setTotal(result.items.length)
        setTotalOutstanding(result.total_outstanding)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load outstanding balances')
    } finally { if (fetchId === fetchIdRef.current) setLoading(false) }
  }, [classFilter])

  useEffect(() => { fetch() }, [fetch])

  if (loading && data.length === 0) return <Loading text="Loading outstanding balances..." />
  if (error) return <ErrorState message={error} onRetry={fetch} />

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        title="Outstanding Balances"
        subtitle="Student fee balances and collection tracking"
        actions={
          <div className="flex gap-2">
            <Link to="/school-finance" className="px-3 py-1.5 text-sm rounded-lg bg-[var(--color-surface-hover)] hover:bg-[var(--color-surface-active)] transition-colors">Hub</Link>
          </div>
        }
      />

      <Card className="text-center bg-gradient-to-br from-rose-50 to-red-50 dark:from-rose-950/20 dark:to-red-950/20">
        <p className="text-sm font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider">Total Outstanding</p>
        <p className="text-4xl font-bold mt-2 text-red-500">{formatCurrency(totalOutstanding)}</p>
      </Card>

      <Card>
        <div className="flex flex-wrap gap-4 mb-4">
          <Input placeholder="Class ID..." value={classFilter} onChange={(e: any) => { setClassFilter(e.target.value); setPage(1) }} className="w-40" />
          <Input placeholder="Academic Year ID..." value={academicYearFilter} onChange={(e: any) => { setAcademicYearFilter(e.target.value); setPage(1) }} className="w-44" />
        </div>

        {loading ? <Loading /> : (
          <>
            <Table data={data} columns={columns} keyExtractor={(r) => r.student_id} />
            <Pagination page={page} size={size} total={total} pages={Math.ceil(total / size)} onPageChange={setPage} onSizeChange={() => {}} />
          </>
        )}
      </Card>
    </div>
  )
}

export default OutstandingBalancesPage
