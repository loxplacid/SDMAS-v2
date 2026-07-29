import { useState, useEffect, useCallback, useRef } from 'react'
import { feeDueApi, type FeeDueListParams } from '../../api/fees/fee-due-api'
import type { FeeDueResponse } from '../../api/generated/types'
import { Card, Table, Pagination, Input, Select, Button, Badge, Modal, Alert, ErrorState, useToast } from '../../components/ui'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'
import { FEE_DUE_STATUSES, capitalize, formatCurrency } from '../../lib/utils'

const statusBadge: Record<string, 'success' | 'warning' | 'danger'> = {
  paid: 'success',
  partially_paid: 'warning',
  unpaid: 'danger',
}

const statusLabel: Record<string, string> = {
  paid: 'Paid',
  partially_paid: 'Partial',
  unpaid: 'Unpaid',
}

export function FeeDueListPage() {
  const { showToast } = useToast()
  const firstFilterRef = useRef<HTMLInputElement>(null)

  useKeyboardShortcut({
    '/': (e) => { e.preventDefault(); firstFilterRef.current?.focus(); },
    'n': () => { setGenModalOpen(true); setGenError(null) },
  }, [])

  const [data, setData] = useState<FeeDueResponse[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(0)
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(20)
  const [studentFilter, setStudentFilter] = useState('')
  const [ayFilter, setAyFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [genModalOpen, setGenModalOpen] = useState(false)
  const [genStudentId, setGenStudentId] = useState('')
  const [genAyId, setGenAyId] = useState('')
  const [generating, setGenerating] = useState(false)
  const [genError, setGenError] = useState<string | null>(null)

  const fetchIdRef = useRef(0)

  const fetch = useCallback(async (params: FeeDueListParams) => {
    const fetchId = ++fetchIdRef.current
    setLoading(true); setError(null)
    try {
      const result = await feeDueApi.list(params)
      if (fetchId === fetchIdRef.current) {
        setData(result.items); setTotal(result.total); setPages(result.pages); setPage(result.page)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load fee dues')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const params: FeeDueListParams = { page, size, status: statusFilter || undefined }
    if (studentFilter) params.student_id = Number(studentFilter)
    if (ayFilter) params.academic_year_id = Number(ayFilter)
    fetch(params)
  }, [page, size, statusFilter, studentFilter, ayFilter, fetch])

  const handleGenerateDues = async () => {
    if (!genStudentId || !genAyId) return
    setGenerating(true); setGenError(null)
    try {
      await feeDueApi.createDues(Number(genStudentId), Number(genAyId))
      showToast('Fee dues generated', 'success')
      setGenModalOpen(false)
      fetch({ page, size })
    } catch (err: any) {
      setGenError(err?.detail || 'Failed to generate dues')
    } finally { setGenerating(false) }
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-[var(--color-brand-accent)] tracking-wide mb-1">Fees</p>
          <h1 className="text-2xl font-bold text-[var(--color-text-primary)] tracking-tight">Fee Dues</h1>
          <p className="text-sm text-[var(--color-text-tertiary)] mt-1">{total} due{total !== 1 ? 's' : ''}</p>
        </div>
        <Button onClick={() => { setGenModalOpen(true); setGenError(null) }}>
          Generate Dues
          <kbd className="ml-2 hidden sm:inline-flex items-center px-1.5 py-0.5 rounded bg-white/20 text-[10px] font-medium text-white/80">N</kbd>
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <Input ref={firstFilterRef} type="number" placeholder="Student ID" value={studentFilter} onChange={(e) => { setStudentFilter(e.target.value); setPage(1) }} className="w-32" />
        <Input type="number" placeholder="Academic Year ID" value={ayFilter} onChange={(e) => { setAyFilter(e.target.value); setPage(1) }} className="w-36" />
        <Select options={FEE_DUE_STATUSES.map((s) => ({ value: s, label: statusLabel[s] || capitalize(s) }))} placeholder="All statuses" value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }} />
      </div>

      <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
        {error ? <ErrorState message={error} onRetry={() => fetch({ page, size })} /> : (
          <>
            <Table
              columns={[
                { key: 'id', header: 'ID', render: (d: FeeDueResponse) => `#${d.id}` },
                { key: 'student_id', header: 'Student' },
                { key: 'fee_structure_id', header: 'Structure' },
                { key: 'original_amount', header: 'Amount', render: (d: FeeDueResponse) => formatCurrency(d.original_amount) },
                { key: 'amount_paid', header: 'Paid', render: (d: FeeDueResponse) => formatCurrency(d.amount_paid) },
                { key: 'due_date', header: 'Due Date', render: (d: FeeDueResponse) => d.due_date || '-' },
                { key: 'status', header: 'Status', render: (d: FeeDueResponse) => <Badge variant={statusBadge[d.status]}>{statusLabel[d.status] || capitalize(d.status)}</Badge> },
              ]}
              data={data}
              keyExtractor={(d) => d.id}
              emptyMessage="No fee dues found."
              loading={loading}
            />
            <Pagination page={page} size={size} total={total} pages={pages} onPageChange={setPage} onSizeChange={(s) => { setSize(s); setPage(1) }} />
          </>
        )}
      </Card>

      <Modal open={genModalOpen} onClose={() => setGenModalOpen(false)}
        title="Generate Fee Dues"
        footer={
          <>
            <Button variant="outline" onClick={() => setGenModalOpen(false)}>Cancel</Button>
            <Button onClick={handleGenerateDues} loading={generating}>Generate</Button>
          </>
        }
      >
        {genError && <Alert variant="error" onClose={() => setGenError(null)}>{genError}</Alert>}
        <div className="space-y-4">
          <Input label="Student ID" type="number" value={genStudentId} onChange={(e) => setGenStudentId(e.target.value)} required />
          <Input label="Academic Year ID" type="number" value={genAyId} onChange={(e) => setGenAyId(e.target.value)} required />
        </div>
      </Modal>
    </div>
  )
}