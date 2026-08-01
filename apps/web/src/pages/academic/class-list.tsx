import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { classApi, type ClassListParams } from '../../api/academic/class-api'
import { academicYearApi } from '../../api/academic/academic-year-api'
import type { ClassResponse, AcademicYearResponse } from '../../api/generated/types'
import { Card, Table, Pagination, Input, Select, Button, Badge, Modal, Form, Alert, Loading, ErrorState, useToast, PageHeader, StatusBadge, SearchInput } from '../../components/ui'
import { ACADEMIC_STATUSES, capitalize } from '../../lib/utils'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'

export function ClassListPage() {
  const navigate = useNavigate()
  const { showToast } = useToast()
  useKeyboardShortcut({ 'n': () => openCreateModal() }, [])

  const [data, setData] = useState<ClassResponse[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(0)
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(20)
  const [yearFilter, setYearFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [years, setYears] = useState<AcademicYearResponse[]>([])
  const [error, setError] = useState<string | null>(null)

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<ClassResponse | null>(null)
  const [formData, setFormData] = useState({ name: '', academic_year_id: null as number | null, status: undefined as string | undefined })
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)

  const fetchIdRef = useRef(0)

  useEffect(() => {
    academicYearApi.list({ size: 100 }).then((r) => setYears(r.items)).catch(() => {})
  }, [])

  const fetch = useCallback(async (params: ClassListParams) => {
    const fetchId = ++fetchIdRef.current
    setLoading(true); setError(null)
    try {
      const result = await classApi.list(params)
      if (fetchId === fetchIdRef.current) {
        setData(result.items); setTotal(result.total); setPages(result.pages); setPage(result.page)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load classes')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetch({ page, size, academic_year_id: yearFilter ? Number(yearFilter) : undefined, status: statusFilter || undefined })
  }, [page, size, yearFilter, statusFilter, fetch])

  const openCreateModal = () => {
    setEditing(null)
    setFormData({ name: '', academic_year_id: yearFilter ? Number(yearFilter) : null, status: undefined })
    setFormErrors({}); setApiError(null); setModalOpen(true)
  }

  const openEditModal = (c: ClassResponse) => {
    setEditing(c)
    setFormData({ name: c.name, academic_year_id: c.academic_year_id, status: c.status })
    setFormErrors({}); setApiError(null); setModalOpen(true)
  }

  const validate = (): boolean => {
    const errors: Record<string, string> = {}
    if (!formData.name.trim()) errors.name = 'Name is required'
    if (!formData.academic_year_id) errors.academic_year_id = 'Academic year is required'
    setFormErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!validate()) return
    setSaving(true); setApiError(null)
    try {
      if (editing) {
        const updated = await classApi.update(editing.id, {
          name: formData.name || null,
          academic_year_id: formData.academic_year_id,
          status: formData.status || null,
        })
        setData((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))
        showToast('Class updated', 'success')
      } else {
        const created = await classApi.create({ name: formData.name, academic_year_id: formData.academic_year_id! })
        setData((prev) => [created, ...prev]); setTotal((t) => t + 1)
        showToast('Class created', 'success')
      }
      setModalOpen(false)
    } catch (err: any) {
      setApiError(err?.detail || 'Failed to save')
    } finally { setSaving(false) }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Classes" subtitle={`${total} class${total !== 1 ? 'es' : ''}`}
        actions={
          <Button onClick={openCreateModal}>
            Add Class
            <kbd className="ml-2 hidden sm:inline-flex items-center px-1.5 py-0.5 rounded bg-white/20 text-[10px] font-medium text-white/80">N</kbd>
          </Button>
        } />
      <div className="flex flex-wrap items-center gap-3">
        <Select options={years.map((y) => ({ value: String(y.id), label: y.name }))} placeholder="All academic years" value={yearFilter}
          onChange={(e) => { setYearFilter(e.target.value); setPage(1) }} />
        <Select options={ACADEMIC_STATUSES.map((s) => ({ value: s, label: capitalize(s) }))} placeholder="All statuses" value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }} />
      </div>
      <Card padding="none">
        {loading ? <Loading text="Loading classes..." /> : error ? <ErrorState message={error} onRetry={() => fetch({ page, size, academic_year_id: yearFilter ? Number(yearFilter) : undefined, status: statusFilter || undefined })} /> : (
          <>
            <Table columns={[
              { key: 'name', header: 'Name' },
              { key: 'academic_year_id', header: 'Academic Year ID', render: (c: ClassResponse) => c.academic_year_id ? `Year #${c.academic_year_id}` : '-' },
              { key: 'status', header: 'Status', render: (c: ClassResponse) => <StatusBadge status={c.status} /> },
              { key: 'actions', header: 'Actions', render: (c: ClassResponse) => (
                <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                  <Button variant="ghost" size="sm" onClick={() => navigate(`/academic/classes/${c.id}/360`)} title="Open Class 360 view">360</Button>
                  <Button variant="outline" size="sm" onClick={() => openEditModal(c)}>Edit</Button>
                </div>
              )},
            ]} data={data} keyExtractor={(c) => c.id} emptyMessage="No classes found." onRowClick={(c) => navigate(`/academic/classes/${c.id}`)} />
            <Pagination page={page} size={size} total={total} pages={pages} onPageChange={setPage} onSizeChange={(s) => { setSize(s); setPage(1) }} />
          </>
        )}
      </Card>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Edit Class' : 'Add Class'}
        footer={<><Button variant="outline" onClick={() => setModalOpen(false)}>Cancel</Button><Button onClick={handleSubmit} loading={saving}>{editing ? 'Save Changes' : 'Create'}</Button></>}>
        {apiError && <Alert variant="error" onClose={() => setApiError(null)}>{apiError}</Alert>}
        <Form onSubmit={handleSubmit}>
          <Input label="Name" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} error={formErrors.name} required />
          <Select label="Academic Year" value={String(formData.academic_year_id ?? '')} onChange={(e) => setFormData({ ...formData, academic_year_id: e.target.value ? Number(e.target.value) : null })} error={formErrors.academic_year_id}
            options={years.map((y) => ({ value: String(y.id), label: y.name }))} placeholder="Select" />
          {editing && (
            <Select label="Status" value={formData.status ?? editing.status} onChange={(e) => setFormData({ ...formData, status: e.target.value })}
              options={ACADEMIC_STATUSES.map((s) => ({ value: s, label: capitalize(s) }))} />
          )}
        </Form>
      </Modal>
    </div>
  )
}
