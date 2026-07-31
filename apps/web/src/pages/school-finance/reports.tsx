import { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { financeReportApi, type FinanceReportResponse } from '../../api/school-finance/school-finance-api'
import { Card, Table, PageHeader, Button, Badge, Pagination, Loading, ErrorState, useToast, Modal, Input, Select } from '../../components/ui'
import { formatDate } from '../../lib/utils'

const reportTypes = [
  { value: 'collection_summary', label: 'Collection Summary' },
  { value: 'fee_collection', label: 'Fee Collection' },
  { value: 'outstanding', label: 'Outstanding' },
  { value: 'receipt_journal', label: 'Receipt Journal' },
]

const columns = [
  { key: 'id', header: 'ID', render: (r: FinanceReportResponse) => `#${r.id}` },
  { key: 'report_type', header: 'Type', render: (r: FinanceReportResponse) => {
    const t = reportTypes.find(rt => rt.value === r.report_type)
    return t ? t.label : r.report_type
  }},
  { key: 'title', header: 'Title' },
  { key: 'created_at', header: 'Generated', render: (r: FinanceReportResponse) => formatDate(r.created_at) },
  { key: 'completed_at', header: 'Completed', render: (r: FinanceReportResponse) => r.completed_at ? formatDate(r.completed_at) : '-' },
  { key: 'status', header: 'Status', render: (r: FinanceReportResponse) => <Badge variant={r.status === 'completed' ? 'success' : r.status === 'generating' ? 'warning' : 'neutral'}>{r.status.charAt(0).toUpperCase() + r.status.slice(1)}</Badge> },
]

export const FinanceReportsPage: React.FC = () => {
  const { showToast } = useToast()
  const [data, setData] = useState<FinanceReportResponse[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [size] = useState(20)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState({ report_type: 'collection_summary', title: '', from_date: '', to_date: '' })
  const fetchIdRef = useRef(0)

  const fetch = useCallback(async () => {
    const fetchId = ++fetchIdRef.current
    setLoading(true); setError(null)
    try {
      const result = await financeReportApi.listReports({ page, size })
      if (fetchId === fetchIdRef.current) { setData(result.items); setTotal(result.total); setPage(result.page) }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load reports')
    } finally { if (fetchId === fetchIdRef.current) setLoading(false) }
  }, [page, size])

  useEffect(() => { fetch() }, [fetch])

  const handleGenerate = async () => {
    try {
      await financeReportApi.generate(form)
      showToast('Report generation started', 'success')
      setShowModal(false)
      setForm({ report_type: 'collection_summary', title: '', from_date: '', to_date: '' })
      fetch()
    } catch (err: any) { showToast(err?.detail || 'Failed to generate report', 'error') }
  }

  const handleDownload = (report: FinanceReportResponse) => {
    window.open(`/api/school-finance/reports/${report.id}/download`, '_blank')
  }

  const actionCol = {
    key: 'actions' as const,
    header: 'Actions' as const,
    render: (r: FinanceReportResponse) => (
      <div className="flex gap-2">
        {r.status === 'completed' && (
          <Button size="sm" variant="outline" onClick={(e: any) => { e.stopPropagation(); handleDownload(r) }}>
            Download CSV
          </Button>
        )}
      </div>
    ),
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        title="Finance Reports"
        subtitle="Generate and download financial reports"
        actions={
          <div className="flex gap-2">
            <Link to="/school-finance" className="px-3 py-1.5 text-sm rounded-lg bg-[var(--color-surface-hover)] hover:bg-[var(--color-surface-active)] transition-colors">Hub</Link>
            <Button onClick={() => setShowModal(true)}>Generate Report</Button>
          </div>
        }
      />

      <Card>
        {error && <ErrorState message={error} />}
        {loading ? <Loading /> : (
          <>
            <Table data={data} columns={[...columns, actionCol as any]} keyExtractor={(r) => r.id} />
            <Pagination page={page} size={size} total={total} pages={Math.ceil(total / size)} onPageChange={setPage} onSizeChange={() => {}} />
          </>
        )}
      </Card>

      <Modal open={showModal} onClose={() => setShowModal(false)} title="Generate Report"
        footer={
          <div className="flex gap-2 justify-end">
            <Button variant="outline" onClick={() => setShowModal(false)}>Cancel</Button>
            <Button onClick={handleGenerate}>Generate</Button>
          </div>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Report Type</label>
            <select className="w-full rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm bg-[var(--color-bg-primary)]" value={form.report_type} onChange={(e: any) => setForm({ ...form, report_type: e.target.value })}>
              {reportTypes.map(rt => <option key={rt.value} value={rt.value}>{rt.label}</option>)}
            </select>
          </div>
          <Input label="Title" value={form.title} onChange={(e: any) => setForm({ ...form, title: e.target.value })} placeholder="e.g. Term 1 Collection Summary" required />
          <div className="grid grid-cols-2 gap-4">
            <Input label="From Date" type="date" value={form.from_date} onChange={(e: any) => setForm({ ...form, from_date: e.target.value })} />
            <Input label="To Date" type="date" value={form.to_date} onChange={(e: any) => setForm({ ...form, to_date: e.target.value })} />
          </div>
        </div>
      </Modal>
    </div>
  )
}

export default FinanceReportsPage
