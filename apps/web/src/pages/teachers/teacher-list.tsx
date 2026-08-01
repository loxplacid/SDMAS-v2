import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { teacherApi, type TeacherListParams } from '../../api/academic/teacher-api'
import type { TeacherResponse, TeacherCreate, TeacherUpdate } from '../../api/generated/types'
import { Card, Table, Pagination, Input, Select, Button, Badge, Modal, Form, Alert, EmptyState, ErrorState, useToast } from '../../components/ui'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'
import { TEACHER_STATUSES, capitalize, debounce } from '../../lib/utils'

const statusBadge: Record<string, 'success' | 'warning' | 'danger' | 'info'> = { active: 'success', inactive: 'danger' }

const columns = [
  { key: 'employee_number', header: 'Employee #' },
  { key: 'first_name', header: 'First Name' },
  { key: 'last_name', header: 'Last Name' },
  { key: 'email', header: 'Email', render: (t: TeacherResponse) => t.email || '-' },
  { key: 'status', header: 'Status', render: (t: TeacherResponse) => <Badge variant={statusBadge[t.status] || 'default'}>{capitalize(t.status)}</Badge> },
]

export function TeacherListPage() {
  const navigate = useNavigate()
  const { showToast } = useToast()

  useKeyboardShortcut({ 'n': () => openCreateModal() }, [])
  const [data, setData] = useState<TeacherResponse[]>([])
  const [total, setTotal] = useState(0); const [pages, setPages] = useState(0)
  const [page, setPage] = useState(1); const [size, setSize] = useState(20)
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true); const [error, setError] = useState<string | null>(null)

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<TeacherResponse | null>(null)
  const [formData, setFormData] = useState<{ first_name: string; last_name: string; employee_number: string; email: string | null; status?: string | null }>({ first_name: '', last_name: '', employee_number: '', email: null })
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false); const [apiError, setApiError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  const fetch = useCallback(async (params: TeacherListParams) => {
    const fetchId = ++fetchIdRef.current; setLoading(true); setError(null)
    try {
      const result = await teacherApi.list(params)
      if (fetchId === fetchIdRef.current) { setData(result.items); setTotal(result.total); setPages(result.pages); setPage(result.page) }
    } catch (err: any) { if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load teachers')
    } finally { if (fetchId === fetchIdRef.current) setLoading(false) }
  }, [])

  useEffect(() => { fetch({ page, size, status: statusFilter || undefined }) }, [page, size, statusFilter, fetch])

  const openCreateModal = () => { setEditing(null); setFormData({ first_name: '', last_name: '', employee_number: '', email: null }); setFormErrors({}); setApiError(null); setModalOpen(true) }
  const openEditModal = (t: TeacherResponse) => { setEditing(t); setFormData({ first_name: t.first_name, last_name: t.last_name, employee_number: t.employee_number, email: t.email, status: t.status }); setFormErrors({}); setApiError(null); setModalOpen(true) }
  const validate = (): boolean => { const e: Record<string, string> = {}; if (!formData.first_name.trim()) e.first_name = 'First name is required'; if (!formData.last_name.trim()) e.last_name = 'Last name is required'; if (!editing && !formData.employee_number.trim()) e.employee_number = 'Employee number is required'; setFormErrors(e); return Object.keys(e).length === 0 }

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault(); if (!validate()) return; setSaving(true); setApiError(null)
    try {
      if (editing) {
        const updated = await teacherApi.update(editing.id, { first_name: formData.first_name || null, last_name: formData.last_name || null, email: formData.email, status: formData.status || null })
        setData((prev) => prev.map((t) => (t.id === updated.id ? updated : t))); showToast('Teacher updated', 'success')
      } else {
        const created = await teacherApi.create({ first_name: formData.first_name, last_name: formData.last_name, employee_number: formData.employee_number, email: formData.email })
        setData((prev) => [created, ...prev]); setTotal((t) => t + 1); showToast('Teacher created', 'success')
      }
      setModalOpen(false)
    } catch (err: any) { setApiError(err?.detail || 'Failed to save')
    } finally { setSaving(false) }
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-[var(--color-brand-accent)] tracking-wide mb-1">People</p>
          <h1 className="text-2xl font-bold text-[var(--color-text-primary)] tracking-tight">Teachers</h1>
          <p className="text-sm text-[var(--color-text-tertiary)] mt-1">{total} teacher{total !== 1 ? 's' : ''}</p>
        </div>
        <Button onClick={openCreateModal}>
          Add Teacher
          <kbd className="ml-2 hidden sm:inline-flex items-center px-1.5 py-0.5 rounded bg-white/20 text-[10px] font-medium text-white/80">N</kbd>
        </Button>
      </div>
      <div className="flex items-center gap-4">
        <Select options={TEACHER_STATUSES.map((s) => ({ value: s, label: capitalize(s) }))} placeholder="All statuses" value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }} />
      </div>
      <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
        {error ? <ErrorState message={error} onRetry={() => fetch({ page, size, status: statusFilter || undefined })} /> : (
          <>
            <Table columns={[...columns, { key: 'actions', header: 'Actions', render: (t: TeacherResponse) => (<div className="flex gap-2" onClick={(e) => e.stopPropagation()}><Button variant="ghost" size="sm" onClick={() => navigate(`/teachers/${t.id}/360`)} title="Open Teacher 360 view">360</Button><Button variant="ghost" size="sm" onClick={() => openEditModal(t)}>Edit</Button></div>) }]} data={data} keyExtractor={(t) => t.id} emptyMessage="No teachers found." onRowClick={(t) => navigate(`/teachers/${t.id}`)} loading={loading} />
            <Pagination page={page} size={size} total={total} pages={pages} onPageChange={setPage} onSizeChange={(s) => { setSize(s); setPage(1) }} />
          </>
        )}
      </Card>
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Edit Teacher' : 'Add Teacher'}
        footer={<><Button variant="outline" onClick={() => setModalOpen(false)}>Cancel</Button><Button onClick={handleSubmit} loading={saving}>{editing ? 'Save Changes' : 'Create'}</Button></>}
      >
        {apiError && <Alert variant="error" onClose={() => setApiError(null)}>{apiError}</Alert>}
        <Form onSubmit={handleSubmit}>
          <Input label="First Name" value={formData.first_name} onChange={(e) => setFormData({ ...formData, first_name: e.target.value })} error={formErrors.first_name} required />
          <Input label="Last Name" value={formData.last_name} onChange={(e) => setFormData({ ...formData, last_name: e.target.value })} error={formErrors.last_name} required />
          <Input label="Employee Number" value={formData.employee_number} onChange={(e) => setFormData({ ...formData, employee_number: e.target.value })} error={formErrors.employee_number} required={!editing} disabled={!!editing} />
          <Input label="Email" type="email" value={formData.email ?? ''} onChange={(e) => setFormData({ ...formData, email: e.target.value || null })} />
          {editing && <Select label="Status" value={formData.status ?? editing.status} onChange={(e) => setFormData({ ...formData, status: e.target.value })} options={TEACHER_STATUSES.map((s) => ({ value: s, label: capitalize(s) }))} />}
        </Form>
      </Modal>
    </div>
  )
}