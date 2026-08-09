import { useState, useEffect, useCallback, useRef } from 'react'
import { feeStructureApi, type FeeStructureListParams } from '../../api/fees/fee-structure-api'
import { feeTypeApi } from '../../api/fees/fee-type-api'
import { academicYearApi } from '../../api/academic/academic-year-api'
import { classApi } from '../../api/academic/class-api'
import type { FeeStructureResponse, FeeStructureCreate, FeeStructureUpdate } from '../../api/generated/types'
import { Card, Table, Pagination, Input, Select, Button, Badge, Modal, Form, Alert, ErrorState, useToast, PageHeader } from '../../components/ui'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'
import { FEE_STRUCTURE_STATUSES, capitalize, formatCurrency } from '../../lib/utils'

const statusBadge: Record<string, 'success' | 'danger'> = { active: 'success', inactive: 'danger' }

export function FeeStructureListPage() {
  const { showToast } = useToast()
  const firstFilterRef = useRef<HTMLInputElement>(null)

  useKeyboardShortcut({
    '/': (e) => { e.preventDefault(); firstFilterRef.current?.focus(); },
    'n': () => openCreateModal(),
  }, [])

  const [data, setData] = useState<FeeStructureResponse[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(0)
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(20)
  const [ayFilter, setAyFilter] = useState('')
  const [classFilter, setClassFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<FeeStructureResponse | null>(null)
  const [formData, setFormData] = useState<FeeStructureCreate>({ academic_year_id: 0, class_id: 0, fee_type_id: 0, amount: 0, frequency: 'annual' })
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)

  const fetchIdRef = useRef(0)

  const fetch = useCallback(async (params: FeeStructureListParams) => {
    const fetchId = ++fetchIdRef.current
    setLoading(true); setError(null)
    try {
      const result = await feeStructureApi.list(params)
      if (fetchId === fetchIdRef.current) {
        setData(result.items); setTotal(result.total); setPages(result.pages); setPage(result.page)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load fee structures')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const params: FeeStructureListParams = { page, size, status: statusFilter || undefined }
    if (ayFilter) params.academic_year_id = Number(ayFilter)
    if (classFilter) params.class_id = Number(classFilter)
    fetch(params)
  }, [page, size, statusFilter, ayFilter, classFilter, fetch])

  const openCreateModal = () => {
    setEditing(null)
    setFormData({ academic_year_id: 0, class_id: 0, fee_type_id: 0, amount: 0, frequency: 'annual' })
    setFormErrors({}); setApiError(null); setModalOpen(true)
  }

  const openEditModal = (fs: FeeStructureResponse) => {
    setEditing(fs)
    setFormData({ academic_year_id: fs.academic_year_id, class_id: fs.class_id, fee_type_id: fs.fee_type_id, amount: fs.amount, frequency: fs.frequency })
    setFormErrors({}); setApiError(null); setModalOpen(true)
  }

  const validate = () => {
    const e: Record<string, string> = {}
    if (!formData.academic_year_id) e.academic_year_id = 'Required'
    if (!formData.class_id) e.class_id = 'Required'
    if (!formData.fee_type_id) e.fee_type_id = 'Required'
    if (formData.amount <= 0) e.amount = 'Must be positive'
    setFormErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault()
    if (!validate()) return
    setSaving(true); setApiError(null)
    try {
      if (editing) {
        const updated = await feeStructureApi.update(editing.id, {
          academic_year_id: formData.academic_year_id || null,
          class_id: formData.class_id || null,
          fee_type_id: formData.fee_type_id || null,
          amount: formData.amount || null,
          frequency: formData.frequency || null,
        })
        setData((prev) => prev.map((fs) => (fs.id === updated.id ? updated : fs)))
        showToast('Fee structure updated', 'success')
      } else {
        const created = await feeStructureApi.create(formData)
        setData((prev) => [created, ...prev]); setTotal((t) => t + 1)
        showToast('Fee structure created', 'success')
      }
      setModalOpen(false)
    } catch (err: any) { setApiError(err?.detail || 'Failed to save') }
    finally { setSaving(false) }
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        eyebrow="Fees"
        title="Fee Structures"
        subtitle={`${total} structure${total !== 1 ? 's' : ''}`}
        compact
        actions={
          <Button onClick={openCreateModal}>
            Add Fee Structure
            <kbd className="ml-2 hidden sm:inline-flex items-center px-1.5 py-0.5 rounded bg-white/20 text-[10px] font-medium text-white/80">N</kbd>
          </Button>
        }
      />

      <div className="flex flex-wrap items-center gap-4">
        <Input ref={firstFilterRef} type="number" placeholder="Academic Year ID" value={ayFilter} onChange={(e) => { setAyFilter(e.target.value); setPage(1) }} className="w-36" />
        <Input type="number" placeholder="Class ID" value={classFilter} onChange={(e) => { setClassFilter(e.target.value); setPage(1) }} className="w-28" />
        <Select options={FEE_STRUCTURE_STATUSES.map((s) => ({ value: s, label: capitalize(s) }))} placeholder="All statuses" value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }} />
      </div>

      <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
        {error ? <ErrorState message={error} onRetry={() => fetch({ page, size })} /> : (
          <>
            <Table
              columns={[
                { key: 'id', header: 'ID', render: (fs: FeeStructureResponse) => `#${fs.id}` },
                { key: 'academic_year_id', header: 'AY' },
                { key: 'class_id', header: 'Class' },
                { key: 'fee_type_id', header: 'Fee Type' },
                { key: 'amount', header: 'Amount', render: (fs: FeeStructureResponse) => formatCurrency(fs.amount) },
                { key: 'frequency', header: 'Frequency', render: (fs: FeeStructureResponse) => capitalize(fs.frequency) },
                { key: 'status', header: 'Status', render: (fs: FeeStructureResponse) => <Badge variant={statusBadge[fs.status]}>{capitalize(fs.status)}</Badge> },
                {
                  key: 'actions', header: 'Actions',
                  render: (fs: FeeStructureResponse) => (
                    <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                      <Button variant="ghost" size="sm" onClick={() => openEditModal(fs)}>Edit</Button>
                    </div>
                  ),
                },
              ]}
              data={data}
              keyExtractor={(fs) => fs.id}
              emptyMessage="No fee structures found."
              loading={loading}
            />
            <Pagination page={page} size={size} total={total} pages={pages} onPageChange={setPage} onSizeChange={(s) => { setSize(s); setPage(1) }} />
          </>
        )}
      </Card>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)}
        title={editing ? 'Edit Fee Structure' : 'Add Fee Structure'}
        footer={
          <>
            <Button variant="outline" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button onClick={handleSubmit} loading={saving}>{editing ? 'Save Changes' : 'Create'}</Button>
          </>
        }
      >
        {apiError && <Alert variant="error" onClose={() => setApiError(null)}>{apiError}</Alert>}
        <Form onSubmit={handleSubmit}>
          <Input label="Academic Year ID" type="number" value={formData.academic_year_id || ''} onChange={(e) => setFormData({ ...formData, academic_year_id: Number(e.target.value) })} error={formErrors.academic_year_id} required />
          <Input label="Class ID" type="number" value={formData.class_id || ''} onChange={(e) => setFormData({ ...formData, class_id: Number(e.target.value) })} error={formErrors.class_id} required />
          <Input label="Fee Type ID" type="number" value={formData.fee_type_id || ''} onChange={(e) => setFormData({ ...formData, fee_type_id: Number(e.target.value) })} error={formErrors.fee_type_id} required />
          <Input label="Amount (cents)" type="number" value={formData.amount || ''} onChange={(e) => setFormData({ ...formData, amount: Number(e.target.value) })} error={formErrors.amount} required />
          <Select label="Frequency" value={formData.frequency} onChange={(e) => setFormData({ ...formData, frequency: e.target.value })} options={[
            { value: 'annual', label: 'Annual' }, { value: 'term', label: 'Per Term' }, { value: 'monthly', label: 'Monthly' }, { value: 'one_time', label: 'One Time' },
          ]} />
          {editing && (
            <Select label="Status" value={editing.status} onChange={(e) => setFormData({ ...formData, ...{ status: e.target.value } })} options={FEE_STRUCTURE_STATUSES.map((s) => ({ value: s, label: capitalize(s) }))} />
          )}
        </Form>
      </Modal>
    </div>
  )
}