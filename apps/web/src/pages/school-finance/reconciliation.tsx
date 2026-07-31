import { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { reconciliationApi, type PaymentReconciliationResponse } from '../../api/school-finance/school-finance-api'
import { Card, Table, PageHeader, Button, Badge, Pagination, Loading, ErrorState, useToast, Modal, Input } from '../../components/ui'
import { formatDate } from '../../lib/utils'

function formatCurrency(amount: number) {
  return (amount / 100).toLocaleString('en-KE', { style: 'currency', currency: 'KES' })
}

const statusBadge: Record<string, 'neutral' | 'success' | 'info' | 'danger'> = {
  draft: 'neutral', verified: 'info', approved: 'success', rejected: 'danger',
}

const columns = [
  { key: 'id', header: 'ID', render: (r: PaymentReconciliationResponse) => `#${r.id}` },
  { key: 'reconciliation_date', header: 'Date', render: (r: PaymentReconciliationResponse) => formatDate(r.reconciliation_date) },
  { key: 'total_amount', header: 'Total Amount', render: (r: PaymentReconciliationResponse) => formatCurrency(r.total_amount) },
  { key: 'total_count', header: 'Count', render: (r: PaymentReconciliationResponse) => r.total_count },
  { key: 'difference', header: 'Difference', render: (r: PaymentReconciliationResponse) => {
    const diff = r.items.reduce((sum, item) => sum + item.difference, 0)
    return <span className={diff !== 0 ? 'text-red-500 font-semibold' : 'text-green-500'}>{diff >= 0 ? '+' : ''}{formatCurrency(Math.abs(diff))}</span>
  }},
  { key: 'status', header: 'Status', render: (r: PaymentReconciliationResponse) => <Badge variant={statusBadge[r.status] || 'neutral'}>{r.status.charAt(0).toUpperCase() + r.status.slice(1)}</Badge> },
  { key: 'notes', header: 'Notes', render: (r: PaymentReconciliationResponse) => r.notes || '-' },
]

export const ReconciliationPage: React.FC = () => {
  const { showToast } = useToast()
  const [data, setData] = useState<PaymentReconciliationResponse[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [size] = useState(20)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState({ reconciliation_date: '', total_amount: '', total_count: '', notes: '' })
  const fetchIdRef = useRef(0)

  const fetch = useCallback(async () => {
    const fetchId = ++fetchIdRef.current
    setLoading(true); setError(null)
    try {
      const result = await reconciliationApi.list({ page, size })
      if (fetchId === fetchIdRef.current) { setData(result.items); setTotal(result.total); setPage(result.page) }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load reconciliations')
    } finally { if (fetchId === fetchIdRef.current) setLoading(false) }
  }, [page, size])

  useEffect(() => { fetch() }, [fetch])

  const handleCreate = async () => {
    try {
      await reconciliationApi.create({
        reconciliation_date: form.reconciliation_date,
        total_amount: form.total_amount ? Number(form.total_amount) : undefined,
        total_count: form.total_count ? Number(form.total_count) : undefined,
        notes: form.notes || null,
      })
      showToast('Reconciliation created', 'success')
      setShowModal(false)
      setForm({ reconciliation_date: '', total_amount: '', total_count: '', notes: '' })
      fetch()
    } catch (err: any) { showToast(err?.detail || 'Failed to create', 'error') }
  }

  const handleVerify = async (id: number) => {
    try {
      await reconciliationApi.verify(id)
      showToast('Reconciliation verified', 'success')
      fetch()
    } catch (err: any) { showToast(err?.detail || 'Failed to verify', 'error') }
  }

  const handleApprove = async (id: number) => {
    try {
      await reconciliationApi.approve(id)
      showToast('Reconciliation approved', 'success')
      fetch()
    } catch (err: any) { showToast(err?.detail || 'Failed to approve', 'error') }
  }

  const actionCol = {
    key: 'actions' as const,
    header: 'Actions' as const,
    render: (r: PaymentReconciliationResponse) => (
      <div className="flex gap-2">
        {r.status === 'draft' && (
          <Button size="sm" variant="primary" onClick={(e: any) => { e.stopPropagation(); handleVerify(r.id) }}>Verify</Button>
        )}
        {r.status === 'verified' && (
          <Button size="sm" variant="primary" onClick={(e: any) => { e.stopPropagation(); handleApprove(r.id) }}>Approve</Button>
        )}
      </div>
    ),
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        title="Reconciliation"
        subtitle="Verify and approve financial reconciliations"
        actions={
          <div className="flex gap-2">
            <Link to="/school-finance" className="px-3 py-1.5 text-sm rounded-lg bg-[var(--color-surface-hover)] hover:bg-[var(--color-surface-active)] transition-colors">Hub</Link>
            <Button onClick={() => setShowModal(true)}>New Reconciliation</Button>
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

      <Modal open={showModal} onClose={() => setShowModal(false)} title="New Reconciliation"
        footer={
          <div className="flex gap-2 justify-end">
            <Button variant="outline" onClick={() => setShowModal(false)}>Cancel</Button>
            <Button onClick={handleCreate}>Create</Button>
          </div>
        }
      >
        <div className="space-y-4">
          <Input label="Date" type="date" value={form.reconciliation_date} onChange={(e: any) => setForm({ ...form, reconciliation_date: e.target.value })} required />
          <div className="grid grid-cols-2 gap-4">
            <Input label="Total Amount (cents)" type="number" value={form.total_amount} onChange={(e: any) => setForm({ ...form, total_amount: e.target.value })} />
            <Input label="Total Count" type="number" value={form.total_count} onChange={(e: any) => setForm({ ...form, total_count: e.target.value })} />
          </div>
          <Input label="Notes" value={form.notes} onChange={(e: any) => setForm({ ...form, notes: e.target.value })} placeholder="Optional notes" />
        </div>
      </Modal>
    </div>
  )
}

export default ReconciliationPage
