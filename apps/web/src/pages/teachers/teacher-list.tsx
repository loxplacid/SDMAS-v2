import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { teacherApi } from '../../api/academic/teacher-api'
import type { TeacherResponse } from '../../api/generated/types'
import { Button, Modal, Form, Input, Select, Alert, Badge, useToast } from '../../components/ui'
import type { Column } from '../../components/ui/table'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'
import { useDelight } from '../../components/delight/delight-provider'
import { DataWorkspace, useWorkspace } from '../../components/data-workspace'
import { TEACHER_STATUSES, capitalize } from '../../lib/utils'

const statusBadge: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
  active: 'success',
  inactive: 'danger',
}

export function TeacherListPage() {
  const navigate = useNavigate()
  const { showToast } = useToast()
  const { celebrate } = useDelight()
  const searchInputRef = useRef<HTMLInputElement>(null)

  // ── data (local mode: the staff directory is fetched once) ──
  const [data, setData] = useState<TeacherResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  const fetchTeachers = useCallback(async (showLoading: boolean) => {
    const fetchId = ++fetchIdRef.current
    if (showLoading) setLoading(true)
    setError(null)
    try {
      // Staff is a bounded directory: one fetch, all filtering/sorting local.
      const result = await teacherApi.list({ page: 1, size: 10000 })
      if (fetchId === fetchIdRef.current) setData(result.items)
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load teachers')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchTeachers(true)
  }, [fetchTeachers])

  // ── create / edit modal ──
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<TeacherResponse | null>(null)
  const [formData, setFormData] = useState<{ first_name: string; last_name: string; employee_number: string; email: string | null; status?: string | null }>({ first_name: '', last_name: '', employee_number: '', email: null })
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)

  const openCreateModal = () => {
    setEditing(null)
    setFormData({ first_name: '', last_name: '', employee_number: '', email: null })
    setFormErrors({}); setApiError(null); setModalOpen(true)
  }

  const openEditModal = (t: TeacherResponse) => {
    setEditing(t)
    setFormData({ first_name: t.first_name, last_name: t.last_name, employee_number: t.employee_number, email: t.email, status: t.status })
    setFormErrors({}); setApiError(null); setModalOpen(true)
  }

  // Columns live inside the component: the actions column binds `navigate`
  // and the modal handlers.
  const columns = useMemo<Column<TeacherResponse>[]>(
    () => [
      { key: 'employee_number', header: 'Employee #', type: 'text', sortable: true },
      { key: 'first_name', header: 'First Name', type: 'text', sortable: true },
      { key: 'last_name', header: 'Last Name', type: 'text', sortable: true },
      { key: 'email', header: 'Email', type: 'text', render: (t) => t.email || '-', hideOnMobile: true },
      {
        key: 'status',
        header: 'Status',
        type: 'status',
        sortable: true,
        render: (t) => <Badge variant={statusBadge[t.status] || 'neutral'}>{capitalize(t.status)}</Badge>,
      },
      {
        key: 'actions',
        header: '',
        type: 'actions',
        render: (t) => (
          <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
            <Button variant="ghost" size="sm" onClick={() => navigate(`/teachers/${t.id}/360`)} title="Open Teacher 360 view">
              360
            </Button>
            <Button variant="ghost" size="sm" onClick={() => openEditModal(t)}>
              Edit
            </Button>
          </div>
        ),
      },
    ],
    [navigate]
  )

  const workspace = useWorkspace<TeacherResponse>({
    viewKey: 'teachers',
    columns,
    defaultPageSize: 20,
  })

  // ── keyboard: `/` focuses the filter rail search, `n` creates ──
  useKeyboardShortcut({
    '/': (e) => {
      e.preventDefault()
      searchInputRef.current?.focus()
    },
    n: () => openCreateModal(),
  }, [])

  const validate = (): boolean => {
    const e: Record<string, string> = {}
    if (!formData.first_name.trim()) e.first_name = 'First name is required'
    if (!formData.last_name.trim()) e.last_name = 'Last name is required'
    if (!editing && !formData.employee_number.trim()) e.employee_number = 'Employee number is required'
    setFormErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault()
    if (!validate()) return
    setSaving(true); setApiError(null)
    try {
      if (editing) {
        const updated = await teacherApi.update(editing.id, { first_name: formData.first_name || null, last_name: formData.last_name || null, email: formData.email, status: formData.status || null })
        setData((prev) => prev.map((t) => (t.id === updated.id ? updated : t)))
        showToast('Teacher updated', 'success')
      } else {
        const created = await teacherApi.create({ first_name: formData.first_name, last_name: formData.last_name, employee_number: formData.employee_number, email: formData.email })
        setData((prev) => [created, ...prev])
        showToast('Teacher created', 'success')
        // Glint §5.1 — first-of-kind milestone (registry-gated, once per campus).
        celebrate('first-teacher')
      }
      setModalOpen(false)
    } catch (err: any) {
      setApiError(err?.detail || 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      <DataWorkspace
        workspace={workspace}
        title="Teachers"
        description={
          data.length > 0
            ? `${data.length} teacher${data.length !== 1 ? 's' : ''} on staff. Manage records, employment status and contact details.`
            : 'Build your staff directory by adding teacher records.'
        }
        columns={columns}
        keyExtractor={(t) => t.id}
        data={data}
        total={data.length}
        pages={Math.ceil(data.length / workspace.size)}
        loading={loading}
        error={error}
        onRetry={() => fetchTeachers(true)}
        onRefresh={() => fetchTeachers(false)}
        mode="local"
        filterPlaceholder="Search by name, employee # or email…"
        onRowClick={(t) => navigate(`/teachers/${t.id}`)}
        primaryAction={
          <Button onClick={openCreateModal}>
            Add Teacher
            <kbd className="ml-2 hidden sm:inline-flex items-center px-1.5 py-0.5 rounded bg-white/20 text-[10px] font-medium text-white/80">N</kbd>
          </Button>
        }
        empty={{
          title: 'No teachers yet',
          description: 'Build your staff directory by adding teacher records.',
          actionLabel: 'Add Teacher',
          onAction: openCreateModal,
        }}
        searchInputRef={searchInputRef}
      />

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
