import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { studentApi } from '../../api/student/student-api'
import { exportApi } from '../../api/reports/export-api'
import type { StudentResponse } from '../../api/generated/types'
import { Button, Modal, Form, Input, Select, Alert, StatusBadge, ConfirmDialog, useToast } from '../../components/ui'
import type { Column } from '../../components/ui/table'
import { applyFilters } from '../../components/ui/table/filter-model'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'
import { useAuth } from '../../api/auth/auth-context'
import { useDelight } from '../../components/delight/delight-provider'
import { DataWorkspace, useWorkspace } from '../../components/data-workspace'
import { STUDENT_STATUSES, capitalize } from '../../lib/utils'

/** Roles that may delete student records. */
const BULK_DELETE_ROLES = new Set(['admin', 'principal'])

export function StudentListPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const { showToast } = useToast()
  const { celebrate } = useDelight()
  const searchInputRef = useRef<HTMLInputElement>(null)

  const canBulkDelete = user?.role ? BULK_DELETE_ROLES.has(user.role) : false

  // ── data (local mode: the full directory is fetched once) ──
  const [data, setData] = useState<StudentResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  const fetchStudents = useCallback(async (showLoading: boolean) => {
    const fetchId = ++fetchIdRef.current
    if (showLoading) setLoading(true)
    setError(null)
    try {
      // Directory-scale dataset: one fetch, all filtering/sorting local.
      // NOTE: capped at 10,000 rows — a larger school would need paged
      // loading or server-side sort support (see P8 known limitations).
      const result = await studentApi.list({ page: 1, size: 10000 })
      if (fetchId === fetchIdRef.current) setData(result.items)
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load students')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStudents(true)
  }, [fetchStudents])

  // ── create / edit modal ──
  const [modalOpen, setModalOpen] = useState(false)
  const [editingStudent, setEditingStudent] = useState<StudentResponse | null>(null)
  const [formData, setFormData] = useState<{ first_name: string; last_name: string; student_number: string; email: string | null; date_of_birth: string | null; status?: string | null }>({ first_name: '', last_name: '', student_number: '', email: null, date_of_birth: null })
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)

  const [deleteConfirm, setDeleteConfirm] = useState<StudentResponse | null>(null)

  const openCreateModal = () => {
    setEditingStudent(null)
    setFormData({ first_name: '', last_name: '', student_number: '', email: null, date_of_birth: null })
    setFormErrors({}); setApiError(null); setModalOpen(true)
  }

  const openEditModal = (student: StudentResponse) => {
    setEditingStudent(student)
    setFormData({ first_name: student.first_name, last_name: student.last_name, student_number: student.student_number, email: student.email, date_of_birth: student.date_of_birth })
    setFormErrors({}); setApiError(null); setModalOpen(true)
  }

  // Columns live inside the component: the actions column binds the modal
  // handlers, so it cannot be a module-level constant.
  const columns = useMemo<Column<StudentResponse>[]>(
    () => [
      { key: 'student_number', header: 'Student #', type: 'text', sortable: true },
      { key: 'first_name', header: 'First Name', type: 'text', sortable: true },
      { key: 'last_name', header: 'Last Name', type: 'text', sortable: true },
      {
        key: 'email',
        header: 'Email',
        type: 'text',
        render: (s) => s.email || '-',
        hideOnMobile: true,
      },
      {
        key: 'status',
        header: 'Status',
        type: 'status',
        sortable: true,
        render: (s) => <StatusBadge status={s.status} />,
      },
      {
        key: 'actions',
        header: '',
        type: 'actions',
        render: (s) => (
          <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
            <Button variant="outline" size="sm" onClick={() => openEditModal(s)}>
              Edit
            </Button>
            <Button variant="ghost" size="sm" className="text-[var(--color-danger)]" onClick={() => setDeleteConfirm(s)}>
              Delete
            </Button>
          </div>
        ),
      },
    ],
    []
  )

  const workspace = useWorkspace<StudentResponse>({
    viewKey: 'students',
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
    const errors: Record<string, string> = {}
    if (!editingStudent) {
      if (!formData.first_name) errors.first_name = 'First name is required'
      if (!formData.last_name) errors.last_name = 'Last name is required'
      if (!formData.student_number) errors.student_number = 'Student number is required'
    }
    setFormErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!validate()) return
    setSaving(true); setApiError(null)
    try {
      if (editingStudent) {
        const updated = await studentApi.update(editingStudent.id, { first_name: formData.first_name || null, last_name: formData.last_name || null, email: formData.email, status: formData.status || null, date_of_birth: formData.date_of_birth })
        setData((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
        showToast('Student updated', 'success')
      } else {
        const created = await studentApi.create({ first_name: formData.first_name, last_name: formData.last_name, student_number: formData.student_number, email: formData.email, date_of_birth: formData.date_of_birth })
        setData((prev) => [created, ...prev])
        showToast('Student created', 'success')
        // Glint §5.1 — first-of-kind milestone (registry-gated, once per campus).
        celebrate('first-student')
      }
      setModalOpen(false)
    } catch (err: any) {
      setApiError(err?.detail || 'Failed to save student')
    } finally {
      setSaving(false)
    }
  }

  // ── single delete ──
  const [deleting, setDeleting] = useState(false)

  const handleDelete = async () => {
    if (!deleteConfirm) return
    setDeleting(true)
    try {
      await studentApi.delete(deleteConfirm.id)
      setData((prev) => prev.filter((s) => s.id !== deleteConfirm.id))
      showToast('Student deleted', 'success')
      setDeleteConfirm(null)
    } catch (err: any) {
      showToast(err?.detail || 'Failed to delete student', 'error')
    } finally {
      setDeleting(false)
    }
  }

  // ── bulk delete (role-gated, confirmation-gated) ──
  const [bulkConfirm, setBulkConfirm] = useState(false)
  const [bulkDeleting, setBulkDeleting] = useState(false)

  const handleBulkDelete = async () => {
    setBulkDeleting(true)
    try {
      // allSettled: a single failure must not report the whole batch as
      // failed — only the rows that actually deleted leave the table.
      const entries = Array.from(workspace.selection)
      const results = await Promise.allSettled(entries.map((id) => studentApi.delete(Number(id))))
      const deleted = new Set(entries.filter((_, i) => results[i].status === 'fulfilled'))
      const failed = entries.length - deleted.size
      setData((prev) => prev.filter((s) => !deleted.has(s.id)))
      workspace.clearSelection()
      setBulkConfirm(false)
      if (failed > 0) {
        showToast(`${deleted.size} deleted, ${failed} failed`, 'error')
      } else {
        showToast(`${deleted.size} student${deleted.size === 1 ? '' : 's'} deleted`, 'success')
      }
    } catch (err: any) {
      showToast(err?.detail || 'Failed to delete students', 'error')
    } finally {
      setBulkDeleting(false)
    }
  }

  // ── export the current filtered dataset (P8 §22) ──
  const [exporting, setExporting] = useState(false)
  const filteredCount = useMemo(
    () => applyFilters(data, workspace.filters, columns).length,
    [data, workspace.filters, columns]
  )

  const handleExport = async () => {
    setExporting(true)
    try {
      const blob = await exportApi.students({
        search: workspace.filters.query || undefined,
        status: workspace.filters.facets.status?.[0] || undefined,
      })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'students.csv'
      a.click()
      window.URL.revokeObjectURL(url)
      showToast(`Exporting ${filteredCount} student${filteredCount === 1 ? '' : 's'}`, 'success')
    } catch (err: any) {
      showToast(err?.detail || 'Export failed', 'error')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="space-y-4">
      <DataWorkspace
        workspace={workspace}
        title="Students"
        description={
          data.length > 0
            ? `${data.length} student${data.length !== 1 ? 's' : ''} across your school. Manage records, track enrollment, and maintain student information.`
            : 'Build your student directory by adding student records to your school.'
        }
        columns={columns}
        keyExtractor={(s) => s.id}
        data={data}
        total={data.length}
        pages={Math.ceil(data.length / workspace.size)}
        loading={loading}
        error={error}
        onRetry={() => fetchStudents(true)}
        onRefresh={() => fetchStudents(false)}
        mode="local"
        filterPlaceholder="Search by name, number or email…"
        onRowClick={(s) => navigate(`/students/${s.id}`)}
        primaryAction={
          <Button onClick={openCreateModal} className="relative">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Add Student
            <kbd className="ml-2 hidden sm:inline-flex items-center px-1.5 py-0.5 rounded bg-white/20 text-[10px] font-medium text-white/80">N</kbd>
          </Button>
        }
        toolbarActions={
          <Button variant="secondary" onClick={handleExport} loading={exporting}>
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Export
          </Button>
        }
        bulkActions={
          canBulkDelete
            ? (_selected, _clear) => (
                <Button variant="danger" size="sm" onClick={() => setBulkConfirm(true)}>
                  Delete selected
                </Button>
              )
            : undefined
        }
        empty={{
          title: 'No students yet',
          description: 'Build your student directory by adding student records to your school.',
          actionLabel: 'Add Student',
          onAction: openCreateModal,
        }}
        searchInputRef={searchInputRef}
      />

      <Modal open={modalOpen} onClose={() => setModalOpen(false)}
        title={editingStudent ? 'Edit Student' : 'Add Student'}
        footer={<><Button variant="outline" onClick={() => setModalOpen(false)}>Cancel</Button><Button onClick={handleSubmit} loading={saving}>{editingStudent ? 'Save Changes' : 'Create Student'}</Button></>}>
        {apiError && <Alert variant="error" onClose={() => setApiError(null)}>{apiError}</Alert>}
        <Form onSubmit={handleSubmit}>
          <Input label="First Name" value={formData.first_name} onChange={(e) => setFormData({ ...formData, first_name: e.target.value })} error={formErrors.first_name} required={!editingStudent} />
          <Input label="Last Name" value={formData.last_name} onChange={(e) => setFormData({ ...formData, last_name: e.target.value })} error={formErrors.last_name} required={!editingStudent} />
          <Input label="Student Number" value={formData.student_number} onChange={(e) => setFormData({ ...formData, student_number: e.target.value })} error={formErrors.student_number} required={!editingStudent} disabled={!!editingStudent} />
          <Input label="Email" type="email" value={formData.email ?? ''} onChange={(e) => setFormData({ ...formData, email: e.target.value || null })} />
          <Input label="Date of Birth" type="date" value={formData.date_of_birth ?? ''} onChange={(e) => setFormData({ ...formData, date_of_birth: e.target.value || null })} />
          {editingStudent && (
            <Select label="Status" value={formData.status ?? editingStudent.status} onChange={(e) => setFormData((s) => ({ ...s, status: e.target.value }))} options={STUDENT_STATUSES.map((s) => ({ value: s, label: capitalize(s) }))} />
          )}
        </Form>
      </Modal>

      <ConfirmDialog open={!!deleteConfirm} onClose={() => setDeleteConfirm(null)} onConfirm={handleDelete}
        title="Delete Student" message={`Are you sure you want to delete ${deleteConfirm?.first_name} ${deleteConfirm?.last_name}? This action cannot be undone.`}
        confirmLabel="Delete" variant="danger" loading={deleting} />

      <ConfirmDialog open={bulkConfirm} onClose={() => setBulkConfirm(false)} onConfirm={handleBulkDelete}
        title="Delete selected students" message={`Delete ${workspace.selection.size} selected student${workspace.selection.size === 1 ? '' : 's'}? This action cannot be undone.`}
        confirmLabel="Delete" variant="danger" loading={bulkDeleting} />
    </div>
  )
}
