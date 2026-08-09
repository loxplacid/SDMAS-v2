import { useState, useEffect, useCallback, useRef } from 'react'
import { subjectApi, type SubjectListParams } from '../../api/academic/subject-api'
import type { SubjectResponse, SubjectCreate, SubjectUpdate } from '../../api/generated/types'
import { Card, Table, Pagination, Input, Select, Button, Badge, Modal, Form, Alert, EmptyState, ErrorState, useToast, PageHeader } from '../../components/ui'
import { SUBJECT_STATUSES, capitalize } from '../../lib/utils'

const statusBadge: Record<string, 'success' | 'warning' | 'danger' | 'info'> = { active: 'success', inactive: 'danger' }

const columns = [
  { key: 'name', header: 'Name' },
  { key: 'code', header: 'Code' },
  { key: 'description', header: 'Description', render: (s: SubjectResponse) => s.description || '-' },
  { key: 'status', header: 'Status', render: (s: SubjectResponse) => <Badge variant={statusBadge[s.status] || 'default'}>{capitalize(s.status)}</Badge> },
]

export function SubjectListPage() {
  const { showToast } = useToast()
  const [data, setData] = useState<SubjectResponse[]>([])
  const [total, setTotal] = useState(0); const [pages, setPages] = useState(0)
  const [page, setPage] = useState(1); const [size, setSize] = useState(20)
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true); const [error, setError] = useState<string | null>(null)

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<SubjectResponse | null>(null)
  const [formData, setFormData] = useState<{ name: string; code: string; description: string | null; status?: string | null }>({ name: '', code: '', description: null })
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false); const [apiError, setApiError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  const fetch = useCallback(async (params: SubjectListParams) => {
    const fetchId = ++fetchIdRef.current; setLoading(true); setError(null)
    try {
      const result = await subjectApi.list(params)
      if (fetchId === fetchIdRef.current) { setData(result.items); setTotal(result.total); setPages(result.pages); setPage(result.page) }
    } catch (err: any) { if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load subjects')
    } finally { if (fetchId === fetchIdRef.current) setLoading(false) }
  }, [])

  useEffect(() => { fetch({ page, size, status: statusFilter || undefined }) }, [page, size, statusFilter, fetch])

  const openCreateModal = () => { setEditing(null); setFormData({ name: '', code: '', description: null }); setFormErrors({}); setApiError(null); setModalOpen(true) }
  const openEditModal = (s: SubjectResponse) => { setEditing(s); setFormData({ name: s.name, code: s.code, description: s.description, status: s.status }); setFormErrors({}); setApiError(null); setModalOpen(true) }
  const validate = (): boolean => { const e: Record<string, string> = {}; if (!formData.name.trim()) e.name = 'Name is required'; if (!formData.code.trim()) e.code = 'Code is required'; setFormErrors(e); return Object.keys(e).length === 0 }

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault(); if (!validate()) return; setSaving(true); setApiError(null)
    try {
      if (editing) {
        const updated = await subjectApi.update(editing.id, { name: formData.name || null, code: formData.code || null, description: formData.description, status: formData.status || null })
        setData((prev) => prev.map((s) => (s.id === updated.id ? updated : s))); showToast('Subject updated', 'success')
      } else {
        const created = await subjectApi.create({ name: formData.name, code: formData.code, description: formData.description })
        setData((prev) => [created, ...prev]); setTotal((t) => t + 1); showToast('Subject created', 'success')
      }
      setModalOpen(false)
    } catch (err: any) { setApiError(err?.detail || 'Failed to save')
    } finally { setSaving(false) }
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        eyebrow="Academics"
        title="Subjects"
        subtitle={`${total} subject${total !== 1 ? 's' : ''}`}
        compact
        actions={<Button onClick={openCreateModal}>Add Subject</Button>}
      />
      <div className="flex items-center gap-4">
        <Select options={SUBJECT_STATUSES.map((s) => ({ value: s, label: capitalize(s) }))} placeholder="All statuses" value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }} />
      </div>
      <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
        {error ? <ErrorState message={error} onRetry={() => fetch({ page, size, status: statusFilter || undefined })} /> : (
          <>
            <Table columns={[...columns, { key: 'actions', header: 'Actions', render: (s: SubjectResponse) => (<div className="flex gap-2" onClick={(e) => e.stopPropagation()}><Button variant="ghost" size="sm" onClick={() => openEditModal(s)}>Edit</Button></div>) }]} data={data} keyExtractor={(s) => s.id} emptyMessage="No subjects found." loading={loading} />
            <Pagination page={page} size={size} total={total} pages={pages} onPageChange={setPage} onSizeChange={(s) => { setSize(s); setPage(1) }} />
          </>
        )}
      </Card>
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Edit Subject' : 'Add Subject'}
        footer={<><Button variant="outline" onClick={() => setModalOpen(false)}>Cancel</Button><Button onClick={handleSubmit} loading={saving}>{editing ? 'Save Changes' : 'Create'}</Button></>}
      >
        {apiError && <Alert variant="error" onClose={() => setApiError(null)}>{apiError}</Alert>}
        <Form onSubmit={handleSubmit}>
          <Input label="Name" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} error={formErrors.name} required />
          <Input label="Code" value={formData.code} onChange={(e) => setFormData({ ...formData, code: e.target.value })} error={formErrors.code} required />
          <Input label="Description" value={formData.description ?? ''} onChange={(e) => setFormData({ ...formData, description: e.target.value || null })} />
          {editing && <Select label="Status" value={formData.status ?? editing.status} onChange={(e) => setFormData({ ...formData, status: e.target.value })} options={SUBJECT_STATUSES.map((s) => ({ value: s, label: capitalize(s) }))} />}
        </Form>
      </Modal>
    </div>
  )
}