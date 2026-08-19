import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../api/auth/auth-context'
import { commandCenterApi } from '../../api/command-center/command-center-api'
import { riskApi, type RiskFinding } from '../../api/risk/risk-api'
import { Button, Badge, Skeleton, Modal, TabGroup, SearchInput, EmptyState } from '../../components/ui'
import { useToast } from '../../components/ui/toast'
import { cn, formatDateTime } from '../../lib/utils'
import {
  toActionItems,
  filterActions,
  GROUP_LABELS,
  type ActionItem,
  type ActionSeverity,
  type ActionStatus,
} from '../../lib/attention/actions'

// ── Presentation helpers ─────────────────────────────────────────────

const SEVERITY_STYLES: Record<string, string> = {
  critical: 'border-[var(--color-danger)]/30 bg-[var(--color-danger)]/5',
  high: 'border-[var(--color-danger)]/20 bg-[var(--color-danger)]/[0.04]',
  warning: 'border-[var(--color-warning)]/25 bg-[var(--color-warning)]/5',
  info: 'border-[var(--color-info)]/25 bg-[var(--color-info)]/5',
}

const SEVERITY_DOT: Record<string, string> = {
  critical: 'bg-[var(--color-danger)]',
  high: 'bg-[var(--color-danger)]',
  warning: 'bg-[var(--color-warning)]',
  info: 'bg-[var(--color-info)]',
}

const SEVERITY_BADGE: Record<string, 'danger' | 'warning' | 'info' | 'success'> = {
  critical: 'danger',
  high: 'danger',
  warning: 'warning',
  info: 'info',
}

const SEVERITY_LABELS: Record<ActionSeverity, string> = {
  critical: 'Critical',
  high: 'High',
  warning: 'Warning',
  info: 'Info',
}

const TABS = [
  { id: 'all', label: 'All' },
  { id: 'critical', label: 'Critical' },
  { id: 'financial', label: 'Financial' },
  { id: 'attendance', label: 'Attendance' },
  { id: 'system', label: 'System' },
] as const

type TabId = (typeof TABS)[number]['id']

// ── Skeleton ─────────────────────────────────────────────────────────

function ActionCenterSkeleton() {
  return (
    <div className="space-y-6 animate-fade-in" aria-busy="true" aria-label="Loading action center">
      <div className="space-y-3">
        <Skeleton className="h-8 w-72" />
        <Skeleton className="h-4 w-96" />
      </div>
      <div className="flex gap-2">
        {Array.from({ length: 5 }, (_, i) => (
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

// ── Action row ───────────────────────────────────────────────────────

function ActionRow({
  item,
  index,
  active,
  selectable,
  selected,
  canResolve,
  canAcknowledge,
  busy,
  onSelect,
  onNavigate,
  onResolve,
  onAcknowledge,
}: {
  item: ActionItem
  index: number
  active: boolean
  selectable: boolean
  selected: boolean
  canResolve: boolean
  canAcknowledge: boolean
  busy: boolean
  onSelect: (item: ActionItem) => void
  onNavigate: (item: ActionItem) => void
  onResolve: (item: ActionItem) => void
  onAcknowledge: (item: ActionItem) => void
}) {
  const navigate = useNavigate()
  const isResolvable = item.source === 'risk' && item.status !== 'resolved' && item.riskFindingId != null

  return (
    <div
      role="listitem"
      aria-current={active ? 'true' : undefined}
      tabIndex={active ? 0 : -1}
      onKeyDown={(e) => {
        if (e.key === 'Enter' && active) {
          e.preventDefault()
          if (item.drillDown) navigate(item.drillDown)
        }
        if (e.key === ' ' && active && selectable) {
          e.preventDefault()
          onSelect(item)
        }
      }}
      className={cn(
        'rounded-xl border p-4 motion-safe:transition-all motion-safe:duration-[var(--motion-fast)]',
        'hover:shadow-sm',
        SEVERITY_STYLES[item.severity],
        active && 'ring-2 ring-[var(--color-brand-accent)] ring-offset-1 ring-offset-[var(--color-bg)]',
        'animate-fade-in-up'
      )}
      style={{ animationDelay: `${Math.min(index, 8) * 40}ms`, animationFillMode: 'both' }}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 min-w-0">
          {selectable && (
            <input
              type="checkbox"
              checked={selected}
              onChange={() => onSelect(item)}
              aria-label={`Select ${item.title}`}
              className="mt-1 h-4 w-4 rounded border-[var(--color-border)] accent-[var(--color-brand-accent)]"
            />
          )}
          <span className={cn('mt-1.5 inline-block h-2 w-2 rounded-full flex-shrink-0', SEVERITY_DOT[item.severity])} aria-hidden="true" />
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <p className="text-sm font-semibold text-[var(--color-text-primary)]">{item.title}</p>
              <Badge variant={SEVERITY_BADGE[item.severity]} size="sm">{SEVERITY_LABELS[item.severity]}</Badge>
              <Badge variant="neutral" size="sm">{GROUP_LABELS[item.group]}</Badge>
              {item.count != null && item.count > 1 && (
                <span className="inline-flex items-center rounded-full bg-[var(--color-bg)] border border-[var(--color-border)] px-2 py-0.5 text-[10px] font-semibold tabular-nums text-[var(--color-text-secondary)]">
                  {item.count}
                </span>
              )}
            </div>
            <p className="text-xs text-[var(--color-text-tertiary)] mt-1 leading-relaxed">{item.description}</p>
            {item.resolvedAt && (
              <p className="text-[11px] text-[var(--color-text-muted)] mt-1.5">
                Resolved {formatDateTime(item.resolvedAt)}
                {item.resolvedReason ? ` · ${item.resolvedReason}` : ''}
              </p>
            )}
            {item.detectedAt && (
              <p className="text-[11px] text-[var(--color-text-muted)] mt-1.5">Detected {formatDateTime(item.detectedAt)}</p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {item.status === 'acknowledged' && (
            <Badge variant="warning" size="sm">Acknowledged</Badge>
          )}
          {isResolvable && item.status === 'open' && canAcknowledge && (
            <button
              onClick={() => onAcknowledge(item)}
              disabled={busy}
              className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/40 hover:text-[var(--color-brand-accent)] motion-safe:transition-colors disabled:opacity-50"
            >
              Acknowledge
            </button>
          )}
          {isResolvable && canResolve && (
            <button
              onClick={() => onResolve(item)}
              disabled={busy}
              className="rounded-lg bg-[var(--color-brand-accent)] px-2.5 py-1.5 text-xs font-medium text-white hover:bg-[var(--color-brand-accent-hover)] motion-safe:transition-colors disabled:opacity-50"
            >
              Resolve
            </button>
          )}
          {item.drillDown && (
            <button
              onClick={() => onNavigate(item)}
              aria-label={`Open ${item.title}`}
              className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/40 hover:text-[var(--color-brand-accent)] motion-safe:transition-colors"
            >
              {item.actionLabel}
              <svg className="h-3 w-3 inline-block ml-1 -mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Main page ────────────────────────────────────────────────────────

export function ActionCenterPage() {
  const { user } = useAuth()
  const { showToast } = useToast()
  const navigate = useNavigate()
  const role = (user?.role as string) || 'staff'
  const canResolve = ['admin', 'principal'].includes(role)
  const canAcknowledge = ['admin', 'principal', 'staff'].includes(role)

  // ── URL state (shareable / refresh-persistent filters) ──
  const [searchParams, setSearchParams] = useSearchParams()
  // Validate the URL tab against the known set — a stale/bogus ?tab= value
  // must not leave the tab group with no selection or odd filter semantics.
  const rawTab = searchParams.get('tab') as TabId | null
  const tab = (rawTab && TABS.some((t) => t.id === rawTab) ? rawTab : 'all') as TabId
  const severity = (searchParams.get('severity') as ActionSeverity | '') || ''
  const status = searchParams.get('status') || ''
  const query = searchParams.get('q') || ''

  const [alerts, setAlerts] = useState<ActionItem[]>([])
  const [resolved, setResolved] = useState<ActionItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [resolveTargets, setResolveTargets] = useState<ActionItem[]>([])
  const [resolveReason, setResolveReason] = useState('')
  const [busy, setBusy] = useState(false)
  const fetchIdRef = useRef(0)
  const listRef = useRef<HTMLDivElement>(null)

  const load = useCallback(async (background = false) => {
    const fetchId = ++fetchIdRef.current
    if (background) setRefreshing(true)
    else setLoading(true)
    setError(null)
    try {
      // All real data: command-center alerts + risk findings (open/acknowledged
      // for attention; recently resolved for the resolved section).
      const [overview, open, resolvedPage] = await Promise.allSettled([
        commandCenterApi.getOverview(),
        riskApi.listFindings({ status: 'open', size: 50 }),
        riskApi.listFindings({ status: 'resolved', size: 10 }),
      ])
      if (fetchId !== fetchIdRef.current) return

      const fromAlerts =
        overview.status === 'fulfilled' && overview.value.needs_attention.available
          ? overview.value.needs_attention.alerts
          : []
      const fromFindings = open.status === 'fulfilled' ? open.value.items : []
      const fromResolved = resolvedPage.status === 'fulfilled' ? resolvedPage.value.items : []

      setAlerts(toActionItems(fromAlerts, fromFindings))
      setResolved(
        toActionItems([], fromResolved).filter((i) => i.status === 'resolved')
      )
      // Only a hard failure when both primary sources are unreachable.
      if (overview.status === 'rejected' && open.status === 'rejected') {
        setError('Unable to load actions from the server.')
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current && !background) {
        setError(err?.detail || 'Failed to load the Action Center')
      }
    } finally {
      if (fetchId === fetchIdRef.current) {
        setLoading(false)
        setRefreshing(false)
      }
    }
  }, [])

  useEffect(() => {
    load(false)
  }, [load])

  // ── Filtering ──
  const visible = useMemo(() => {
    const group =
      tab === 'financial' || tab === 'attendance' || tab === 'system' ? tab : null
    return filterActions(alerts, {
      group,
      severity: tab === 'critical' ? 'critical' : severity || null,
      status: (status || null) as ActionStatus | null,
      query: query || undefined,
    })
  }, [alerts, tab, severity, status, query])

  // Keep the roving index in range whenever the visible list changes
  // (search/severity/status filters shrink the list).
  useEffect(() => {
    setActiveIndex((i) => (visible.length === 0 ? 0 : Math.min(i, visible.length - 1)))
  }, [visible.length])

  const selectionTargets = visible.filter((i) => selected.has(i.id))

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

  // ── Keyboard navigation (roving) ──
  // True roving tabindex: Arrow moves both the active ring AND DOM focus to
  // the new row, so Enter/Space on the focused row always targets the active
  // item (the row's own onKeyDown checks `active`).
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

  // ── Selection / bulk resolve ──
  const toggleSelect = (item: ActionItem) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(item.id)) next.delete(item.id)
      else next.add(item.id)
      return next
    })
  }

  const openResolve = (items: ActionItem[]) => {
    setResolveTargets(items)
    setResolveReason('')
  }

  const handleResolve = async () => {
    if (resolveTargets.length === 0) return
    setBusy(true)
    try {
      const results = await Promise.allSettled(
        resolveTargets
          .map((t) => t.riskFindingId)
          .filter((id): id is number => id != null)
          .map((id) => riskApi.resolveFinding(id, resolveReason.trim() || 'Resolved from Action Center'))
      )
      const ok = results.filter((r) => r.status === 'fulfilled').length
      const fail = results.length - ok
      showToast(
        fail === 0
          ? `Resolved ${ok} action${ok !== 1 ? 's' : ''} (audited)`
          : `Resolved ${ok}, failed ${fail}`,
        fail === 0 ? 'success' : 'warning'
      )
      setResolveTargets([])
      setSelected(new Set())
      setResolveReason('')
      await load(true)
    } catch (err: any) {
      showToast(err?.detail || 'Resolve failed', 'error')
    } finally {
      setBusy(false)
    }
  }

  const handleAcknowledge = async (item: ActionItem) => {
    if (item.riskFindingId == null) return
    setBusy(true)
    try {
      await riskApi.acknowledgeFinding(item.riskFindingId)
      showToast('Action acknowledged', 'success')
      await load(true)
    } catch (err: any) {
      showToast(err?.detail || 'Acknowledge failed', 'error')
    } finally {
      setBusy(false)
    }
  }

  const allSelected = visible.length > 0 && visible.every((i) => selected.has(i.id))

  const attentionCount = alerts.filter((a) => a.status !== 'resolved').length

  return (
    <div className="space-y-4">
      {/* Page header — clean, no gradient */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-sm font-semibold text-[var(--color-text-primary)]">Action Center</h1>
          <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">
            Real alerts from live school data and the risk engine · every resolution is audited
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => load(true)}
            disabled={refreshing}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 text-sm font-medium text-[var(--color-text-secondary)]',
              'hover:bg-[var(--color-surface-hover)] motion-safe:transition-colors',
              refreshing && 'opacity-60 cursor-wait'
            )}
            aria-label="Refresh action center"
          >
            <svg className={cn('h-3.5 w-3.5', refreshing && 'animate-spin')} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {refreshing ? 'Refreshing…' : 'Refresh'}
          </button>
          <button
            onClick={() => navigate('/risk')}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--color-brand-accent)] px-3 py-1.5 text-sm font-medium text-white hover:bg-[var(--color-brand-accent-hover)] motion-safe:transition-colors"
          >
            Risk Center
          </button>
        </div>
      </div>

      {loading ? (
        <ActionCenterSkeleton />
      ) : error && alerts.length === 0 ? (
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
          {/* Filters */}
          <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3 space-y-2.5">
            <TabGroup
              tabs={TABS.map((t) => ({
                id: t.id,
                label: t.label,
                badge:
                  t.id === 'all'
                    ? attentionCount > 0
                      ? <span className="tabular-nums">{attentionCount}</span>
                      : undefined
                    : undefined,
              }))}
              activeTab={tab}
              onChange={(id) => {
                setParam({ tab: id === 'all' ? null : id })
                setActiveIndex(0)
              }}
              variant="pills"
              size="sm"
            />
            <div className="flex flex-col sm:flex-row gap-2.5">
              <div className="flex-1 min-w-0">
                <SearchInput
                  value={query}
                  onChange={(e) => setParam({ q: e.target.value || null })}
                  placeholder="Search actions…"
                  onClear={() => setParam({ q: null })}
                  showKbdHint
                  aria-label="Search actions"
                />
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <select
                  value={severity}
                  onChange={(e) => setParam({ severity: e.target.value || null })}
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
                  onChange={(e) => setParam({ status: e.target.value || null })}
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-2 text-xs text-[var(--color-text-secondary)] focus:border-[var(--color-brand-accent)] focus:outline-none"
                  aria-label="Filter by status"
                >
                  <option value="">Open &amp; acknowledged</option>
                  <option value="open">Open only</option>
                  <option value="acknowledged">Acknowledged</option>
                </select>
              </div>
            </div>
          </div>

          {/* Bulk selection bar */}
          {selectionTargets.length > 0 && (
            <div className="flex items-center justify-between rounded-xl border border-[var(--color-brand-accent)]/30 bg-[var(--color-brand-accent)]/5 px-4 py-3 animate-fade-in-up">
              <p className="text-sm font-semibold text-[var(--color-text-primary)]">
                {selectionTargets.length} selected
              </p>
              <div className="flex items-center gap-2">
                {canResolve && (
                  <Button size="sm" onClick={() => openResolve(selectionTargets)}>
                    Resolve selected
                  </Button>
                )}
                <Button variant="outline" size="sm" onClick={() => setSelected(new Set())}>
                  Clear
                </Button>
              </div>
            </div>
          )}

          {/* Attention required */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <div>
                <h2 className="text-base font-semibold text-[var(--color-text-primary)]">Attention Required</h2>
                <p className="text-sm text-[var(--color-text-tertiary)] mt-0.5">
                  {visible.length} action{visible.length !== 1 ? 's' : ''} · from live school data
                </p>
              </div>
              {allSelected && (
                <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>
                  Clear selection
                </Button>
              )}
            </div>

            {visible.length === 0 ? (
              <EmptyState
                compact
                title={attentionCount === 0 ? 'All clear' : 'No actions match'}
                description={
                  attentionCount === 0
                    ? 'Nothing needs your attention right now. We\'ll surface new actions as data changes.'
                    : 'No actions match the current filters. Try widening your search.'
                }
                action={
                  attentionCount === 0
                    ? undefined
                    : {
                        label: 'Clear filters',
                        onClick: () => setSearchParams(new URLSearchParams()),
                      }
                }
              />
            ) : (
              <div ref={listRef} role="list" aria-label="Attention actions" onKeyDown={handleListKeyDown} className="space-y-2.5">
                {visible.map((item, i) => (
                  <ActionRow
                    key={item.id}
                    item={item}
                    index={i}
                    active={i === activeIndex}
                    selectable={item.source === 'risk' && item.status !== 'resolved'}
                    selected={selected.has(item.id)}
                    canResolve={canResolve}
                    canAcknowledge={canAcknowledge}
                    busy={busy}
                    onSelect={toggleSelect}
                    onNavigate={() => item.drillDown && navigate(item.drillDown)}
                    onResolve={() => openResolve([item])}
                    onAcknowledge={() => handleAcknowledge(item)}
                  />
                ))}
              </div>
            )}
          </section>

          {/* Recently resolved */}
          {resolved.length > 0 && (
            <section>
              <div className="mb-3">
                <h2 className="text-base font-semibold text-[var(--color-text-primary)]">Recently Resolved</h2>
                <p className="text-sm text-[var(--color-text-tertiary)] mt-0.5">Audited risk findings resolved recently</p>
              </div>
              <div role="list" aria-label="Recently resolved actions" className="space-y-2.5">
                {resolved.slice(0, 5).map((item, i) => (
                  <ActionRow
                    key={item.id}
                    item={item}
                    index={i}
                    active={false}
                    selectable={false}
                    selected={false}
                    canResolve={false}
                    canAcknowledge={false}
                    busy={false}
                    onSelect={() => {}}
                    onNavigate={() => item.drillDown && navigate(item.drillDown)}
                    onResolve={() => {}}
                    onAcknowledge={() => {}}
                  />
                ))}
              </div>
            </section>
          )}
        </>
      )}

      {/* Resolve dialog — audited, reason recorded */}
      <Modal
        open={resolveTargets.length > 0}
        onClose={() => setResolveTargets([])}
        title={resolveTargets.length > 1 ? `Resolve ${resolveTargets.length} actions` : 'Resolve action'}
        size="sm"
        footer={
          <>
            <Button variant="outline" size="sm" onClick={() => setResolveTargets([])}>Cancel</Button>
            <Button size="sm" onClick={handleResolve} disabled={busy}>
              {busy ? 'Resolving…' : 'Resolve'}
            </Button>
          </>
        }
      >
        <p className="text-xs text-[var(--color-text-tertiary)]">
          {resolveTargets.length > 1
            ? `This will resolve ${resolveTargets.length} selected risk findings. The reason is recorded in the audit trail.`
            : resolveTargets[0]?.title}
        </p>
        <textarea
          value={resolveReason}
          onChange={(e) => setResolveReason(e.target.value)}
          placeholder="Reason (audited) — e.g. fees paid in cash, parent contacted"
          rows={3}
          className="mt-4 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text-primary)] focus:border-[var(--color-brand-accent)] focus:outline-none resize-none"
        />
      </Modal>
    </div>
  )
}

export default ActionCenterPage
