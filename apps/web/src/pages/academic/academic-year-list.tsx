import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { academicYearApi, type AcademicYearListParams } from '../../api/academic/academic-year-api'
import type { AcademicYearResponse, AcademicYearCreate, AcademicYearUpdate } from '../../api/generated/types'
import { Card, Table, Pagination, Input, Select, Button, Badge, Modal, Form, Alert, Loading, EmptyState, ErrorState, useToast } from '../../components/ui'
import { ACADEMIC_STATUSES, capitalize, debounce } from '../../lib/utils'

type AcademicYearFormData = {
  name: string
  start_date: string
  end_date: string
  status?: string | null
}

const statusBadge: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
  active: 'success',
  inactive: 'danger',
}

const columns = [
  { key: 'name', header: 'Name' },
  {
    key: 'start_date',
    header: 'Start Date',
    render: (y: AcademicYearResponse) => y.start_date,
  },
  {
    key: 'end_date',
    header: 'End Date',
    render: (y: AcademicYearResponse) => y.end_date,
  },
  {
    key: 'status',
    header: 'Status',
    render: (y: AcademicYearResponse) => (
      <Badge variant={statusBadge[y.status] || 'default'}>{capitalize(y.status)}</Badge>
    ),
  },
]

export function AcademicYearListPage() {
  const navigate = useNavigate()
  const { showToast } = useToast()

  const [data, setData] = useState<AcademicYearResponse[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(0)
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(20)
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<AcademicYearResponse | null>(null)
  const [formData, setFormData] = useState<AcademicYearFormData>({ name: '', start_date: '', end_date: '' })
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)

  const fetchIdRef = useRef(0)

  const fetch = useCallback(async (params: AcademicYearListParams) => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)
    try {
      const result = await academicYearApi.list(params)
      if (fetchId === fetchIdRef.current) {
        setData(result.items); setTotal(result.total); setPages(result.pages); setPage(result.page)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load academic years')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetch({ page, size, status: statusFilter || undefined })
  }, [page, size, statusFilter, fetch])

  const openCreateModal = () => {
    setEditing(null)
    setFormData({ name: '', start_date: '', end_date: '' })
    setFormErrors({}); setApiError(null); setModalOpen(true)
  }

  const openEditModal = (y: AcademicYearResponse) => {
    setEditing(y)
    setFormData({ name: y.name, start_date: y.start_date, end_date: y.end_date, status: y.status })
    setFormErrors({}); setApiError(null); setModalOpen(true)
  }

  const validate = (): boolean => {
    const errors: Record<string, string> = {}
    if (!formData.name.trim()) errors.name = 'Name is required'
    if (!formData.start_date) errors.start_date = 'Start date is required'
    if (!formData.end_date) errors.end_date = 'End date is required'
    setFormErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!validate()) return
    setSaving(true)
    setApiError(null)
    try {
      if (editing) {
        const updated = await academicYearApi.update(editing.id, {
          name: formData.name || null,
          start_date: formData.start_date || null,
          end_date: formData.end_date || null,
          status: formData.status || null,
        })
        setData((prev) => prev.map((y) => (y.id === updated.id ? updated : y)))
        showToast('Academic year updated', 'success')
      } else {
        const created = await academicYearApi.create({
          name: formData.name,
          start_date: formData.start_date,
          end_date: formData.end_date,
        })
        setData((prev) => [created, ...prev]); setTotal((t) => t + 1)
        showToast('Academic year created', 'success')
      }
      setModalOpen(false)
    } catch (err: any) {
      setApiError(err?.detail || 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (y: AcademicYearResponse) => {
    if (!confirm(`Delete academic year "${y.name}"?`)) return
    try {
      await academicYearApi.delete(y.id)
      setData((prev) => prev.filter((item) => item.id !== y.id))
      setTotal((t) => t - 1)
      showToast('Academic year deleted', 'success')
    } catch (err: any) {
      showToast(err?.detail || 'Failed to delete', 'error')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Academic Years</h1>
          <p className="text-gray-500 mt-1">{total} year{total !== 1 ? 's' : ''}</p>
        </div>
        <Button onClick={openCreateModal}>Add Academic Year</Button>
      </div>

      <div className="flex items-center gap-4">
        <Select
          options={ACADEMIC_STATUSES.map((s) => ({ value: s, label: capitalize(s) }))}
          placeholder="All statuses"
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
        />
      </div>

      <Card>
        {loading ? <Loading text="Loading academic years..." /> : error ? <ErrorState message={error} onRetry={() => fetch({ page, size, status: statusFilter || undefined })} /> : (
          <>
            <Table
              columns={[
                ...columns,
                {
                  key: 'actions', header: 'Actions',
                  render: (y: AcademicYearResponse) => (
                    <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                      <Button variant="ghost" size="sm" onClick={() => openEditModal(y)}>Edit</Button>
                      <Button variant="danger" size="sm" onClick={() => handleDelete(y)}>Delete</Button>
                    </div>
                  ),
                },
              ]}
              data={data}
              keyExtractor={(y) => y.id}
              emptyMessage="No academic years found."
              onRowClick={(y) => navigate(`/academic/years/${y.id}`)}
            />
            <Pagination page={page} size={size} total={total} pages={pages} onPageChange={setPage} onSizeChange={(s) => { setSize(s); setPage(1) }} />
          </>
        )}
      </Card>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)}
        title={editing ? 'Edit Academic Year' : 'Add Academic Year'}
        footer={
          <>
            <Button variant="secondary" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button onClick={handleSubmit} loading={saving}>{editing ? 'Save Changes' : 'Create'}</Button>
          </>
        }
      >
        {apiError && <Alert variant="error" onClose={() => setApiError(null)}>{apiError}</Alert>}
        <Form onSubmit={handleSubmit}>
          <Input label="Name" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} error={formErrors.name} required />
          <Input label="Start Date" type="date" value={formData.start_date} onChange={(e) => setFormData({ ...formData, start_date: e.target.value })} error={formErrors.start_date} required />
          <Input label="End Date" type="date" value={formData.end_date} onChange={(e) => setFormData({ ...formData, end_date: e.target.value })} error={formErrors.end_date} required />
          {editing && (
            <Select label="Status" value={formData.status ?? editing.status}
              onChange={(e) => setFormData({ ...formData, status: e.target.value })}
              options={ACADEMIC_STATUSES.map((s) => ({ value: s, label: capitalize(s) }))} />
          )}
        </Form>
      </Modal>
    </div>
  )
}