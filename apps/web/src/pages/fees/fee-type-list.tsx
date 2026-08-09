import { useState, useEffect, useCallback, useRef } from 'react'
import { feeTypeApi, type FeeTypeListParams } from '../../api/fees/fee-type-api'
import type { FeeTypeResponse, FeeTypeCreate, FeeTypeUpdate } from '../../api/generated/types'
import { Card, Table, Pagination, Select, Button, Badge, Modal, Form, Alert, Input, ErrorState, useToast, PageHeader } from '../../components/ui'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'
import { FEE_TYPE_STATUSES, capitalize } from '../../lib/utils'

const statusBadge: Record<string, 'success' | 'danger'> = { active: 'success', inactive: 'danger' }

export function FeeTypeListPage() {
  const { showToast } = useToast()

  useKeyboardShortcut({ 'n': () => openCreateModal() }, [])

  const [data, setData] = useState<FeeTypeResponse[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(0)
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(20)
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<FeeTypeResponse | null>(null)
  const [formData, setFormData] = useState({ name: '', description: '' })
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)

  const fetchIdRef = useRef(0)

  const fetch = useCallback(async (params: FeeTypeListParams) => {
    const fetchId = ++fetchIdRef.current
    setLoading(true); setError(null)
    try {
      const result = await feeTypeApi.list(params)
      if (fetchId === fetchIdRef.current) {
        setData(result.items); setTotal(result.total); setPages(result.pages); setPage(result.page)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load fee types')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetch({ page, size, status: statusFilter || undefined })
  }, [page, size, statusFilter, fetch])

  const openCreateModal = () => {
    setEditing(null); setFormData({ name: '', description: '' })
    setFormErrors({}); setApiError(null); setModalOpen(true)
  }

  const openEditModal = (ft: FeeTypeResponse) => {
    setEditing(ft)
    setFormData({ name: ft.name, description: ft.description || '' })
    setFormErrors({}); setApiError(null); setModalOpen(true)
  }

  const validate = () => { const e: Record<string, string> = {}; if (!formData.name.trim()) e.name = 'Name is required'; setFormErrors(e); return Object.keys(e).length === 0 }

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault()
    if (!validate()) return
    setSaving(true); setApiError(null)
    try {
      if (editing) {
        const updated = await feeTypeApi.update(editing.id, { name: formData.name || null, description: formData.description || null })
        setData((prev) => prev.map((ft) => (ft.id === updated.id ? updated : ft)))
        showToast('Fee type updated', 'success')
      } else {
        const created = await feeTypeApi.create({ name: formData.name, description: formData.description || null })
        setData((prev) => [created, ...prev]); setTotal((t) => t + 1)
        showToast('Fee type created', 'success')
      }
      setModalOpen(false)
    } catch (err: any) {
      setApiError(err?.detail || 'Failed to save')
    } finally { setSaving(false) }
  }

  const handleDeactivate = async (ft: FeeTypeResponse) => {
    if (!confirm(`Deactivate fee type "${ft.name}"?`)) return
    try {
      await feeTypeApi.deactivate(ft.id)
      const updated = await feeTypeApi.getById(ft.id)
      setData((prev) => prev.map((item) => (item.id === updated.id ? updated : item)))
      showToast('Fee type deactivated', 'success')
    } catch (err: any) { showToast(err?.detail || 'Failed to deactivate', 'error') }
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        eyebrow="Fees"
        title="Fee Types"
        subtitle={`${total} type${total !== 1 ? 's' : ''}`}
        compact
        actions={
          <Button onClick={openCreateModal}>
            Add Fee Type
            <kbd className="ml-2 hidden sm:inline-flex items-center px-1.5 py-0.5 rounded bg-white/20 text-[10px] font-medium text-white/80">N</kbd>
          </Button>
        }
      />

      <div className="flex items-center gap-4">
        <Select
          options={FEE_TYPE_STATUSES.map((s) => ({ value: s, label: capitalize(s) }))}
          placeholder="All statuses"
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
        />
      </div>

      <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
        {error ? <ErrorState message={error} onRetry={() => fetch({ page, size })} /> : (
          <>
            <Table
              columns={[
                { key: 'name', header: 'Name' },
                { key: 'description', header: 'Description', render: (ft: FeeTypeResponse) => ft.description || '-' },
                { key: 'status', header: 'Status', render: (ft: FeeTypeResponse) => <Badge variant={statusBadge[ft.status]}>{capitalize(ft.status)}</Badge> },
                {
                  key: 'actions', header: 'Actions',
                  render: (ft: FeeTypeResponse) => (
                    <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                      <Button variant="ghost" size="sm" onClick={() => openEditModal(ft)}>Edit</Button>
                      {ft.status === 'active' && <Button variant="danger" size="sm" onClick={() => handleDeactivate(ft)}>Deactivate</Button>}
                    </div>
                  ),
                },
              ]}
              data={data}
              keyExtractor={(ft) => ft.id}
              emptyMessage="No fee types found."
              loading={loading}
            />
            <Pagination page={page} size={size} total={total} pages={pages} onPageChange={setPage} onSizeChange={(s) => { setSize(s); setPage(1) }} />
          </>
        )}
      </Card>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)}
        title={editing ? 'Edit Fee Type' : 'Add Fee Type'}
        footer={
          <>
            <Button variant="outline" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button onClick={handleSubmit} loading={saving}>{editing ? 'Save Changes' : 'Create'}</Button>
          </>
        }
      >
        {apiError && <Alert variant="error" onClose={() => setApiError(null)}>{apiError}</Alert>}
        <Form onSubmit={handleSubmit}>
          <Input label="Name" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} error={formErrors.name} required />
          <Input label="Description" value={formData.description} onChange={(e) => setFormData({ ...formData, description: e.target.value })} />
        </Form>
      </Modal>
    </div>
  )
}