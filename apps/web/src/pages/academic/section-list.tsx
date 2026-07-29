import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { sectionApi, type SectionListParams } from '../../api/academic/section-api'
import { classApi } from '../../api/academic/class-api'
import type { SectionResponse, SectionCreate, SectionUpdate, ClassResponse } from '../../api/generated/types'
import { Card, Table, Pagination, Input, Select, Button, Badge, Modal, Form, Alert, EmptyState, ErrorState, useToast } from '../../components/ui'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'
import { ACADEMIC_STATUSES, capitalize } from '../../lib/utils'

type SectionFormData = { name: string; class_id: number | null; status?: string | null }

const statusBadge: Record<string, 'success' | 'warning' | 'danger' | 'info'> = { active: 'success', inactive: 'danger' }

const columns = [
  { key: 'name', header: 'Name' },
  { key: 'class_id', header: 'Class ID', render: (s: SectionResponse) => `Class #${s.class_id}` },
  { key: 'status', header: 'Status', render: (s: SectionResponse) => <Badge variant={statusBadge[s.status] || 'default'}>{capitalize(s.status)}</Badge> },
]

export function SectionListPage() {
  const navigate = useNavigate()
  const { showToast } = useToast()

  useKeyboardShortcut({ 'n': () => openCreateModal() }, [])
  const [data, setData] = useState<SectionResponse[]>([])
  const [total, setTotal] = useState(0); const [pages, setPages] = useState(0)
  const [page, setPage] = useState(1); const [size, setSize] = useState(20)
  const [classFilter, setClassFilter] = useState(''); const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true); const [error, setError] = useState<string | null>(null)
  const [classes, setClasses] = useState<ClassResponse[]>([])

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<SectionResponse | null>(null)
  const [formData, setFormData] = useState<SectionFormData>({ name: '', class_id: null })
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false); const [apiError, setApiError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  useEffect(() => { classApi.list({ size: 100 }).then((r) => setClasses(r.items)).catch(() => {}) }, [])

  const fetch = useCallback(async (params: SectionListParams) => {
    const fetchId = ++fetchIdRef.current; setLoading(true); setError(null)
    try {
      const result = await sectionApi.list(params)
      if (fetchId === fetchIdRef.current) { setData(result.items); setTotal(result.total); setPages(result.pages); setPage(result.page) }
    } catch (err: any) { if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load sections')
    } finally { if (fetchId === fetchIdRef.current) setLoading(false) }
  }, [])

  useEffect(() => { fetch({ page, size, class_id: classFilter ? Number(classFilter) : undefined, status: statusFilter || undefined }) }, [page, size, classFilter, statusFilter, fetch])

  const openCreateModal = () => { setEditing(null); setFormData({ name: '', class_id: classFilter ? Number(classFilter) : null }); setFormErrors({}); setApiError(null); setModalOpen(true) }
  const openEditModal = (s: SectionResponse) => { setEditing(s); setFormData({ name: s.name, class_id: s.class_id, status: s.status }); setFormErrors({}); setApiError(null); setModalOpen(true) }

  const validate = (): boolean => { const e: Record<string, string> = {}; if (!formData.name.trim()) e.name = 'Name is required'; if (!formData.class_id) e.class_id = 'Class is required'; setFormErrors(e); return Object.keys(e).length === 0 }

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault(); if (!validate()) return; setSaving(true); setApiError(null)
    try {
      if (editing) {
        const updated = await sectionApi.update(editing.id, { name: formData.name || null, class_id: formData.class_id, status: formData.status || null })
        setData((prev) => prev.map((s) => (s.id === updated.id ? updated : s))); showToast('Section updated', 'success')
      } else {
        const created = await sectionApi.create({ name: formData.name, class_id: formData.class_id! })
        setData((prev) => [created, ...prev]); setTotal((t) => t + 1); showToast('Section created', 'success')
      }
      setModalOpen(false)
    } catch (err: any) { setApiError(err?.detail || 'Failed to save')
    } finally { setSaving(false) }
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-[var(--color-brand-accent)] tracking-wide mb-1">Academics</p>
          <h1 className="text-2xl font-bold text-[var(--color-text-primary)] tracking-tight">Sections</h1>
          <p className="text-sm text-[var(--color-text-tertiary)] mt-1">{total} section{total !== 1 ? 's' : ''}</p>
        </div>
        <Button onClick={openCreateModal}>
          Add Section
          <kbd className="ml-2 hidden sm:inline-flex items-center px-1.5 py-0.5 rounded bg-white/20 text-[10px] font-medium text-white/80">N</kbd>
        </Button>
      </div>
      <div className="flex items-center gap-4">
        <Select options={classes.map((c) => ({ value: String(c.id), label: c.name }))} placeholder="All classes" value={classFilter}
          onChange={(e) => { setClassFilter(e.target.value); setPage(1) }} />
        <Select options={ACADEMIC_STATUSES.map((s) => ({ value: s, label: capitalize(s) }))} placeholder="All statuses" value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }} />
      </div>
      <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
        {error ? <ErrorState message={error} onRetry={() => fetch({ page, size, class_id: classFilter ? Number(classFilter) : undefined, status: statusFilter || undefined })} /> : (
          <>
            <Table columns={[...columns, { key: 'actions', header: 'Actions', render: (s: SectionResponse) => (<div className="flex gap-2" onClick={(e) => e.stopPropagation()}><Button variant="ghost" size="sm" onClick={() => openEditModal(s)}>Edit</Button></div>) }]} data={data} keyExtractor={(s) => s.id} emptyMessage="No sections found." loading={loading} />
            <Pagination page={page} size={size} total={total} pages={pages} onPageChange={setPage} onSizeChange={(s) => { setSize(s); setPage(1) }} />
          </>
        )}
      </Card>
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Edit Section' : 'Add Section'}
        footer={<>            <Button variant="outline" onClick={() => setModalOpen(false)}>Cancel</Button><Button onClick={handleSubmit} loading={saving}>{editing ? 'Save Changes' : 'Create'}</Button></>}
      >
        {apiError && <Alert variant="error" onClose={() => setApiError(null)}>{apiError}</Alert>}
        <Form onSubmit={handleSubmit}>
          <Input label="Name" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} error={formErrors.name} required />
          <Select label="Class" value={String(formData.class_id ?? '')} onChange={(e) => setFormData({ ...formData, class_id: e.target.value ? Number(e.target.value) : null })} error={formErrors.class_id}
            options={classes.map((c) => ({ value: String(c.id), label: c.name }))} placeholder="Select class" />
          {editing && <Select label="Status" value={formData.status ?? editing.status} onChange={(e) => setFormData({ ...formData, status: e.target.value })} options={ACADEMIC_STATUSES.map((s) => ({ value: s, label: capitalize(s) }))} />}
        </Form>
      </Modal>
    </div>
  )
}