import { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { feeScheduleApi, type FeeScheduleResponse } from '../../api/school-finance/school-finance-api'
import { Card, Table, PageHeader, Button, Badge, Pagination, Loading, ErrorState, useToast, Modal, Input, Select } from '../../components/ui'
import { formatDate } from '../../lib/utils'

function formatCurrency(amount: number) {
  return (amount / 100).toLocaleString('en-KE', { style: 'currency', currency: 'KES' })
}

const statusBadge: Record<string, 'success' | 'neutral' | 'warning' | 'danger'> = {
  active: 'success', inactive: 'neutral', draft: 'warning', archived: 'danger',
}

const columns = [
  { key: 'id', header: 'ID', render: (r: FeeScheduleResponse) => `#${r.id}` },
  { key: 'name', header: 'Name' },
  { key: 'amount', header: 'Amount', render: (r: FeeScheduleResponse) => formatCurrency(r.amount) },
  { key: 'installment_number', header: 'Installment' },
  { key: 'due_date', header: 'Due Date', render: (r: FeeScheduleResponse) => formatDate(r.due_date) },
  { key: 'status', header: 'Status', render: (r: FeeScheduleResponse) => <Badge variant={statusBadge[r.status] || 'neutral'}>{r.status.charAt(0).toUpperCase() + r.status.slice(1)}</Badge> },
  { key: 'created_at', header: 'Created', render: (r: FeeScheduleResponse) => formatDate(r.created_at) },
]

export const FeeSchedulesPage: React.FC = () => {
  const { showToast } = useToast()
  const [data, setData] = useState<FeeScheduleResponse[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [size] = useState(20)
  const [statusFilter, setStatusFilter] = useState('')
  const [feeStructureFilter, setFeeStructureFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState({ name: '', fee_structure_id: '', amount: '', status: 'draft' })
  const fetchIdRef = useRef(0)

  const fetch = useCallback(async () => {
    const fetchId = ++fetchIdRef.current
    setLoading(true); setError(null)
    try {
      const params: any = { page, size }
      if (statusFilter) params.status = statusFilter
      if (feeStructureFilter) params.fee_structure_id = Number(feeStructureFilter)
      const result = await feeScheduleApi.list(params)
      if (fetchId === fetchIdRef.current) { setData(result.items); setTotal(result.total); setPage(result.page) }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load fee schedules')
    } finally { if (fetchId === fetchIdRef.current) setLoading(false) }
  }, [page, size, statusFilter, feeStructureFilter])

  useEffect(() => { fetch() }, [fetch])

  const handleCreate = async () => {
    try {
      await feeScheduleApi.create({
        name: form.name,
        fee_structure_id: form.fee_structure_id ? Number(form.fee_structure_id) : 0,
        amount: form.amount ? Number(form.amount) : 0,
        status: form.status,
        installment_number: 1,
        due_date: new Date().toISOString().split('T')[0],
      })
      showToast('Fee schedule created', 'success')
      setShowModal(false)
      setForm({ name: '', fee_structure_id: '', amount: '', status: 'draft' })
      fetch()
    } catch (err: any) { showToast(err?.detail || 'Failed to create', 'error') }
  }

  const handleDelete = async (id: number) => {
    try {
      await feeScheduleApi.delete(id)
      showToast('Fee schedule deleted', 'info')
      fetch()
    } catch (err: any) { showToast(err?.detail || 'Failed to delete', 'error') }
  }

  const actionCol = {
    key: 'actions' as const,
    header: 'Actions' as const,
    render: (r: FeeScheduleResponse) => (
      <div className="flex gap-2">
        <Button size="sm" variant="ghost" onClick={() => { /* edit */ }}>Edit</Button>
        <Button size="sm" variant="ghost" className="text-red-500" onClick={(e: any) => { e.stopPropagation(); handleDelete(r.id) }}>Delete</Button>
      </div>
    ),
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        title="Fee Schedules"
        subtitle="Manage fee structures and schedules"
        actions={
          <div className="flex gap-2">
            <Link to="/school-finance" className="px-3 py-1.5 text-sm rounded-lg bg-[var(--color-surface-hover)] hover:bg-[var(--color-surface-active)] transition-colors">Hub</Link>
            <Button onClick={() => setShowModal(true)}>Create Schedule</Button>
          </div>
        }
      />

      <Card>
        <div className="flex flex-wrap gap-4 mb-4">
          <Select
            value={statusFilter}
            onChange={(e: any) => { setStatusFilter(e.target.value); setPage(1) }}
            options={[
              { value: '', label: 'All Statuses' },
              { value: 'active', label: 'Active' },
              { value: 'inactive', label: 'Inactive' },
              { value: 'draft', label: 'Draft' },
              { value: 'archived', label: 'Archived' },
            ]}
            className="w-40"
          />
          <Input placeholder="Fee Structure ID..." value={feeStructureFilter} onChange={(e) => { setFeeStructureFilter(e.target.value); setPage(1) }} className="w-44" />
        </div>

        {error && <ErrorState message={error} />}
        {loading ? <Loading /> : (
          <>
            <Table data={data} columns={[...columns, actionCol as any]} keyExtractor={(r) => r.id} />
            <Pagination page={page} size={size} total={total} pages={Math.ceil(total / size)} onPageChange={setPage} onSizeChange={() => {}} />
          </>
        )}
      </Card>

      <Modal open={showModal} onClose={() => setShowModal(false)} title="New Fee Schedule"
        footer={
          <div className="flex gap-2 justify-end">
            <Button variant="outline" onClick={() => setShowModal(false)}>Cancel</Button>
            <Button onClick={handleCreate}>Create</Button>
          </div>
        }
      >
        <div className="space-y-4">
          <Input label="Name" value={form.name} onChange={(e: any) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Term 1 Fees" required />
          <div className="grid grid-cols-2 gap-4">
            <Input label="Fee Structure ID" type="number" value={form.fee_structure_id} onChange={(e: any) => setForm({ ...form, fee_structure_id: e.target.value })} placeholder="Optional" />
            <Input label="Amount (cents)" type="number" value={form.amount} onChange={(e: any) => setForm({ ...form, amount: e.target.value })} placeholder="e.g. 50000" />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Status</label>
            <select className="w-full rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm bg-[var(--color-bg-primary)]" value={form.status} onChange={(e: any) => setForm({ ...form, status: e.target.value })}>
              <option value="draft">Draft</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </div>
        </div>
      </Modal>
    </div>
  )
}

export default FeeSchedulesPage
