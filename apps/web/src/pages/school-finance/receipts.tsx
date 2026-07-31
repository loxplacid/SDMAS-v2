import { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { receiptApi, type ReceiptResponse, type ReceiptDetailResponse } from '../../api/school-finance/school-finance-api'
import { Card, Table, PageHeader, Button, Badge, Pagination, Loading, ErrorState, useToast, Modal, Input, Select } from '../../components/ui'
import { formatDate } from '../../lib/utils'

function formatCurrency(amount: number) {
  return (amount / 100).toLocaleString('en-KE', { style: 'currency', currency: 'KES' })
}

const columns = [
  { key: 'receipt_number', header: 'Receipt #', render: (r: ReceiptResponse) => `#${r.receipt_number}` },
  { key: 'amount', header: 'Amount', render: (r: ReceiptResponse) => formatCurrency(r.amount) },
  { key: 'payment_method_name', header: 'Method' },
  { key: 'receipt_date', header: 'Date', render: (r: ReceiptResponse) => formatDate(r.receipt_date) },
  { key: 'reference_number', header: 'Reference', render: (r: ReceiptResponse) => r.reference_number || '-' },
  { key: 'status', header: 'Status', render: (r: ReceiptResponse) => <Badge variant={r.status === 'active' ? 'success' : 'neutral'}>{r.status.charAt(0).toUpperCase() + r.status.slice(1)}</Badge> },
]

const receiptDetailColumns = [
  { key: 'receipt_number', header: 'Receipt #' },
  { key: 'student_name', header: 'Student', render: (r: ReceiptDetailResponse) => r.student_name || 'N/A' },
  { key: 'amount', header: 'Amount', render: (r: ReceiptDetailResponse) => formatCurrency(r.amount) },
  { key: 'payment_method_name', header: 'Method' },
  { key: 'receipt_date', header: 'Date', render: (r: ReceiptDetailResponse) => formatDate(r.receipt_date) },
  { key: 'notes', header: 'Notes', render: (r: ReceiptDetailResponse) => r.notes || '-' },
]

export const ReceiptsPage: React.FC = () => {
  const { showToast } = useToast()
  const [data, setData] = useState<ReceiptResponse[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [size] = useState(20)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [showDetail, setShowDetail] = useState(false)
  const [detailData, setDetailData] = useState<any>(null)
  const [form, setForm] = useState({ payment_id: '', notes: '' })
  const fetchIdRef = useRef(0)

  const fetch = useCallback(async () => {
    const fetchId = ++fetchIdRef.current
    setLoading(true); setError(null)
    try {
      const params: any = { page, size }
      if (search) params.search = search
      if (statusFilter) params.status = statusFilter
      const result = await receiptApi.list(params)
      if (fetchId === fetchIdRef.current) { setData(result.items); setTotal(result.total); setPage(result.page) }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load receipts')
    } finally { if (fetchId === fetchIdRef.current) setLoading(false) }
  }, [page, size, search, statusFilter])

  useEffect(() => { fetch() }, [fetch])

  const handleCreate = async () => {
    try {
      await receiptApi.generate({
        payment_id: Number(form.payment_id),
        notes: form.notes || null,
      })
      showToast('Receipt generated', 'success')
      setShowModal(false)
      setForm({ payment_id: '', notes: '' })
      fetch()
    } catch (err: any) { showToast(err?.detail || 'Failed to generate receipt', 'error') }
  }

  const handleViewDetail = async (id: number) => {
    try {
      const detail = await receiptApi.getDetail(id)
      setDetailData(detail)
      setShowDetail(true)
    } catch (err: any) { showToast(err?.detail || 'Failed to load receipt detail', 'error') }
  }

  const actionCol = {
    key: 'actions' as const,
    header: 'Actions' as const,
    render: (r: ReceiptResponse) => (
      <div className="flex gap-2">
        <Button size="sm" variant="outline" onClick={(e: any) => { e.stopPropagation(); handleViewDetail(r.id) }}>View</Button>
        <Button size="sm" variant="ghost" onClick={(e: any) => { e.stopPropagation(); window.open(`/api/school-finance/receipts/${r.id}/print`, '_blank') }}>Print</Button>
      </div>
    ),
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        title="Receipts"
        subtitle="Generate and manage payment receipts"
        actions={
          <div className="flex gap-2">
            <Link to="/school-finance" className="px-3 py-1.5 text-sm rounded-lg bg-[var(--color-surface-hover)] hover:bg-[var(--color-surface-active)] transition-colors">Hub</Link>
            <Button onClick={() => setShowModal(true)}>Generate Receipt</Button>
          </div>
        }
      />

      <Card>
        <div className="flex flex-wrap gap-4 mb-4">
          <Input placeholder="Search receipts..." value={search} onChange={(e: any) => { setSearch(e.target.value); setPage(1) }} className="w-60" />
          <Select
            value={statusFilter}
            onChange={(e: any) => { setStatusFilter(e.target.value); setPage(1) }}
            options={[
              { value: '', label: 'All Statuses' },
              { value: 'active', label: 'Active' },
              { value: 'cancelled', label: 'Cancelled' },
            ]}
            className="w-40"
          />
        </div>

        {error && <ErrorState message={error} />}
        {loading ? <Loading /> : (
          <>
            <Table data={data} columns={[...columns, actionCol as any]} keyExtractor={(r) => r.id} />
            <Pagination page={page} size={size} total={total} pages={Math.ceil(total / size)} onPageChange={setPage} onSizeChange={() => {}} />
          </>
        )}
      </Card>

      <Modal open={showModal} onClose={() => setShowModal(false)} title="Generate Receipt"
        footer={
          <div className="flex gap-2 justify-end">
            <Button variant="outline" onClick={() => setShowModal(false)}>Cancel</Button>
            <Button onClick={handleCreate}>Generate</Button>
          </div>
        }
      >
        <div className="space-y-4">
          <Input label="Payment ID" type="number" value={form.payment_id} onChange={(e: any) => setForm({ ...form, payment_id: e.target.value })} required />
          <Input label="Notes" value={form.notes} onChange={(e: any) => setForm({ ...form, notes: e.target.value })} placeholder="Optional notes" />
        </div>
      </Modal>

      <Modal open={showDetail} onClose={() => setShowDetail(false)} title="Receipt Detail" size="lg"
        footer={
          <div className="flex gap-2 justify-end">
            {detailData && (
              <Button variant="outline" onClick={() => window.open(`/api/school-finance/receipts/${detailData.id}/print`, '_blank')}>Print</Button>
            )}
            <Button variant="outline" onClick={() => setShowDetail(false)}>Close</Button>
          </div>
        }
      >
        {detailData ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-[var(--color-text-tertiary)]">Receipt #</p>
                <p className="text-sm font-medium">#{detailData.receipt_number}</p>
              </div>
              <div>
                <p className="text-sm text-[var(--color-text-tertiary)]">Student</p>
                <p className="text-sm font-medium">{detailData.student_name || `Student #${detailData.student_id}`}</p>
              </div>
              <div>
                <p className="text-sm text-[var(--color-text-tertiary)]">Amount</p>
                <p className="text-sm font-medium">{formatCurrency(detailData.amount)}</p>
              </div>
              <div>
                <p className="text-sm text-[var(--color-text-tertiary)]">Method</p>
                <p className="text-sm font-medium">{detailData.payment_method_name}</p>
              </div>
              <div>
                <p className="text-sm text-[var(--color-text-tertiary)]">Date</p>
                <p className="text-sm font-medium">{formatDate(detailData.receipt_date)}</p>
              </div>
              <div>
                <p className="text-sm text-[var(--color-text-tertiary)]">Status</p>
                <Badge variant={detailData.status === 'active' ? 'success' : 'neutral'}>{detailData.status}</Badge>
              </div>
            </div>
            {detailData.notes && (
              <div>
                <p className="text-sm text-[var(--color-text-tertiary)]">Notes</p>
                <p className="text-sm">{detailData.notes}</p>
              </div>
            )}
          </div>
        ) : (
          <Loading />
        )}
      </Modal>
    </div>
  )
}

export default ReceiptsPage
