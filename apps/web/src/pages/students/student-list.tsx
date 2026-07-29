import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { studentApi, type StudentListParams } from '../../api/student/student-api'
import type { StudentResponse } from '../../api/generated/types'
import { Card, Table, Pagination, Input, Select, Button, Modal, Form, Alert, ErrorState, useToast, StatusBadge, SearchInput, ConfirmDialog, EmptyState, getEmptyState } from '../../components/ui'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'
import { STUDENT_STATUSES, capitalize, debounce } from '../../lib/utils'

export function StudentListPage() {
  const navigate = useNavigate()
  const { showToast } = useToast()
  const searchRef = useRef<HTMLInputElement>(null)

  useKeyboardShortcut({
    '/': (e) => { e.preventDefault(); searchRef.current?.focus(); },
    'n': () => openCreateModal(),
  }, [])

  const [data, setData] = useState<StudentResponse[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(0)
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(20)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [modalOpen, setModalOpen] = useState(false)
  const [editingStudent, setEditingStudent] = useState<StudentResponse | null>(null)
  const [formData, setFormData] = useState<{ first_name: string; last_name: string; student_number: string; email: string | null; date_of_birth: string | null; status?: string | null }>({ first_name: '', last_name: '', student_number: '', email: null, date_of_birth: null })
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)

  const [deleteConfirm, setDeleteConfirm] = useState<StudentResponse | null>(null)
  const [deleting, setDeleting] = useState(false)

  const fetchIdRef = useRef(0)

  const fetchStudents = useCallback(async (params: StudentListParams) => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)
    try {
      const result = await studentApi.list(params)
      if (fetchId === fetchIdRef.current) {
        setData(result.items)
        setTotal(result.total)
        setPages(result.pages)
        setPage(result.page)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load students')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStudents({ page, size, search: search || undefined, status: statusFilter || undefined })
  }, [page, size, statusFilter, fetchStudents])

  const debouncedSearch = useCallback(
    debounce((value: string) => { setSearch(value); setPage(1) }, 300), []
  )

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    debouncedSearch(e.target.value)
  }

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
        setData((prev) => [created, ...prev]); setTotal((t) => t + 1)
        showToast('Student created', 'success')
      }
      setModalOpen(false)
    } catch (err: any) { setApiError(err?.detail || 'Failed to save student')
    } finally { setSaving(false) }
  }

  const handleDelete = async () => {
    if (!deleteConfirm) return
    setDeleting(true)
    try {
      await studentApi.delete(deleteConfirm.id)
      setData((prev) => prev.filter((s) => s.id !== deleteConfirm.id))
      setTotal((t) => t - 1)
      showToast('Student deleted', 'success')
      setDeleteConfirm(null)
    } catch (err: any) { showToast(err?.detail || 'Failed to delete student', 'error')
    } finally { setDeleting(false) }
  }

  const emptyState = getEmptyState('students')

  return (
    <div className="space-y-8 animate-fade-in-up">
      {/* Narrative header */}
      <div>
        <p className="text-sm font-medium text-[var(--color-brand-accent)] tracking-wide mb-1">People</p>
        <h1 className="text-3xl lg:text-4xl font-extrabold text-[var(--color-text-primary)] tracking-tight leading-tight">
          Students
        </h1>
        <p className="text-base text-[var(--color-text-tertiary)] mt-2 max-w-xl">
          {total > 0
            ? `${total} student${total !== 1 ? 's' : ''} across your school. Manage records, track enrollment, and maintain student information.`
            : 'Build your student directory. Start by adding student records to your school.'}
        </p>
      </div>

      {/* Search & filters bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3 flex-1 max-w-lg">
          <div className="flex-1 min-w-[200px]">
            <SearchInput
              ref={searchRef}
              placeholder="Search by name or student #..."
              onChange={handleSearchChange}
              showKbdHint
            />
          </div>
          <Select
            options={STUDENT_STATUSES.map((s) => ({ value: s, label: capitalize(s) }))}
            placeholder="All statuses"
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
          />
        </div>
        <Button onClick={openCreateModal} className="relative">
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Add Student
          <kbd className="ml-2 hidden sm:inline-flex items-center px-1.5 py-0.5 rounded bg-white/20 text-[10px] font-medium text-white/80">N</kbd>
        </Button>
      </div>

      {/* Data table area */}
      <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] overflow-hidden">
        {loading ? (
          <Table columns={[]} data={[]} loading={true} keyExtractor={() => ''} emptyMessage="" />
        ) : error ? (
          <ErrorState message={error} onRetry={() => fetchStudents({ page, size, search: search || undefined, status: statusFilter || undefined })} />
        ) : data.length === 0 ? (
          <div className="p-8">
            <EmptyState
              title={emptyState.title}
              description={emptyState.description}
              action={{ label: 'Add Student', onClick: openCreateModal }}
            />
          </div>
        ) : (
          <>
            <Table
              columns={[
                { key: 'student_number', header: 'Student #' },
                { key: 'first_name', header: 'First Name' },
                { key: 'last_name', header: 'Last Name' },
                { key: 'email', header: 'Email', render: (s: StudentResponse) => s.email || '-' },
                { key: 'status', header: 'Status', render: (s: StudentResponse) => <StatusBadge status={s.status} /> },
                { key: 'actions', header: 'Actions', render: (s: StudentResponse) => (
                  <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                    <Button variant="outline" size="sm" onClick={() => openEditModal(s)}>Edit</Button>
                    <Button variant="danger" size="sm" onClick={() => setDeleteConfirm(s)}>Delete</Button>
                  </div>
                )},
              ]}
              data={data}
              keyExtractor={(s) => s.id}
              emptyMessage={emptyState.title}
              onRowClick={(s) => navigate(`/students/${s.id}`)}
            />
            <Pagination page={page} size={size} total={total} pages={pages} onPageChange={setPage} onSizeChange={(s) => { setSize(s); setPage(1) }} />
          </>
        )}
      </div>

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
            <Select label="Status" value={formData.status ?? editingStudent.status} onChange={(e) => setFormData(s => ({ ...s, status: e.target.value }))} options={STUDENT_STATUSES.map((s) => ({ value: s, label: capitalize(s) }))} />
          )}
        </Form>
      </Modal>

      <ConfirmDialog open={!!deleteConfirm} onClose={() => setDeleteConfirm(null)} onConfirm={handleDelete}
        title="Delete Student" message={`Are you sure you want to delete ${deleteConfirm?.first_name} ${deleteConfirm?.last_name}? This action cannot be undone.`}
        confirmLabel="Delete" variant="danger" loading={deleting} />
    </div>
  )
}
