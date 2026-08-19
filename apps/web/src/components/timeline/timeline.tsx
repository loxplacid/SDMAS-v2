import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  timelineApi,
  type TimelineItem,
  type TimelineParams,
  type TimelineSourceInfo,
  type TimelineResponse,
} from '../../api/timeline/timeline-api'
import { Badge, Button, Input, Select, Skeleton } from '../ui'
import { cn, debounce, formatDateTime, formatRelativeTime } from '../../lib/utils'

// ── Visual maps ───────────────────────────────────────────────────────

const SOURCE_LABELS: Record<string, string> = {
  audit: 'Audit Trail',
  workflow: 'Approvals',
  notification: 'Notifications',
  fees: 'Payments',
  academic: 'Enrollments',
  admissions: 'Admissions',
  risk: 'Risk',
}

const SOURCE_ICON: Record<string, string> = {
  audit: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4',
  workflow: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
  notification: 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9',
  fees: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  academic: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
  admissions: 'M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z',
  risk: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z',
}

const SOURCE_ICON_COLOR: Record<string, string> = {
  audit: 'text-[var(--color-info)] bg-[var(--color-info)]/10',
  workflow: 'text-[var(--color-warning)] bg-[var(--color-warning)]/10',
  notification: 'text-[var(--color-brand-accent)] bg-[var(--color-brand-accent)]/10',
  fees: 'text-[var(--color-success)] bg-[var(--color-success)]/10',
  academic: 'text-[var(--color-info)] bg-[var(--color-info)]/10',
  admissions: 'text-[var(--color-brand-accent)] bg-[var(--color-brand-accent)]/10',
  risk: 'text-[var(--color-danger)] bg-[var(--color-danger)]/10',
}

const SEVERITY_BADGE: Record<string, 'info' | 'success' | 'warning' | 'danger'> = {
  info: 'info',
  success: 'success',
  warning: 'warning',
  critical: 'danger',
}

const SEVERITY_DOT: Record<string, string> = {
  info: 'bg-[var(--color-info)]',
  success: 'bg-[var(--color-success)]',
  warning: 'bg-[var(--color-warning)]',
  critical: 'bg-[var(--color-danger)]',
}

// ── Props ─────────────────────────────────────────────────────────────

interface TimelineProps {
  /** Fixed entity scope applied to every request (e.g. a student for Student 360). */
  params?: Omit<TimelineParams, 'page' | 'page_size'>
  /** Rows per page. Default 20. */
  pageSize?: number
  /** Hide the filter toolbar — used inside 360 tabs and the command center. */
  compact?: boolean
  /** Cap rendered rows before a "view full timeline" link (command center ≈ 6). */
  maxVisible?: number
  className?: string
}

function ItemSkeleton() {
  return (
    <div className="flex items-start gap-3 px-4 py-3.5">
      <Skeleton className="h-9 w-9 rounded-xl flex-shrink-0" />
      <div className="flex-1 space-y-2 min-w-0">
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-3 w-1/2" />
      </div>
      <Skeleton className="h-4 w-16" />
    </div>
  )
}

// ── Component ─────────────────────────────────────────────────────────

export function Timeline({
  params = {},
  pageSize = 20,
  compact = false,
  maxVisible,
  className,
}: TimelineProps) {
  const navigate = useNavigate()
  // Destructure params to primitives so a parent re-render (which recreates
  // the inline params object) never churns the effect dependencies.
  const { entity_type, entity_id } = params
  const [items, setItems] = useState<TimelineItem[]>([])
  const [total, setTotal] = useState(0)
  const [sources, setSources] = useState<TimelineSourceInfo[]>([])
  const [degraded, setDegraded] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  // Filters
  const [source, setSource] = useState('')
  const [eventType, setEventType] = useState('')
  const [actor, setActor] = useState('')
  const [actorFilter, setActorFilter] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')

  const fetchIdRef = useRef(0)
  const hasDataRef = useRef(false)

  // Debounce free-text actor input so we don't fire a request per keystroke.
  const debouncedSetActor = useMemo(
    () => debounce((v: string) => setActorFilter(v), 350),
    [],
  )
  useEffect(() => {
    debouncedSetActor(actor)
    return () => debouncedSetActor.cancel()
  }, [actor, debouncedSetActor])

  const buildQuery = useCallback(
    (page: number): TimelineParams => ({
      entity_type,
      entity_id,
      source: source || undefined,
      event_type: eventType || undefined,
      actor: actorFilter || undefined,
      start: start || undefined,
      end: end || undefined,
      page,
      page_size: pageSize,
    }),
    [entity_type, entity_id, source, eventType, actorFilter, start, end, pageSize],
  )

  const load = useCallback(
    async (page: number, append = false) => {
      const fetchId = ++fetchIdRef.current
      if (append) setLoadingMore(true)
      else setLoading(true)
      setError(null)
      try {
        const res: TimelineResponse = await timelineApi.get(buildQuery(page))
        if (fetchId !== fetchIdRef.current) return
        setItems((prev) => (append ? [...prev, ...res.items] : res.items))
        setTotal(res.total)
        setSources(res.sources)
        setDegraded(res.degraded)
        if (res.items.length > 0) hasDataRef.current = true
      } catch (err: any) {
        if (fetchId === fetchIdRef.current && !hasDataRef.current) {
          setError(err?.detail || 'Failed to load the timeline')
        }
      } finally {
        if (fetchId === fetchIdRef.current) {
          setLoading(false)
          setLoadingMore(false)
        }
      }
    },
    [buildQuery],
  )

  useEffect(() => {
    hasDataRef.current = false
    load(1, false)
    return () => {
      fetchIdRef.current++
    }
  }, [load])

  // ── Derived ──

  const eventTypeOptions = useMemo(() => {
    const seen = new Map<string, string>()
    items.forEach((i) => {
      if (!seen.has(i.event_type)) seen.set(i.event_type, i.event_type)
    })
    return [...seen.keys()].sort().map((v) => ({ value: v, label: v }))
  }, [items])

  const availableSources = sources.filter((s) => s.available)
  const visibleItems = maxVisible ? items.slice(0, maxVisible) : items
  const hasActiveFilters = Boolean(source || eventType || actor || start || end)
  const showLoadMore = !maxVisible && !loadingMore && items.length < total
  const showFullLink = Boolean(
    maxVisible && (items.length >= maxVisible || total > pageSize),
  )

  const clearFilters = () => {
    setSource('')
    setEventType('')
    setActor('')
    setActorFilter('')
    setStart('')
    setEnd('')
  }

  const toggleExpanded = (id: string) =>
    setExpandedId((cur) => (cur === id ? null : id))

  // ── Render ──

  if (error) {
    return (
      <div
        className={cn(
          'flex flex-col items-center justify-center py-12 text-center animate-fade-in rounded-xl border border-[var(--color-danger)]/20 bg-[var(--color-danger)]/5',
          className,
        )}
      >
        <div className="flex items-center justify-center h-12 w-12 rounded-xl bg-[var(--color-danger)]/10 mb-4">
          <svg className="h-6 w-6 text-[var(--color-danger)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
        </div>
        <p className="text-sm font-semibold text-[var(--color-danger-dark)]">{error}</p>
        <Button variant="outline" size="sm" className="mt-4" onClick={() => load(1, false)}>
          Try Again
        </Button>
      </div>
    )
  }

  return (
    <div className={cn('rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden', className)}>
      {/* Filter toolbar (hidden in compact mode) */}
      {!compact && (
        <div className="border-b border-[var(--color-border)] p-4 space-y-3">
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-40">
              <Select
                label="Source"
                id="timeline-source"
                value={source}
                onChange={(e) => setSource(e.target.value)}
                placeholder="All sources"
                options={availableSources.map((s) => ({
                  value: s.key,
                  label: `${SOURCE_LABELS[s.key] || s.key} (${s.count})`,
                }))}
              />
            </div>
            <div className="w-56">
              <Select
                label="Event type"
                id="timeline-event-type"
                value={eventType}
                onChange={(e) => setEventType(e.target.value)}
                placeholder="All events"
                options={eventTypeOptions}
              />
            </div>
            <div className="w-52">
              <Input
                label="Actor"
                id="timeline-actor"
                placeholder="Search by name…"
                value={actor}
                onChange={(e) => setActor(e.target.value)}
              />
            </div>
            <div className="w-44">
              <Input
                label="From"
                id="timeline-start"
                type="date"
                value={start}
                onChange={(e) => setStart(e.target.value)}
              />
            </div>
            <div className="w-44">
              <Input
                label="To"
                id="timeline-end"
                type="date"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
              />
            </div>
            {hasActiveFilters && (
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                Clear filters
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Degraded note */}
      {degraded && (
        <div className="flex items-center gap-2.5 border-b border-[var(--color-warning)]/20 bg-[var(--color-warning)]/5 px-4 py-2.5 text-xs text-[var(--color-warning-dark)]">
          <svg className="h-4 w-4 flex-shrink-0 text-[var(--color-warning)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
          Some data sources are unavailable — showing the latest available activity.
        </div>
      )}

      {/* Loading skeleton */}
      {loading ? (
        <div aria-busy="true" aria-label="Loading timeline">
          <ItemSkeleton />
          <ItemSkeleton />
          <ItemSkeleton />
          <ItemSkeleton />
        </div>
      ) : visibleItems.length === 0 ? (
        <div className="py-12 text-center">
          <div className="flex items-center justify-center h-12 w-12 rounded-full bg-[var(--color-surface-hover)] mx-auto mb-3">
            <svg className="h-6 w-6 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <p className="text-sm text-[var(--color-text-tertiary)]">
            {hasActiveFilters ? 'No events match the current filters.' : 'No activity recorded yet.'}
          </p>
          {hasActiveFilters && (
            <Button variant="ghost" size="sm" className="mt-3" onClick={clearFilters}>
              Clear filters
            </Button>
          )}
        </div>
      ) : (
        <>
          <div className="relative">
            <span className="absolute left-[26px] top-2 bottom-2 w-px bg-[var(--color-border)]" aria-hidden="true" />
            <ul className="divide-y divide-[var(--color-border)]">
              {visibleItems.map((item, i) => {
                const isExpanded = expandedId === item.id
                const severityBadge = SEVERITY_BADGE[item.severity] || 'info'
                return (
                  <li key={item.id} className="relative animate-fade-in-up" style={{ animationDelay: `${i * 40}ms`, animationFillMode: 'both' }}>
                    <div className="flex items-start gap-3 px-4 py-3.5 group">
                      {/* Timeline node */}
                      <span className="relative z-10 mt-0.5 flex items-center justify-center h-9 w-9 rounded-xl border border-[var(--color-border)] flex-shrink-0">
                        <svg className={cn('h-4 w-4', SOURCE_ICON_COLOR[item.source] || 'text-[var(--color-text-muted)]')} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={SOURCE_ICON[item.source] || SOURCE_ICON.notification} />
                        </svg>
                      </span>

                      <div className="flex-1 min-w-0 pt-0.5">
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge variant={severityBadge} size="sm" dot>{item.severity}</Badge>
                          <Badge variant="neutral" size="sm">{SOURCE_LABELS[item.source] || item.source}</Badge>
                          <span className="text-[11px] text-[var(--color-text-tertiary)]">
                            {formatRelativeTime(item.timestamp)}
                          </span>
                        </div>
                        <p className="text-sm font-medium text-[var(--color-text-primary)] mt-1.5">
                          <span className="font-semibold">{item.actor}</span>
                          <span className="text-[var(--color-text-muted)] font-normal"> · </span>
                          <span className="font-normal text-[var(--color-text-secondary)]">{item.entity}</span>
                        </p>
                        <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">{item.description}</p>
                        <p className="text-[11px] text-[var(--color-text-muted)] mt-1">{formatDateTime(item.timestamp)}</p>
                      </div>

                      <div className="flex items-center gap-1 flex-shrink-0">
                        {item.deep_link && (
                          <button
                            onClick={() => navigate(item.deep_link!)}
                            className="inline-flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:text-[var(--color-brand-accent)] hover:bg-[var(--color-brand-accent)]/10 motion-safe:transition-colors"
                            aria-label={`Open ${item.deep_link}`}
                          >
                            Open
                            <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                          </button>
                        )}
                        {Object.keys(item.metadata).length > 0 && (
                          <button
                            onClick={() => toggleExpanded(item.id)}
                            className="inline-flex items-center justify-center h-7 w-7 rounded-lg text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)] motion-safe:transition-colors"
                            aria-label={isExpanded ? 'Collapse details' : 'Show details'}
                          >
                            <svg className={cn('h-4 w-4 motion-safe:transition-transform motion-safe:duration-[var(--motion-fast)]', isExpanded && 'rotate-180')} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Expandable details */}
                    {isExpanded && (
                      <div className="mx-4 mb-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-hover)]/60 p-3 animate-fade-in">
                        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2">
                          {Object.entries(item.metadata).map(([k, v]) => (
                            <div key={k} className="flex items-baseline justify-between gap-3">
                              <dt className="text-[11px] uppercase tracking-wider text-[var(--color-text-muted)] flex-shrink-0">
                                {k.replace(/_/g, ' ')}
                              </dt>
                              <dd className="text-xs font-medium text-[var(--color-text-secondary)] text-right break-all">
                                {typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v ?? '—')}
                              </dd>
                            </div>
                          ))}
                        </dl>
                      </div>
                    )}
                  </li>
                )
              })}
            </ul>
          </div>

          {/* Footer actions */}
          {(showLoadMore || showFullLink) && (
            <div className="border-t border-[var(--color-border)] p-3 flex items-center justify-center">
              {showFullLink ? (
                <Button variant="outline" size="sm" onClick={() => navigate('/timeline')}>
                  View full timeline ({total})
                </Button>
              ) : (
                <Button variant="outline" size="sm" onClick={() => load(Math.floor(items.length / pageSize) + 1, true)} disabled={loadingMore}>
                  {loadingMore ? 'Loading…' : `Load more (${total - items.length} remaining)`}
                </Button>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default Timeline
