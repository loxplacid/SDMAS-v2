import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { studentApi, type StudentListParams } from '../../api/student/student-api'
import type { StudentResponse } from '../../api/generated/types'

type StudentFormData = {
  first_name: string
  last_name: string
  student_number: string
  email: string | null
  date_of_birth: string | null
  status?: string | null
}
import { Card, Table, Pagination, Input, Select, Button, Badge, Modal, Form, Alert, Loading, EmptyState, ErrorState, useToast } from '../../components/ui'
import { STUDENT_STATUSES, capitalize, debounce } from '../../lib/utils'

const statusBadge: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
  active: 'success',
  inactive: 'danger',
  graduated: 'info',
  transferred: 'warning',
}

const columns = [
  { key: 'student_number', header: 'Student #' },
  { key: 'first_name', header: 'First Name' },
  { key: 'last_name', header: 'Last Name' },
  {
    key: 'status',
    header: 'Status',
    render: (s: StudentResponse) => (
      <Badge variant={statusBadge[s.status] || 'default'}>{capitalize(s.status)}</Badge>
    ),
  },
  {
    key: 'email',
    header: 'Email',
    render: (s: StudentResponse) => s.email || '-',
  },
]

export function StudentListPage() {
  const navigate = useNavigate()
  const { showToast } = useToast()

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
  const [formData, setFormData] = useState<StudentFormData>({
    first_name: '',
    last_name: '',
    student_number: '',
    email: null,
    date_of_birth: null,
  })
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)

  const searchInputRef = useRef<HTMLInputElement>(null)
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
      if (fetchId === fetchIdRef.current) {
        setError(err?.detail || 'Failed to load students')
      }
    } finally {
      if (fetchId === fetchIdRef.current) {
        setLoading(false)
      }
    }
  }, [])

  useEffect(() => {
    fetchStudents({ page, size, search: search || undefined, status: statusFilter || undefined })
  }, [page, size, statusFilter, fetchStudents])

  const debouncedSearch = useCallback(
    debounce((value: string) => {
      setSearch(value)
      setPage(1)
    }, 300),
    []
  )

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    debouncedSearch(e.target.value)
  }

  const openCreateModal = () => {
    setEditingStudent(null)
    setFormData({ first_name: '', last_name: '', student_number: '', email: null, date_of_birth: null })
    setFormErrors({})
    setApiError(null)
    setModalOpen(true)
  }

  const openEditModal = (student: StudentResponse) => {
    setEditingStudent(student)
    setFormData({
      first_name: student.first_name,
      last_name: student.last_name,
      student_number: student.student_number,
      email: student.email,
      date_of_birth: student.date_of_birth,
      status: student.status,
    })
    setFormErrors({})
    setApiError(null)
    setModalOpen(true)
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
    setSaving(true)
    setApiError(null)
    try {
      if (editingStudent) {
        const updated = await studentApi.update(editingStudent.id, {
          first_name: formData.first_name || null,
          last_name: formData.last_name || null,
          email: formData.email,
          status: formData.status || null,
          date_of_birth: formData.date_of_birth,
        })
        setData((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
        showToast('Student updated', 'success')
      } else {
        const created = await studentApi.create({
          first_name: formData.first_name,
          last_name: formData.last_name,
          student_number: formData.student_number,
          email: formData.email,
          date_of_birth: formData.date_of_birth,
        })
        setData((prev) => [created, ...prev])
        setTotal((t) => t + 1)
        showToast('Student created', 'success')
      }
      setModalOpen(false)
    } catch (err: any) {
      setApiError(err?.detail || 'Failed to save student')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (student: StudentResponse) => {
    if (!confirm(`Delete student ${student.first_name} ${student.last_name}?`)) return
    try {
      await studentApi.delete(student.id)
      setData((prev) => prev.filter((s) => s.id !== student.id))
      setTotal((t) => t - 1)
      showToast('Student deleted', 'success')
    } catch (err: any) {
      showToast(err?.detail || 'Failed to delete student', 'error')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Students</h1>
          <p className="text-gray-500 mt-1">{total} student{total !== 1 ? 's' : ''}</p>
        </div>
        <Button onClick={openCreateModal}>Add Student</Button>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex-1 max-w-sm">
          <Input
            placeholder="Search by name or student #..."
            onChange={handleSearchChange}
            ref={searchInputRef}
          />
        </div>
        <Select
          options={STUDENT_STATUSES.map((s) => ({ value: s, label: capitalize(s) }))}
          placeholder="All statuses"
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
        />
      </div>

      <Card>
        {loading ? (
          <Loading text="Loading students..." />
        ) : error ? (
          <ErrorState message={error} onRetry={() => fetchStudents({ page, size, search: search || undefined, status: statusFilter || undefined })} />
        ) : (
          <>
            <Table
              columns={[
                ...columns,
                {
                  key: 'actions',
                  header: 'Actions',
                  render: (student: StudentResponse) => (
                    <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                      <Button variant="ghost" size="sm" onClick={() => openEditModal(student)}>Edit</Button>
                      <Button variant="danger" size="sm" onClick={() => handleDelete(student)}>Delete</Button>
                    </div>
                  ),
                },
              ]}
              data={data}
              keyExtractor={(s) => s.id}
              emptyMessage="No students found matching your criteria."
              onRowClick={(s) => navigate(`/students/${s.id}`)}
            />
            <Pagination
              page={page}
              size={size}
              total={total}
              pages={pages}
              onPageChange={setPage}
              onSizeChange={(s) => { setSize(s); setPage(1) }}
            />
          </>
        )}
      </Card>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editingStudent ? 'Edit Student' : 'Add Student'}
        footer={
          <>
            <Button variant="secondary" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button onClick={handleSubmit} loading={saving}>
              {editingStudent ? 'Save Changes' : 'Create Student'}
            </Button>
          </>
        }
      >
        {apiError && <Alert variant="error" onClose={() => setApiError(null)}>{apiError}</Alert>}
        <Form onSubmit={handleSubmit}>
          <Input
            label="First Name"
            value={formData.first_name}
            onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
            error={formErrors.first_name}
            required={!editingStudent}
          />
          <Input
            label="Last Name"
            value={formData.last_name}
            onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
            error={formErrors.last_name}
            required={!editingStudent}
          />
          <Input
            label="Student Number"
            value={formData.student_number}
            onChange={(e) => setFormData({ ...formData, student_number: e.target.value })}
            error={formErrors.student_number}
            required={!editingStudent}
            disabled={!!editingStudent}
          />
          <Input
            label="Email"
            type="email"
            value={formData.email ?? ''}
            onChange={(e) => setFormData({ ...formData, email: e.target.value || null })}
          />
          <Input
            label="Date of Birth"
            type="date"
            value={formData.date_of_birth ?? ''}
            onChange={(e) => setFormData({ ...formData, date_of_birth: e.target.value || null })}
          />
          {editingStudent && (
            <Select
              label="Status"
              value={formData.status ?? editingStudent.status}
              onChange={(e) => setFormData({ ...formData, status: e.target.value })}
              options={STUDENT_STATUSES.map((s) => ({ value: s, label: capitalize(s) }))}
            />
          )}
        </Form>
      </Modal>
    </div>
  )
}