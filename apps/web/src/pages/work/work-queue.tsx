import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../api/auth/auth-context'
import {
  casesApi,
  type AssignableUser,
  type CaseItem,
  type CaseOverview,
  type CasePriority,
  type CaseStatus,
  type CaseType,
} from '../../api/cases/cases-api'
import { Badge, Button, Modal, SearchInput, Skeleton } from '../../components/ui'
import { useToast } from '../../components/ui/toast'
import { cn, formatDateTime, formatRelativeTime, plural } from '../../lib/utils'

// ── Presentation helpers ─────────────────────────────────────────────

const PRIORITY_ORDER: CasePriority[] = ['critical', 'high', 'medium', 'low']

const PRIORITY_BADGE: Record<string, 'danger' | 'warning' | 'info' | 'neutral'> = {
  critical: 'danger',
  high: 'danger',
  medium: 'warning',
  low: 'info',
}

const STATUS_LABELS: Record<string, string> = {
  open: 'Open',
  acknowledged: 'Acknowledged',
  in_progress: 'In Progress',
  waiting: 'Waiting',
  resolved: 'Resolved',
  closed: 'Closed',
}

const STATUS_BADGE: Record<string, 'warning' | 'info' | 'success' | 'neutral'> = {
  open: 'warning',
  acknowledged: 'info',
  in_progress: 'info',
  waiting: 'neutral',
  resolved: 'success',
  closed: 'neutral',
}

const SLA_STYLES: Record<string, { badge: 'danger' | 'warning' | 'success' | 'neutral'; text: string }> = {
  OVERDUE: { badge: 'danger', text: 'text-[var(--color-danger)]' },
  DUE_SOON: { badge: 'warning', text: 'text-[var(--color-warning)]' },
  ON_TRACK: { badge: 'neutral', text: 'text-[var(--color-text-tertiary)]' },
  RESOLVED: { badge: 'success', text: 'text-[var(--color-success)]' },
}

const TYPE_LABELS: Record<string, string> = {
  attendance: 'Attendance',
  finance: 'Finance',
  academic: 'Academic',
  documents: 'Documents',
  data_quality: 'Data Quality',
  admissions: 'Admissions',
  operational: 'Operational',
  administrative: 'Administrative',
}

const VIEWS = [
  { id: 'my', label: 'My Work' },
  { id: 'unassigned', label: 'Unassigned' },
  { id: 'open', label: 'All Open' },
  { id: 'overdue', label: 'Overdue' },
  { id: 'due_soon', label: 'Due Soon' },
  { id: 'resolved', label: 'Recently Resolved' },
] as const

type ViewId = (typeof VIEWS)[number]['id']

// ── Skeleton ─────────────────────────────────────────────────────────

function WorkQueueSkeleton() {
  return (
    <div className="space-y-6 animate-fade-in" aria-busy="true" aria-label="Loading work queue">
      <div className="space-y-3">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-96" />
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-6 gap-3">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-20 rounded-xl" />
        ))}
      </div>
      <div className="space-y-2">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-24 rounded-xl" />
        ))}
      </div>
    </div>
  )
}

// ── Case row ─────────────────────────────────────────────────────────

function CaseRow({
  item,
  selected,
  canSelect,
  onToggle,
  index,
}: {
  item: CaseItem
  selected: boolean
  canSelect: boolean
  onToggle: (id: number) => void
  index: number
}) {
  const navigate = useNavigate()
  const sla = SLA_STYLES[item.sla_state] || SLA_STYLES.ON_TRACK

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => navigate(`/cases/${item.id}`)}
      onKeyDown={(e) => {
        if (e.key === 'Enter') navigate(`/cases/${item.id}`)
      }}
      className={cn(
        'group rounded-xl border p-4 text-left cursor-pointer motion-safe:transition-all motion-safe:duration-[var(--motion-fast)] hover:shadow-sm hover:-translate-y-0.5 motion-reduce:hover:translate-y-0',
        selected ? 'border-[var(--color-brand-accent)]/50 bg-[var(--color-brand-accent)]/5' : 'border-[var(--color-border)] bg-[var(--color-surface)]',
        item.escalated_at && 'border-[var(--color-danger)]/30',
        'animate-fade-in-up'
      )}
      style={{ animationDelay: `${Math.min(index, 8) * 40}ms`, animationFillMode: 'both' }}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 min-w-0">
          {canSelect && (
            <input
              type="checkbox"
              checked={selected}
              onChange={(e) => {
                e.stopPropagation()
                onToggle(item.id)
              }}
              onClick={(e) => e.stopPropagation()}
              aria-label={`Select ${item.case_number}`}
              className="mt-1 h-4 w-4 rounded border-[var(--color-border)] accent-[var(--color-brand-accent)] cursor-pointer"
            />
          )}
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-mono font-semibold text-[var(--color-brand-accent)]">{item.case_number}</span>
              <Badge variant={PRIORITY_BADGE[item.priority]} size="sm">{item.priority}</Badge>
              <Badge variant={STATUS_BADGE[item.status]} size="sm">{STATUS_LABELS[item.status]}</Badge>
              <Badge variant="neutral" size="sm">{TYPE_LABELS[item.case_type] || item.case_type}</Badge>
              <Badge variant={sla.badge} size="sm">{item.sla_state}</Badge>
              {item.escalated_at && <Badge variant="danger" size="sm">Escalated</Badge>}
            </div>
            <p className="text-sm font-semibold text-[var(--color-text-primary)] mt-1.5 truncate">{item.title}</p>
            <p className="text-xs text-[var(--color-text-tertiary)] mt-1">
              {item.assignee_name ? `Assigned to ${item.assignee_name}` : 'Unassigned'}
              {item.due_at ? ` · Due ${formatDateTime(item.due_at)}` : ' · No deadline'}
              {item.source_type !== 'manual' && ` · From ${item.source_type.replace('_', ' ')}`}
              {item.created_at ? ` · Created ${formatRelativeTime(item.created_at)}` : ''}
            </p>
          </div>
        </div>
        <svg className={cn('h-4 w-4 text-[var(--color-text-muted)] flex-shrink-0 opacity-0 group-hover:opacity-100 motion-safe:transition-opacity')} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </div>
    </div>
  )
}

// ── Count card ───────────────────────────────────────────────────────

function CountCard({ label, value, tone, onClick }: { label: string; value: number; tone: string; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      disabled={!onClick}
      className={cn(
        'rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3 text-left',
        'motion-safe:transition-all motion-safe:duration-[var(--motion-fast)]',
        onClick && 'hover:-translate-y-0.5 hover:shadow-md hover:border-[var(--color-brand-accent)]/30 cursor-pointer',
        'animate-fade-in-up'
      )}
      style={{ animationFillMode: 'both' }}
    >
      <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-text-tertiary)]">{label}</p>
      <p className={cn('mt-1.5 text-2xl font-bold tabular-nums leading-none', tone)}>{value}</p>
    </button>
  )
}

// ── Main page ────────────────────────────────────────────────────────

export function WorkQueuePage() {
  const { user } = useAuth()
  const { showToast } = useToast()
  const navigate = useNavigate()
  const role = (user?.role as string) || 'staff'
  const canAct = ['admin', 'principal'].includes(role)

  // ── URL state ──
  const [searchParams, setSearchParams] = useSearchParams()
  const rawView = searchParams.get('view') as ViewId | null
  const status = searchParams.get('status') || ''
  // When a status filter is active it is authoritative: fall back to the
  // unfiltered 'all' view instead of 'open' so e.g. "Resolved" isn't
  // contradicted by the default view's terminal-status exclusion.
  const hasView = rawView && VIEWS.some((v) => v.id === rawView)
  const view = hasView ? rawView : status ? 'all' : 'open'
  const priority = searchParams.get('priority') || ''
  const caseType = searchParams.get('case_type') || ''
  const search = searchParams.get('q') || ''
  const sort = searchParams.get('sort') || 'updated'
  const page = Math.max(1, parseInt(searchParams.get('page') || '1', 10) || 1)

  const [overview, setOverview] = useState<CaseOverview | null>(null)
  const [items, setItems] = useState<CaseItem[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Set<number>>(new Set())

  const [createOpen, setCreateOpen] = useState(false)
  const [createForm, setCreateForm] = useState({ title: '', case_type: 'administrative', priority: 'medium', assigned_to: '' })
  const [creating, setCreating] = useState(false)
  const [assignable, setAssignable] = useState<AssignableUser[]>([])

  const [bulkMode, setBulkMode] = useState<'assign' | 'priority' | 'status' | 'due' | null>(null)
  const [bulkValue, setBulkValue] = useState('')
  const [bulkBusy, setBulkBusy] = useState(false)
  const fetchIdRef = useRef(0)

  const setParam = useCallback(
    (patch: Record<string, string | null>) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        for (const [key, value] of Object.entries(patch)) {
          if (value) next.set(key, value)
          else next.delete(key)
        }
        return next
      })
    },
    [setSearchParams]
  )

  const load = useCallback(
    async (background = false) => {
      const fetchId = ++fetchIdRef.current
      if (!background) setLoading(true)
      setError(null)
      try {
        const [ov, list] = await Promise.allSettled([
          casesApi.overview(),
          casesApi.list({
            view,
            status: (status as CaseStatus | '') || null,
            priority: (priority as CasePriority | '') || null,
            case_type: (caseType as CaseType | '') || null,
            search: search || null,
            sort: (sort as 'priority' | 'due' | 'created' | 'updated') || 'updated',
            page,
            size: 20,
          }),
        ])
        if (fetchId !== fetchIdRef.current) return
        if (ov.status === 'fulfilled') setOverview(ov.value)
        if (list.status === 'fulfilled') {
          setItems(list.value.items)
          setTotal(list.value.total)
          setPages(list.value.pages)
        }
        if (ov.status === 'rejected' && list.status === 'rejected') {
          setError('Unable to load the work queue from the server.')
        }
      } catch (err: any) {
        if (fetchId === fetchIdRef.current && !background) {
          setError(err?.detail || 'Failed to load the work queue')
        }
      } finally {
        if (fetchId === fetchIdRef.current) {
          setLoading(false)
        }
      }
    },
    [view, status, priority, caseType, search, sort, page]
  )

  useEffect(() => {
    load(false)
  }, [load])

  useEffect(() => {
    if (canAct) {
      casesApi.assignable().then(setAssignable).catch(() => {})
    }
  }, [canAct])

  useEffect(() => {
    setSelected(new Set())
  }, [view, status, priority, caseType, search, page])

  const allSelected = items.length > 0 && selected.size === items.length

  const handleCreate = async () => {
    if (!createForm.title.trim()) return
    setCreating(true)
    try {
      const created = await casesApi.create({
        title: createForm.title.trim(),
        case_type: createForm.case_type as CaseType,
        priority: createForm.priority as CasePriority,
        assigned_to: createForm.assigned_to ? Number(createForm.assigned_to) : null,
      })
      showToast(`Case ${created.case_number} created`, 'success')
      setCreateOpen(false)
      setCreateForm({ title: '', case_type: 'administrative', priority: 'medium', assigned_to: '' })
      await load(true)
      navigate(`/cases/${created.id}`)
    } catch (err: any) {
      showToast(err?.detail || 'Failed to create case', 'error')
    } finally {
      setCreating(false)
    }
  }

  const handleBulk = async () => {
    if (!bulkMode || selected.size === 0) return
    setBulkBusy(true)
    try {
      const ids = [...selected]
      let result
      if (bulkMode === 'assign') {
        result = await casesApi.bulkAssign(ids, Number(bulkValue))
      } else if (bulkMode === 'priority') {
        result = await casesApi.bulkPriority(ids, bulkValue as CasePriority)
      } else if (bulkMode === 'status') {
        result = await casesApi.bulkStatus(ids, bulkValue as CaseStatus)
      } else {
        result = await casesApi.bulkDueDate(ids, bulkValue || null)
      }
      showToast(`${result.updated.length} updated, ${result.skipped} skipped (audited)`, 'success')
      setBulkMode(null)
      setBulkValue('')
      await load(true)
    } catch (err: any) {
      showToast(err?.detail || 'Bulk operation failed', 'error')
    } finally {
      setBulkBusy(false)
    }
  }

  const overviewCards = overview
    ? [
        { key: 'open', label: 'Open', value: overview.open, tone: 'text-[var(--color-info)]', to: '/work?view=open' },
        { key: 'critical', label: 'Critical', value: overview.critical, tone: 'text-[var(--color-danger)]', to: '/work?view=open&priority=critical' },
        { key: 'overdue', label: 'Overdue', value: overview.overdue, tone: 'text-[var(--color-danger)]', to: '/work?view=overdue' },
        { key: 'due_today', label: 'Due Today', value: overview.due_today, tone: 'text-[var(--color-warning)]', to: '/work?view=due_soon' },
        { key: 'my_open', label: 'My Work', value: overview.my_open, tone: 'text-[var(--color-brand-accent)]', to: '/work?view=my' },
        { key: 'unassigned', label: 'Unassigned', value: overview.unassigned, tone: 'text-[var(--color-text-secondary)]', to: '/work?view=unassigned' },
      ]
    : []

  return (
    <div className="space-y-4">
      {/* Page header — clean, no gradient */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-sm font-semibold text-[var(--color-text-primary)]">Work Queue</h1>
          <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">
            Detect → Assign → Investigate → Act → Resolve → Audit
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => load(true)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 text-sm font-medium text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] motion-safe:transition-colors"
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh
          </button>
          <button
            onClick={() => setCreateOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--color-brand-accent)] px-3 py-1.5 text-sm font-medium text-white hover:bg-[var(--color-brand-accent-hover)] motion-safe:transition-colors"
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            New Case
          </button>
        </div>
      </div>

      {loading ? (
        <WorkQueueSkeleton />
      ) : error ? (
        <div className="flex flex-col items-center justify-center py-16 text-center animate-fade-in">
          <div className="h-12 w-12 rounded-xl bg-[var(--color-danger)]/10 flex items-center justify-center mb-4">
            <svg className="h-7 w-7 text-[var(--color-danger)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <h3 className="text-sm font-semibold text-[var(--color-danger-dark)]">{error}</h3>
          <button
            onClick={() => load(false)}
            className="mt-5 inline-flex items-center rounded-lg bg-[var(--color-danger)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--color-danger-dark)] motion-safe:transition-colors"
          >
            Try Again
          </button>
        </div>
      ) : (
        <>
          {/* Counts */}
          <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3">
            {overviewCards.map((c) => (
              <CountCard key={c.key} label={c.label} value={c.value} tone={c.tone} onClick={() => navigate(c.to)} />
            ))}
          </div>

          {/* View chips */}
          <div className="flex flex-wrap gap-2">
            {VIEWS.map((v) => (
              <button
                key={v.id}
                onClick={() => setParam({ view: v.id === 'open' ? null : v.id, page: null })}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium motion-safe:transition-colors',
                  view === v.id
                    ? 'border-[var(--color-brand-accent)] bg-[var(--color-brand-accent)]/10 text-[var(--color-brand-accent)]'
                    : 'border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/40'
                )}
              >
                {v.label}
                {overview && v.id === 'my' && overview.my_open > 0 && <span className="tabular-nums">{overview.my_open}</span>}
                {overview && v.id === 'overdue' && overview.overdue > 0 && <span className="tabular-nums">{overview.overdue}</span>}
              </button>
            ))}
          </div>

          {/* Filters */}
          <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3 space-y-2.5">
            <div className="flex flex-col sm:flex-row gap-2.5">
              <div className="flex-1 min-w-0">
                <SearchInput
                  value={search}
                  onChange={(e) => setParam({ q: e.target.value || null, page: null })}
                  placeholder="Search case number or title…"
                  onClear={() => setParam({ q: null })}
                  aria-label="Search cases"
                />
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <select
                  value={status}
                  onChange={(e) =>
                    // A status filter is authoritative — clear the view
                    // shortcut so e.g. "Resolved" isn't contradicted by the
                    // default "All Open" view's terminal-status exclusion.
                    setParam({ status: e.target.value || null, view: null, page: null })
                  }
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-2 text-xs text-[var(--color-text-secondary)] focus:border-[var(--color-brand-accent)] focus:outline-none"
                  aria-label="Filter by status"
                >
                  <option value="">All statuses</option>
                  {Object.entries(STATUS_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
                <select
                  value={priority}
                  onChange={(e) => setParam({ priority: e.target.value || null, page: null })}
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-2 text-xs text-[var(--color-text-secondary)] focus:border-[var(--color-brand-accent)] focus:outline-none"
                  aria-label="Filter by priority"
                >
                  <option value="">All priorities</option>
                  {PRIORITY_ORDER.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
                <select
                  value={caseType}
                  onChange={(e) => setParam({ case_type: e.target.value || null, page: null })}
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-2 text-xs text-[var(--color-text-secondary)] focus:border-[var(--color-brand-accent)] focus:outline-none"
                  aria-label="Filter by type"
                >
                  <option value="">All types</option>
                  {Object.entries(TYPE_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
                <select
                  value={sort}
                  onChange={(e) => setParam({ sort: e.target.value || null })}
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-2 text-xs text-[var(--color-text-secondary)] focus:border-[var(--color-brand-accent)] focus:outline-none"
                  aria-label="Sort cases"
                >
                  <option value="updated">Sort: Updated</option>
                  <option value="priority">Sort: Priority</option>
                  <option value="due">Sort: Due date</option>
                  <option value="created">Sort: Created</option>
                </select>
              </div>
            </div>

            {/* Bulk bar */}
            {selected.size > 0 && canAct && (
              <div className="flex flex-wrap items-center gap-2 rounded-xl border border-[var(--color-brand-accent)]/30 bg-[var(--color-brand-accent)]/5 px-3 py-2.5 animate-fade-in-up">
                <p className="text-xs font-semibold text-[var(--color-text-primary)] mr-1">
                  {selected.size} selected
                </p>
                <button
                  onClick={() => setBulkMode('assign')}
                  className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/40"
                >
                  Assign
                </button>
                <button
                  onClick={() => setBulkMode('priority')}
                  className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/40"
                >
                  Change priority
                </button>
                <button
                  onClick={() => setBulkMode('status')}
                  className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/40"
                >
                  Change status
                </button>
                <button
                  onClick={() => setBulkMode('due')}
                  className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/40"
                >
                  Set deadline
                </button>
                <button
                  onClick={() => setSelected(new Set())}
                  className="ml-auto rounded-lg px-2.5 py-1.5 text-xs font-medium text-[var(--color-text-tertiary)] hover:text-[var(--color-danger)] motion-safe:transition-colors"
                >
                  Clear
                </button>
              </div>
            )}
          </div>

          {/* List */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <div>
                <h2 className="text-base font-semibold text-[var(--color-text-primary)]">Cases</h2>
                <p className="text-sm text-[var(--color-text-tertiary)] mt-0.5">{plural(total, 'case')}</p>
              </div>
              {items.length > 0 && canAct && (
                <label className="flex items-center gap-2 text-xs text-[var(--color-text-tertiary)]">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={(e) => {
                      setSelected(e.target.checked ? new Set(items.map((i) => i.id)) : new Set())
                    }}
                    aria-label="Select all on this page"
                    className="h-4 w-4 rounded border-[var(--color-border)] accent-[var(--color-brand-accent)] cursor-pointer"
                  />
                  Select page
                </label>
              )}
            </div>

            {items.length === 0 ? (
              <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-8 text-center">
                <div className="flex items-center justify-center h-11 w-11 rounded-xl bg-[var(--color-surface-hover)] mx-auto mb-3">
                  <svg className="h-5 w-5 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                  </svg>
                </div>
                <p className="text-sm font-semibold text-[var(--color-text-primary)]">
                  {search || priority || caseType || status ? 'No cases match these filters' : 'No open cases'}
                </p>
                <p className="text-xs text-[var(--color-text-tertiary)] mt-1 max-w-sm mx-auto">
                  {search || priority || caseType || status
                    ? 'Try widening your search or clearing the filters.'
                    : 'Promote risk findings to cases from the Risk Center, or create one manually.'}
                </p>
                {(search || priority || caseType || status) && (
                  <button
                    onClick={() => setSearchParams(new URLSearchParams())}
                    className="mt-4 rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/40"
                  >
                    Clear filters
                  </button>
                )}
              </div>
            ) : (
              <div className="space-y-2.5">
                {items.map((item, i) => (
                  <CaseRow
                    key={item.id}
                    item={item}
                    index={i}
                    selected={selected.has(item.id)}
                    canSelect={canAct}
                    onToggle={(id) =>
                      setSelected((prev) => {
                        const next = new Set(prev)
                        if (next.has(id)) next.delete(id)
                        else next.add(id)
                        return next
                      })
                    }
                  />
                ))}
              </div>
            )}

            {/* Pagination */}
            {pages > 1 && (
              <div className="flex items-center justify-between mt-5">
                <p className="text-xs text-[var(--color-text-tertiary)]">Page {page} of {pages}</p>
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setParam({ page: String(page - 1) })}>
                    Previous
                  </Button>
                  <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setParam({ page: String(page + 1) })}>
                    Next
                  </Button>
                </div>
              </div>
            )}
          </section>
        </>
      )}

      {/* Create case modal */}
      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Create a case"
        size="md"
        footer={
          <>
            <Button variant="outline" size="sm" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button size="sm" onClick={handleCreate} disabled={creating || !createForm.title.trim()}>
              {creating ? 'Creating…' : 'Create case'}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <div>
            <label className="text-xs font-medium text-[var(--color-text-secondary)] block mb-1">Title *</label>
            <input
              value={createForm.title}
              onChange={(e) => setCreateForm((f) => ({ ...f, title: e.target.value }))}
              placeholder="What needs attention?"
              className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text-primary)] focus:border-[var(--color-brand-accent)] focus:outline-none"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-[var(--color-text-secondary)] block mb-1">Type</label>
              <select
                value={createForm.case_type}
                onChange={(e) => setCreateForm((f) => ({ ...f, case_type: e.target.value }))}
                className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text-primary)] focus:border-[var(--color-brand-accent)] focus:outline-none"
              >
                {Object.entries(TYPE_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-[var(--color-text-secondary)] block mb-1">Priority</label>
              <select
                value={createForm.priority}
                onChange={(e) => setCreateForm((f) => ({ ...f, priority: e.target.value }))}
                className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text-primary)] focus:border-[var(--color-brand-accent)] focus:outline-none"
              >
                {PRIORITY_ORDER.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-[var(--color-text-secondary)] block mb-1">Assign to</label>
            <select
              value={createForm.assigned_to}
              onChange={(e) => setCreateForm((f) => ({ ...f, assigned_to: e.target.value }))}
              className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text-primary)] focus:border-[var(--color-brand-accent)] focus:outline-none"
            >
              <option value="">Unassigned</option>
              {assignable.map((u) => (
                <option key={u.id} value={u.id}>{u.name} · {u.role}</option>
              ))}
            </select>
          </div>
        </div>
      </Modal>

      {/* Bulk action modal */}
      <Modal
        open={bulkMode != null}
        onClose={() => setBulkMode(null)}
        title={
          bulkMode === 'assign' ? 'Assign selected cases'
            : bulkMode === 'priority' ? 'Change priority of selected cases'
            : bulkMode === 'status' ? 'Change status of selected cases'
            : 'Set deadline for selected cases'
        }
        size="sm"
        footer={
          <>
            <Button variant="outline" size="sm" onClick={() => setBulkMode(null)}>Cancel</Button>
            <Button size="sm" onClick={handleBulk} disabled={bulkBusy || !bulkValue}>
              {bulkBusy ? 'Applying…' : 'Apply'}
            </Button>
          </>
        }
      >
        <p className="text-xs text-[var(--color-text-tertiary)] mb-3">
          {selected.size} case(s) will be updated. Every change is recorded in the audit trail.
        </p>
        {bulkMode === 'assign' && (
          <select
            value={bulkValue}
            onChange={(e) => setBulkValue(e.target.value)}
            className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text-primary)] focus:border-[var(--color-brand-accent)] focus:outline-none"
            aria-label="Assign to"
          >
            <option value="">Select assignee…</option>
            {assignable.map((u) => (
              <option key={u.id} value={u.id}>{u.name} · {u.role}</option>
            ))}
          </select>
        )}
        {bulkMode === 'priority' && (
          <select
            value={bulkValue}
            onChange={(e) => setBulkValue(e.target.value)}
            className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text-primary)] focus:border-[var(--color-brand-accent)] focus:outline-none"
            aria-label="New priority"
          >
            <option value="">Select priority…</option>
            {PRIORITY_ORDER.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        )}
        {bulkMode === 'status' && (
          <select
            value={bulkValue}
            onChange={(e) => setBulkValue(e.target.value)}
            className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text-primary)] focus:border-[var(--color-brand-accent)] focus:outline-none"
            aria-label="New status"
          >
            <option value="">Select status…</option>
            {Object.entries(STATUS_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        )}
        {bulkMode === 'due' && (
          <input
            type="datetime-local"
            value={bulkValue}
            onChange={(e) => setBulkValue(e.target.value)}
            className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text-primary)] focus:border-[var(--color-brand-accent)] focus:outline-none"
            aria-label="Due date"
          />
        )}
      </Modal>
    </div>
  )
}

export default WorkQueuePage
