import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../api/auth/auth-context'
import {
  dataQualityApi,
  type DataQualityFinding,
  type DataQualityOverview,
} from '../../api/data-quality/data-quality-api'
import { casesApi } from '../../api/cases/cases-api'
import { Button, Badge, Skeleton, Modal, TabGroup, SearchInput, EmptyState } from '../../components/ui'
import { useToast } from '../../components/ui/toast'
import { cn, formatDateTime } from '../../lib/utils'

// ── Presentation helpers ─────────────────────────────────────────────

const SEVERITY_STYLES: Record<string, string> = {
  critical: 'border-[var(--color-danger)]/30 bg-[var(--color-danger)]/5',
  high: 'border-[var(--color-danger)]/20 bg-[var(--color-danger)]/[0.04]',
  medium: 'border-[var(--color-warning)]/25 bg-[var(--color-warning)]/5',
  low: 'border-[var(--color-info)]/25 bg-[var(--color-info)]/5',
}

const SEVERITY_DOT: Record<string, string> = {
  critical: 'bg-[var(--color-danger)]',
  high: 'bg-[var(--color-danger)]',
  medium: 'bg-[var(--color-warning)]',
  low: 'bg-[var(--color-info)]',
}

const SEVERITY_BADGE: Record<string, 'danger' | 'warning' | 'info' | 'success'> = {
  critical: 'danger',
  high: 'danger',
  medium: 'warning',
  low: 'info',
}

const SEVERITY_LABELS: Record<string, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
}

const CATEGORY_LABELS: Record<string, string> = {
  duplicates: 'Duplicates',
  missing_fields: 'Missing Fields',
  invalid_format: 'Invalid Format',
  impossible_dates: 'Impossible Dates',
  inconsistent_references: 'Inconsistent References',
}

const ENTITY_LABELS: Record<string, string> = {
  student: 'Student',
  attendance_record: 'Attendance',
  fee_due: 'Fee Due',
  payment: 'Payment',
  enrollment: 'Enrollment',
}

const STATUS_BADGE: Record<string, 'success' | 'neutral' | 'warning'> = {
  open: 'warning',
  resolved: 'success',
  ignored: 'neutral',
}

const CATEGORY_TABS = [
  { id: 'all', label: 'All' },
  { id: 'duplicates', label: 'Duplicates' },
  { id: 'missing_fields', label: 'Missing Fields' },
  { id: 'invalid_format', label: 'Invalid Format' },
  { id: 'impossible_dates', label: 'Impossible Dates' },
  { id: 'inconsistent_references', label: 'Inconsistent References' },
] as const

type CategoryTabId = (typeof CATEGORY_TABS)[number]['id']

// ── Skeleton ─────────────────────────────────────────────────────────

function DataQualitySkeleton() {
  return (
    <div className="space-y-6 animate-fade-in" aria-busy="true" aria-label="Loading data quality center">
      <div className="space-y-3">
        <Skeleton className="h-8 w-72" />
        <Skeleton className="h-4 w-96" />
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-24 rounded-2xl" />
        ))}
      </div>
      <div className="flex gap-2">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-8 w-24 rounded-lg" />
        ))}
      </div>
      <div className="space-y-2">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className="h-24 rounded-xl" />
        ))}
      </div>
    </div>
  )
}

// ── Overview summary ─────────────────────────────────────────────────

function OverviewCards({
  overview,
  onNavigate,
}: {
  overview: DataQualityOverview | null
  onNavigate: (path: string) => void
}) {
  if (!overview) return null

  const qualityPct = overview.overall_quality
  const qualityStatus =
    qualityPct >= 95 ? 'good' : qualityPct >= 80 ? 'warn' : 'critical'
  const qualityColor: Record<string, string> = {
    good: 'text-[var(--color-success)]',
    warn: 'text-[var(--color-warning)]',
    critical: 'text-[var(--color-danger)]',
  }

  const cards = [
    {
      key: 'quality',
      label: 'Overall Quality',
      value: `${qualityPct.toFixed(1)}%`,
      sub: `across ${overview.total_checks} checks`,
      accent: qualityColor[qualityStatus],
      onClick: undefined as string | undefined,
    },
    { key: 'critical', label: 'Critical', value: String(overview.critical), sub: 'open findings', accent: 'text-[var(--color-danger)]', onClick: 'critical' },
    { key: 'high', label: 'High', value: String(overview.high), sub: 'open findings', accent: 'text-[var(--color-danger)]', onClick: 'high' },
    { key: 'medium', label: 'Medium', value: String(overview.medium), sub: 'open findings', accent: 'text-[var(--color-warning)]', onClick: 'medium' },
    { key: 'low', label: 'Low', value: String(overview.low), sub: 'open findings', accent: 'text-[var(--color-info)]', onClick: 'low' },
  ]

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-5 gap-3">
      {cards.map((c, i) => (
        <button
          key={c.key}
          onClick={() => c.onClick && onNavigate(`/data-quality?severity=${c.onClick}`)}
          disabled={!c.onClick}
          className={cn(
            'rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 text-left',
            'motion-safe:transition-all motion-safe:duration-[var(--motion-fast)]',
            c.onClick && 'hover:-translate-y-0.5 hover:shadow-md hover:border-[var(--color-brand-accent)]/30 cursor-pointer motion-reduce:hover:translate-y-0',
            'animate-fade-in-up'
          )}
          style={{ animationDelay: `${i * 50}ms`, animationFillMode: 'both' }}
        >
          <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-text-tertiary)] truncate">
            {c.label}
          </p>
          <p className={cn('mt-1.5 text-2xl font-bold tabular-nums leading-none', c.accent)}>{c.value}</p>
          <p className="text-[11px] text-[var(--color-text-tertiary)] mt-1.5 truncate">{c.sub}</p>
        </button>
      ))}
    </div>
  )
}

// ── Finding row ──────────────────────────────────────────────────────

function FindingRow({
  finding,
  index,
  active,
  canResolve,
  busy,
  onNavigate,
  onResolve,
  onIgnore,
  onCreateCase,
}: {
  finding: DataQualityFinding
  index: number
  active: boolean
  canResolve: boolean
  busy: boolean
  onNavigate: (finding: DataQualityFinding) => void
  onResolve: (finding: DataQualityFinding) => void
  onIgnore: (finding: DataQualityFinding) => void
  onCreateCase: (finding: DataQualityFinding) => void
}) {
  const navigate = useNavigate()

  return (
    <div
      role="listitem"
      aria-current={active ? 'true' : undefined}
      tabIndex={active ? 0 : -1}
      onKeyDown={(e) => {
        if (e.key === 'Enter' && active && finding.student_id) {
          e.preventDefault()
          navigate(`/students/${finding.student_id}`)
        }
      }}
      className={cn(
        'rounded-xl border p-4 motion-safe:transition-all motion-safe:duration-[var(--motion-fast)]',
        'hover:shadow-sm',
        SEVERITY_STYLES[finding.severity],
        active && 'ring-2 ring-[var(--color-brand-accent)] ring-offset-1 ring-offset-[var(--color-bg)]',
        'animate-fade-in-up'
      )}
      style={{ animationDelay: `${Math.min(index, 8) * 40}ms`, animationFillMode: 'both' }}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 min-w-0">
          <span className={cn('mt-1.5 inline-block h-2 w-2 rounded-full flex-shrink-0', SEVERITY_DOT[finding.severity])} aria-hidden="true" />
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <p className="text-sm font-semibold text-[var(--color-text-primary)]">{finding.description}</p>
              <Badge variant={SEVERITY_BADGE[finding.severity]} size="sm">{SEVERITY_LABELS[finding.severity]}</Badge>
              <Badge variant="neutral" size="sm">{CATEGORY_LABELS[finding.category] || finding.category}</Badge>
              <Badge variant={STATUS_BADGE[finding.status]} size="sm" className="capitalize">{finding.status}</Badge>
            </div>
            <p className="text-xs text-[var(--color-text-tertiary)] mt-1.5">
              {ENTITY_LABELS[finding.entity_type] || finding.entity_type} #{finding.entity_id}
              {finding.field ? ` · field: ${finding.field}` : ''}
            </p>
            <p className="text-[11px] text-[var(--color-text-muted)] mt-1.5">
              Detected {formatDateTime(finding.detected_at)}
              {finding.resolved_at && ` · Resolved ${formatDateTime(finding.resolved_at)}`}
              {finding.resolved_reason ? ` · ${finding.resolved_reason}` : ''}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {finding.student_id != null && (
            <button
              onClick={() => onNavigate(finding)}
              aria-label={`Open student ${finding.student_id}`}
              className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/40 hover:text-[var(--color-brand-accent)] motion-safe:transition-colors"
            >
              View student
              <svg className="h-3 w-3 inline-block ml-1 -mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          )}
          {finding.status === 'open' && (
            <button
              onClick={() => onCreateCase(finding)}
              disabled={busy}
              className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/50 hover:text-[var(--color-brand-accent)] motion-safe:transition-colors disabled:opacity-50"
            >
              Create case
            </button>
          )}
          {finding.status === 'open' && canResolve && (
            <>
              <button
                onClick={() => onResolve(finding)}
                disabled={busy}
                className="rounded-lg bg-[var(--color-brand-accent)] px-2.5 py-1.5 text-xs font-medium text-white hover:bg-[var(--color-brand-accent-hover)] motion-safe:transition-colors disabled:opacity-50"
              >
                Resolve
              </button>
              <button
                onClick={() => onIgnore(finding)}
                disabled={busy}
                className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-warning)]/50 hover:text-[var(--color-warning)] motion-safe:transition-colors disabled:opacity-50"
              >
                Ignore
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Main page ────────────────────────────────────────────────────────

export function DataQualityCenterPage() {
  const { user } = useAuth()
  const { showToast } = useToast()
  const navigate = useNavigate()
  const role = (user?.role as string) || 'staff'
  const canResolve = ['admin', 'principal'].includes(role)

  // ── URL state ──
  const [searchParams, setSearchParams] = useSearchParams()
  const rawTab = searchParams.get('category') as CategoryTabId | null
  const category = rawTab && CATEGORY_TABS.some((t) => t.id === rawTab) ? rawTab : 'all'
  const severity = searchParams.get('severity') || ''
  const status = searchParams.get('status') || ''
  const query = searchParams.get('q') || ''
  const page = Math.max(1, parseInt(searchParams.get('page') || '1', 10) || 1)

  // P11 — deep-link: a case's "View underlying records" arrives here as
  // ?finding=<id>. The banner renders the exact finding regardless of the
  // list's status filter/pagination, so a finding that was resolved by its
  // case (and thus hidden from the default open view) is never lost.
  const findingParam = searchParams.get('finding')
  const [contextFinding, setContextFinding] = useState<DataQualityFinding | null>(null)
  const [contextError, setContextError] = useState(false)

  useEffect(() => {
    if (!findingParam) {
      setContextFinding(null)
      setContextError(false)
      return
    }
    const parsed = Number(findingParam)
    if (!Number.isInteger(parsed) || parsed <= 0) {
      // Malformed deep-link (?finding=abc) — render a neutral invalid-link
      // state instead of issuing a request for /findings/NaN.
      setContextFinding(null)
      setContextError(false)
      return
    }
    let active = true
    setContextFinding(null)
    setContextError(false)
    dataQualityApi
      .getFinding(parsed)
      .then((f) => {
        if (active) setContextFinding(f)
      })
      .catch(() => {
        if (active) setContextError(true)
      })
    return () => {
      active = false
    }
  }, [findingParam])

  const [overview, setOverview] = useState<DataQualityOverview | null>(null)
  const [findings, setFindings] = useState<DataQualityFinding[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [running, setRunning] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const [actionTarget, setActionTarget] = useState<{ finding: DataQualityFinding; mode: 'resolve' | 'ignore' } | null>(null)
  const [caseCreating, setCaseCreating] = useState<number | null>(null)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const fetchIdRef = useRef(0)
  const listRef = useRef<HTMLDivElement>(null)

  const load = useCallback(
    async (background = false) => {
      const fetchId = ++fetchIdRef.current
      if (background) setRefreshing(true)
      else setLoading(true)
      setError(null)
      try {
        const [ov, list] = await Promise.allSettled([
          dataQualityApi.getOverview(),
          dataQualityApi.listFindings({
            category: category === 'all' ? null : category,
            severity: severity || null,
            status: status || null,
            page,
            size: 20,
          }),
        ])
        if (fetchId !== fetchIdRef.current) return

        if (ov.status === 'fulfilled') setOverview(ov.value)
        if (list.status === 'fulfilled') {
          setFindings(list.value.items)
          setTotal(list.value.total)
          setPages(list.value.pages)
        }
        if (ov.status === 'rejected' && list.status === 'rejected') {
          setError('Unable to load data-quality findings from the server.')
        }
      } catch (err: any) {
        if (fetchId === fetchIdRef.current && !background) {
          setError(err?.detail || 'Failed to load the Data Quality Center')
        }
      } finally {
        if (fetchId === fetchIdRef.current) {
          setLoading(false)
          setRefreshing(false)
        }
      }
    },
    [category, severity, status, page]
  )

  useEffect(() => {
    load(false)
  }, [load])

  useEffect(() => {
    setActiveIndex(0)
  }, [category, severity, status, query, page])

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

  // Local search over the current page (server pagination covers the rest).
  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return findings
    return findings.filter(
      (f) =>
        f.description.toLowerCase().includes(q) ||
        f.check_code.toLowerCase().includes(q) ||
        f.category.toLowerCase().includes(q) ||
        (f.field || '').toLowerCase().includes(q)
    )
  }, [findings, query])

  // ── Keyboard navigation (roving) ──
  const moveActive = (next: number) => {
    setActiveIndex(next)
    requestAnimationFrame(() => {
      const row = listRef.current?.querySelectorAll<HTMLElement>('[role="listitem"]')[next]
      row?.focus()
    })
  }
  const handleListKeyDown = (e: React.KeyboardEvent) => {
    if (visible.length === 0) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      moveActive((activeIndex + 1) % visible.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      moveActive((activeIndex - 1 + visible.length) % visible.length)
    }
  }

  // ── Actions ──
  const handleRunChecks = async () => {
    setRunning(true)
    try {
      const result = await dataQualityApi.runChecks()
      showToast(
        `Scan complete — ${result.created} created, ${result.resolved} resolved (${result.total_open} open)`,
        'success'
      )
      await load(true)
    } catch (err: any) {
      showToast(err?.detail || 'Scan failed', 'error')
    } finally {
      setRunning(false)
    }
  }

  const handleAction = async () => {
    if (!actionTarget) return
    setBusy(true)
    try {
      if (actionTarget.mode === 'resolve') {
        const updated = await dataQualityApi.resolveFinding(actionTarget.finding.id, reason.trim() || 'Resolved from Data Quality Center')
        showToast('Finding resolved (audited)', 'success')
        // Keep the deep-linked banner in step from the mutation response
        // (no fire-and-forget refetch that could race unmount).
        setContextFinding((prev) => (prev && prev.id === updated.id ? updated : prev))
      } else {
        const updated = await dataQualityApi.ignoreFinding(actionTarget.finding.id, reason.trim() || 'Ignored from Data Quality Center')
        showToast('Finding ignored (audited)', 'success')
        setContextFinding((prev) => (prev && prev.id === updated.id ? updated : prev))
      }
      setActionTarget(null)
      setReason('')
      await load(true)
    } catch (err: any) {
      showToast(err?.detail || 'Action failed', 'error')
    } finally {
      setBusy(false)
    }
  }

  const severityCount = overview ? overview.critical + overview.high + overview.medium + overview.low : 0

  // P8 §13 — escalate an open finding into an operational case. The case
  // references the finding via source_type/source_id; the finding itself is
  // not mutated, so the audit trail stays intact.
  const handleCreateCase = async (finding: DataQualityFinding) => {
    setCaseCreating(finding.id)
    try {
      const c = await casesApi.create({
        title: finding.description,
        description: `Data quality finding #${finding.id} (${finding.category}) — ${finding.field ? `field: ${finding.field}; ` : ''}entity ${finding.entity_type}#${finding.entity_id}`,
        case_type: 'data_quality',
        priority: finding.severity === 'critical' ? 'critical' : finding.severity === 'high' ? 'high' : finding.severity === 'medium' ? 'medium' : 'low',
        source_type: 'data_quality_finding',
        source_id: finding.id,
        student_id: finding.student_id,
      })
      showToast(`Case ${c.case_number} created from finding #${finding.id}`, 'success')
      navigate(`/cases/${c.id}`)
    } catch (err: any) {
      showToast(err?.detail || 'Could not create case', 'error')
    } finally {
      setCaseCreating(null)
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-[var(--color-brand-navy)] via-[var(--color-brand-navy-light)] to-[var(--color-brand-navy-mid)] p-7 lg:p-8">
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage:
              'linear-gradient(rgba(255,255,255,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.3) 1px, transparent 1px)',
            backgroundSize: '40px 40px',
          }}
        />
        <div className="relative">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5">
            <div className="space-y-1.5">
              <p className="text-sm font-medium text-[var(--color-brand-accent)] tracking-wide">
                Deterministic checks over real school data
              </p>
              <h1 className="text-2xl lg:text-3xl font-extrabold text-white leading-tight tracking-tight">
                Data Quality Center
              </h1>
              <p className="text-white/50 text-sm max-w-xl leading-relaxed">
                Duplicates, missing fields, invalid formats, impossible dates and inconsistent references.
                Every finding points at the exact record that triggered it — nothing is inferred.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => load(true)}
                disabled={refreshing}
                className={cn(
                  'inline-flex items-center gap-2 rounded-xl bg-white/10 px-4 py-2 text-sm font-medium text-white',
                  'hover:bg-white/20 motion-safe:transition-colors',
                  refreshing && 'opacity-60 cursor-wait'
                )}
                aria-label="Refresh data quality"
              >
                <svg className={cn('h-4 w-4', refreshing && 'animate-spin')} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                {refreshing ? 'Refreshing…' : 'Refresh'}
              </button>
              {canResolve && (
                <button
                  onClick={handleRunChecks}
                  disabled={running}
                  className="inline-flex items-center gap-2 rounded-xl bg-[var(--color-brand-accent)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--color-brand-accent-hover)] motion-safe:transition-colors shadow-lg shadow-[var(--color-brand-accent)]/20 disabled:opacity-60 disabled:cursor-wait"
                >
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  {running ? 'Scanning…' : 'Run checks'}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {loading ? (
        <DataQualitySkeleton />
      ) : error && !overview ? (
        <div className="flex flex-col items-center justify-center py-16 text-center animate-fade-in">
          <div className="h-14 w-14 rounded-2xl bg-[var(--color-danger-light)] flex items-center justify-center mb-5">
            <svg className="h-7 w-7 text-[var(--color-danger)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <h3 className="text-sm font-semibold text-[var(--color-danger-dark)]">{error}</h3>
          <button
            onClick={() => load(false)}
            className="mt-5 inline-flex items-center rounded-[10px] bg-[var(--color-danger)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--color-danger-dark)] motion-safe:transition-colors"
          >
            Try Again
          </button>
        </div>
      ) : (
        <>
          <OverviewCards overview={overview} onNavigate={navigate} />

          {/* Filters */}
          <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 space-y-3">
            <TabGroup
              tabs={CATEGORY_TABS.map((t) => ({
                id: t.id,
                label: t.label,
              }))}
              activeTab={category}
              onChange={(id) => {
                setParam({ category: id === 'all' ? null : id, page: null })
              }}
              variant="pills"
              size="sm"
            />
            <div className="flex flex-col sm:flex-row gap-2.5">
              <div className="flex-1 min-w-0">
                <SearchInput
                  value={query}
                  onChange={(e) => setParam({ q: e.target.value || null, page: null })}
                  placeholder="Search findings…"
                  onClear={() => setParam({ q: null })}
                  aria-label="Search findings"
                />
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <select
                  value={severity}
                  onChange={(e) => setParam({ severity: e.target.value || null, page: null })}
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-2 text-xs text-[var(--color-text-secondary)] focus:border-[var(--color-brand-accent)] focus:outline-none"
                  aria-label="Filter by severity"
                >
                  <option value="">All severities</option>
                  {Object.entries(SEVERITY_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
                <select
                  value={status}
                  onChange={(e) => setParam({ status: e.target.value || null, page: null })}
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-2 text-xs text-[var(--color-text-secondary)] focus:border-[var(--color-brand-accent)] focus:outline-none"
                  aria-label="Filter by status"
                >
                  <option value="">All statuses</option>
                  <option value="open">Open</option>
                  <option value="resolved">Resolved</option>
                  <option value="ignored">Ignored</option>
                </select>
              </div>
            </div>
          </div>

          {/* Findings */}
          <section>
            {findingParam && (
              <div
                aria-label={`Deep-linked finding ${findingParam}`}
                className="mb-4 rounded-xl border border-[var(--color-brand-accent)]/25 bg-[var(--color-brand-accent)]/5 p-4 animate-fade-in"
              >
                <div className="flex items-center justify-between gap-3 mb-3">
                  <p className="text-xs font-semibold text-[var(--color-brand-accent)]">
                    Finding #{findingParam} — opened from a case
                  </p>
                  <button
                    onClick={() =>
                      setSearchParams((prev) => {
                        const next = new URLSearchParams(prev)
                        next.delete('finding')
                        return next
                      })
                    }
                    className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1 text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/40 hover:text-[var(--color-brand-accent)] motion-safe:transition-colors"
                  >
                    Show in list
                  </button>
                </div>
                {(() => {
                  const invalidLink = !!findingParam && (!Number.isInteger(Number(findingParam)) || Number(findingParam) <= 0)
                  if (invalidLink) {
                    return (
                      <p className="text-xs text-[var(--color-text-tertiary)] py-2">
                        This link is malformed — no finding reference was provided.
                      </p>
                    )
                  }
                  if (contextError) {
                    return (
                      <p className="text-xs text-[var(--color-danger)] py-2">
                        Couldn't load finding #{findingParam}. It may have been removed, belong to another campus, or your role cannot view it.
                      </p>
                    )
                  }
                  if (!contextFinding) {
                    return <Skeleton className="h-20 rounded-xl" />
                  }
                  return (
                    <div role="list">
                      <FindingRow
                        finding={contextFinding}
                        index={0}
                        active={false}
                        canResolve={canResolve}
                        busy={busy || caseCreating === contextFinding.id}
                        onNavigate={(f) => f.student_id && navigate(`/students/${f.student_id}`)}
                        onResolve={(f) => {
                          setActionTarget({ finding: f, mode: 'resolve' })
                          setReason('')
                        }}
                        onIgnore={(f) => {
                          setActionTarget({ finding: f, mode: 'ignore' })
                          setReason('')
                        }}
                        onCreateCase={handleCreateCase}
                      />
                    </div>
                  )
                })()}
              </div>
            )}

            <div className="flex items-center justify-between mb-3">
              <div>
                <h2 className="text-base font-semibold text-[var(--color-text-primary)]">Findings</h2>
                <p className="text-sm text-[var(--color-text-tertiary)] mt-0.5">
                  {total.toLocaleString()} finding{total !== 1 ? 's' : ''}
                  {severityCount > 0 && total !== severityCount ? ` · ${severityCount} open` : ''}
                </p>
              </div>
            </div>

            {visible.length === 0 ? (
              <EmptyState
                compact
                title={total === 0 ? 'No findings yet' : 'No findings match'}
                description={
                  total === 0
                    ? canResolve
                      ? 'Run a scan to check your data for duplicates, missing fields and invalid records.'
                      : 'No data-quality findings are currently recorded for your school.'
                    : 'No findings match the current filters. Try widening your search.'
                }
                action={
                  total === 0 && canResolve
                    ? { label: 'Run checks', onClick: handleRunChecks }
                    : total > 0
                      ? { label: 'Clear filters', onClick: () => setSearchParams(new URLSearchParams()) }
                      : undefined
                }
              />
            ) : (
              <div ref={listRef} role="list" aria-label="Data quality findings" onKeyDown={handleListKeyDown} className="space-y-2.5">
                {visible.map((f, i) => (
                  <FindingRow
                    key={f.id}
                    finding={f}
                    index={i}
                    active={i === activeIndex}
                    canResolve={canResolve}
                    busy={busy || caseCreating === f.id}
                    onNavigate={(finding) => finding.student_id && navigate(`/students/${finding.student_id}`)}
                    onResolve={(finding) => {
                      setActionTarget({ finding, mode: 'resolve' })
                      setReason('')
                    }}
                    onIgnore={(finding) => {
                      setActionTarget({ finding, mode: 'ignore' })
                      setReason('')
                    }}
                    onCreateCase={handleCreateCase}
                  />
                ))}
              </div>
            )}
          </section>

          {/* Pagination */}
          {pages > 1 && (
            <div className="flex items-center justify-between">
              <p className="text-xs text-[var(--color-text-tertiary)]">
                Page {page} of {pages}
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setParam({ page: String(page - 1) })}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= pages}
                  onClick={() => setParam({ page: String(page + 1) })}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Resolve / ignore dialog — audited */}
      <Modal
        open={actionTarget != null}
        onClose={() => setActionTarget(null)}
        title={actionTarget?.mode === 'ignore' ? 'Ignore finding' : 'Resolve finding'}
        size="sm"
        footer={
          <>
            <Button variant="outline" size="sm" onClick={() => setActionTarget(null)}>Cancel</Button>
            <Button size="sm" onClick={handleAction} disabled={busy}>
              {busy ? 'Saving…' : actionTarget?.mode === 'ignore' ? 'Ignore' : 'Resolve'}
            </Button>
          </>
        }
      >
        <p className="text-xs text-[var(--color-text-tertiary)]">
          {actionTarget?.mode === 'ignore'
            ? 'The finding will be marked ignored and excluded from open counts. The reason is recorded in the audit trail.'
            : 'The finding will be marked resolved. The reason is recorded in the audit trail.'}
        </p>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Reason (audited) — e.g. duplicate merged, email corrected"
          rows={3}
          className="mt-4 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text-primary)] focus:border-[var(--color-brand-accent)] focus:outline-none resize-none"
        />
      </Modal>
    </div>
  )
}

export default DataQualityCenterPage
