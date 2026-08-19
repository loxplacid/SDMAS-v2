import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { leaveApi, LEAVE_TYPES, type LeaveRequestResponse } from '../../api/leave/leave-api'
import { Table, Pagination, Button, Select, ErrorState, StatusBadge, SearchInput, EmptyState, getEmptyState, useToast, ShortcutKey} from '../../components/ui'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'
import { capitalize, debounce } from '../../lib/utils'

function getStatusVariant(status: string | null): 'success' | 'warning' | 'danger' | 'info' | 'neutral' {
  if (!status) return 'neutral'
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info' | 'neutral'> = {
    active: 'warning',
    completed: 'success',
    cancelled: 'danger',
  }
  return map[status] || 'neutral'
}

export function LeaveListPage() {
  const navigate = useNavigate()
  const { showToast } = useToast()
  const searchRef = useRef<HTMLInputElement>(null)

  useKeyboardShortcut({
    '/': (e) => { e.preventDefault(); searchRef.current?.focus() },
    'n': () => navigate('/leave/new'),
  }, [])

  const [data, setData] = useState<LeaveRequestResponse[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(0)
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(20)
  const [typeFilter, setTypeFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchIdRef = useRef(0)

  const fetchLeave = useCallback(async (params: { page: number; size: number; leave_type?: string }) => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)
    try {
      const result = await leaveApi.list(params)
      if (fetchId === fetchIdRef.current) {
        setData(result.items)
        setTotal(result.total)
        setPages(result.pages)
        setPage(result.page)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load leave requests')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchLeave({ page, size, leave_type: typeFilter || undefined })
  }, [page, size, typeFilter, fetchLeave])

  return (
    <div className="space-y-8 animate-fade-in-up">
      <div>
        <p className="text-sm font-medium text-[var(--color-brand-accent)] tracking-wide mb-1">Workflow</p>
        <h1 className="text-3xl lg:text-4xl font-extrabold text-[var(--color-text-primary)] tracking-tight leading-tight">
          Leave Requests
        </h1>
        <p className="text-base text-[var(--color-text-tertiary)] mt-2 max-w-xl">
          Submit and track leave requests through the automated approval workflow.
        </p>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3 flex-1 max-w-lg">
          <div className="flex-1 min-w-[200px]">
            <SearchInput
              ref={searchRef}
              placeholder="Filter by leave type..."
              onChange={(e) => setTypeFilter(e.target.value)}
              showKbdHint
            />
          </div>
          <Select
            options={[
              { value: '', label: 'All types' },
              ...LEAVE_TYPES.map((t) => ({ value: t, label: capitalize(t) })),
            ]}
            value={typeFilter}
            onChange={(e) => { setTypeFilter(e.target.value); setPage(1) }}
          />
        </div>
        <Button onClick={() => navigate('/leave/new')} className="relative">
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Leave
          <ShortcutKey>N</ShortcutKey>
        </Button>
      </div>

      <div className="bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)] overflow-hidden">
        {loading ? (
          <Table columns={[]} data={[]} loading={true} keyExtractor={() => ''} emptyMessage="" />
        ) : error ? (
          <ErrorState message={error} onRetry={() => fetchLeave({ page, size, leave_type: typeFilter || undefined })} />
        ) : data.length === 0 ? (
          <div className="p-8">
            <EmptyState
              title="No leave requests"
              description="Submit your first leave request to get started."
              action={{ label: 'New Leave', onClick: () => navigate('/leave/new') }}
            />
          </div>
        ) : (
          <>
            <Table
              columns={[
                { key: 'leave_type', header: 'Type', render: (l: LeaveRequestResponse) => capitalize(l.leave_type) },
                { key: 'start_date', header: 'Start' },
                { key: 'end_date', header: 'End' },
                { key: 'duration_days', header: 'Days' },
                { key: 'reason', header: 'Reason', render: (l: LeaveRequestResponse) => l.reason || '-' },
                { key: 'status', header: 'Status', render: (l: LeaveRequestResponse) => (
                  <StatusBadge status={l.workflow_instance_id ? 'active' : 'draft'} variant="info" />
                )},
              ]}
              data={data}
              keyExtractor={(l) => l.id}
              emptyMessage="No leave requests"
              onRowClick={(l) => navigate(`/leave/${l.id}`)}
            />
            <Pagination page={page} size={size} total={total} pages={pages} onPageChange={setPage} onSizeChange={(s) => { setSize(s); setPage(1) }} />
          </>
        )}
      </div>
    </div>
  )
}

export default LeaveListPage
