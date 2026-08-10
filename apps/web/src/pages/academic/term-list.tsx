import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { termApi } from '../../api/academic/term-api'
import { academicYearApi } from '../../api/academic/academic-year-api'
import type { TermResponse, TermCreate, TermUpdate, AcademicYearResponse } from '../../api/generated/types'
import { Card, Table, Pagination, Input, Select, Button, Badge, Modal, Form, Alert, EmptyState, ErrorState, useToast, PageHeader, ShortcutKey} from '../../components/ui'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'
import { useDelight } from '../../components/delight/delight-provider'
import { TERM_STATUSES, capitalize, plural } from '../../lib/utils'

const statusBadge: Record<string, 'success' | 'warning' | 'danger' | 'info'> = { active: 'success', inactive: 'danger' }

const columns = [
  { key: 'name', header: 'Name' },
  { key: 'start_date', header: 'Start Date' },
  { key: 'end_date', header: 'End Date' },
  { key: 'status', header: 'Status', render: (t: TermResponse) => <Badge variant={statusBadge[t.status] || 'default'}>{capitalize(t.status)}</Badge> },
]

type TermFormData = { name: string; start_date: string; end_date: string; status?: string | null }

export function TermListPage() {
  const navigate = useNavigate()
  const { showToast } = useToast()
  const { celebrate } = useDelight()

  useKeyboardShortcut({ 'n': () => openCreateModal() }, [])
  const [data, setData] = useState<TermResponse[]>([])
  const [total, setTotal] = useState(0); const [pages, setPages] = useState(0)
  const [page, setPage] = useState(1); const [size, setSize] = useState(20)
  const [yearFilter, setYearFilter] = useState('')
  const [years, setYears] = useState<AcademicYearResponse[]>([])
  const [loading, setLoading] = useState(true); const [error, setError] = useState<string | null>(null)

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<TermResponse | null>(null)
  const [formData, setFormData] = useState<TermFormData>({ name: '', start_date: '', end_date: '' })
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false); const [apiError, setApiError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  useEffect(() => { academicYearApi.list({ size: 100 }).then((r) => setYears(r.items)).catch(() => {}) }, [])

  const fetch = useCallback(async () => {
    if (!yearFilter) { setData([]); setTotal(0); setPages(0); setLoading(false); return }
    const fetchId = ++fetchIdRef.current; setLoading(true); setError(null)
    try {
      const result = await termApi.listByYear(Number(yearFilter), { page, size })
      if (fetchId === fetchIdRef.current) { setData(result.items); setTotal(result.total); setPages(result.pages); setPage(result.page) }
    } catch (err: any) { if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load terms')
    } finally { if (fetchId === fetchIdRef.current) setLoading(false) }
  }, [page, size, yearFilter])

  useEffect(() => { fetch() }, [fetch])

  const openCreateModal = () => {
    if (!yearFilter) { showToast('Select an academic year first', 'info'); return }
    setEditing(null); setFormData({ name: '', start_date: '', end_date: '' }); setFormErrors({}); setApiError(null); setModalOpen(true)
  }

  const openEditModal = (t: TermResponse) => {
    setEditing(t); setFormData({ name: t.name, start_date: t.start_date, end_date: t.end_date, status: t.status }); setFormErrors({}); setApiError(null); setModalOpen(true)
  }

  const validate = (): boolean => {
    const e: Record<string, string> = {}
    if (!formData.name.trim()) e.name = 'Name is required'
    if (!formData.start_date) e.start_date = 'Start date is required'
    if (!formData.end_date) e.end_date = 'End date is required'
    setFormErrors(e); return Object.keys(e).length === 0
  }

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault(); if (!validate()) return; setSaving(true); setApiError(null)
    try {
      if (editing) {
        const updated = await termApi.update(editing.id, { name: formData.name || null, start_date: formData.start_date || null, end_date: formData.end_date || null, status: formData.status || null })
        setData((prev) => prev.map((t) => (t.id === updated.id ? updated : t))); showToast('Term updated', 'success')
      } else {
        const created = await termApi.create(Number(yearFilter), { name: formData.name, start_date: formData.start_date, end_date: formData.end_date })
        setData((prev) => [created, ...prev]); setTotal((t) => t + 1); showToast('Term created', 'success')
        // Glint §5.1 — first-of-kind milestone (registry-gated, once per campus).
        celebrate('first-term')
      }
      setModalOpen(false)
    } catch (err: any) { setApiError(err?.detail || 'Failed to save')
    } finally { setSaving(false) }
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        eyebrow="Academics"
        title="Terms"
        subtitle={plural(total, 'term')}
        compact
        actions={
          <Button onClick={openCreateModal}>
            Add Term
            <ShortcutKey>N</ShortcutKey>
          </Button>
        }
      />
      <div className="flex items-center gap-4">
        <Select options={years.map((y) => ({ value: String(y.id), label: y.name }))} placeholder="Select an academic year" value={yearFilter}
          onChange={(e) => { setYearFilter(e.target.value); setPage(1) }} />
      </div>
      <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
        {!yearFilter ? <EmptyState title="Select an academic year" description="Choose a year above to view its terms." /> : loading ? <Table columns={[]} data={[]} loading={true} keyExtractor={() => ''} emptyMessage="" /> : error ? <ErrorState message={error} onRetry={() => fetch()} /> : (
          <>
            <Table columns={[...columns, { key: 'actions', header: 'Actions', render: (t: TermResponse) => (<div className="flex gap-2" onClick={(e) => e.stopPropagation()}><Button variant="ghost" size="sm" onClick={() => openEditModal(t)}>Edit</Button></div>) }]} data={data} keyExtractor={(t) => t.id} emptyMessage="No terms found for this year." />
            <Pagination page={page} size={size} total={total} pages={pages} onPageChange={setPage} onSizeChange={(s) => { setSize(s); setPage(1) }} />
          </>
        )}
      </Card>
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Edit Term' : 'Add Term'}
        footer={<><Button variant="outline" onClick={() => setModalOpen(false)}>Cancel</Button><Button onClick={handleSubmit} loading={saving}>{editing ? 'Save Changes' : 'Create'}</Button></>}
      >
        {apiError && <Alert variant="error" onClose={() => setApiError(null)}>{apiError}</Alert>}
        <Form onSubmit={handleSubmit}>
          <Input label="Name" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} error={formErrors.name} required />
          <Input label="Start Date" type="date" value={formData.start_date} onChange={(e) => setFormData({ ...formData, start_date: e.target.value })} error={formErrors.start_date} required />
          <Input label="End Date" type="date" value={formData.end_date} onChange={(e) => setFormData({ ...formData, end_date: e.target.value })} error={formErrors.end_date} required />
          {editing && <Select label="Status" value={formData.status ?? editing.status} onChange={(e) => setFormData({ ...formData, status: e.target.value })} options={TERM_STATUSES.map((s) => ({ value: s, label: capitalize(s) }))} />}
        </Form>
      </Modal>
    </div>
  )
}