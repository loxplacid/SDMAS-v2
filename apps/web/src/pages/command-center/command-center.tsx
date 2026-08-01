import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../api/auth/auth-context'
import { commandCenterApi, type CommandCenterOverview } from '../../api/command-center/command-center-api'
import { Timeline } from '../../components/timeline/timeline'
import { AnimatedCount, Badge, Skeleton } from '../../components/ui'
import { cn, formatDateTime } from '../../lib/utils'

// ── Helpers ───────────────────────────────────────────────────────────

const REFRESH_MS = 5 * 60 * 1000 // 5-minute auto-refresh

const severityStyles: Record<string, string> = {
  critical: 'border-[var(--color-danger)]/25 bg-[var(--color-danger)]/5',
  warning: 'border-[var(--color-warning)]/25 bg-[var(--color-warning)]/5',
  info: 'border-[var(--color-info)]/25 bg-[var(--color-info)]/5',
}

const severityDot: Record<string, string> = {
  critical: 'bg-[var(--color-danger)]',
  warning: 'bg-[var(--color-warning)]',
  info: 'bg-[var(--color-info)]',
}

const metricAccent: Record<string, string> = {
  good: 'text-[var(--color-success)]',
  warn: 'text-[var(--color-warning)]',
  critical: 'text-[var(--color-danger)]',
  info: 'text-[var(--color-info)]',
  neutral: 'text-[var(--color-text-primary)]',
}

const metricRing: Record<string, string> = {
  good: 'bg-[var(--color-success)]/10',
  warn: 'bg-[var(--color-warning)]/10',
  critical: 'bg-[var(--color-danger)]/10',
  info: 'bg-[var(--color-info)]/10',
  neutral: 'bg-[var(--color-bg)]',
}

const eventIcons: Record<string, string> = {
  attendance: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4',
  payment: 'M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2z',
  admission: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z',
  approval: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
  leave: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2zM7 14l3 3 7-7',
  announcement: 'M11 5.882V19.24a1.76 1.76 0 01-3.417.592l-2.147-6.15M18 13a3 3 0 100-6M5.436 13.683A4.001 4.001 0 017 6h1.832c4.1 0 7.625-1.234 9.168-3v14c-1.543-1.766-5.067-3-9.168-3H7a3.988 3.988 0 01-1.564-.317z',
}

const eventColors: Record<string, string> = {
  attendance: 'text-[var(--color-success)] bg-[var(--color-success)]/10',
  payment: 'text-[var(--color-info)] bg-[var(--color-info)]/10',
  admission: 'text-[var(--color-brand-accent)] bg-[var(--color-brand-accent)]/10',
  approval: 'text-[var(--color-warning)] bg-[var(--color-warning)]/10',
  leave: 'text-[var(--color-danger)] bg-[var(--color-danger)]/10',
  announcement: 'text-[var(--color-info)] bg-[var(--color-info)]/10',
}

const quickActionIcons: Record<string, string> = {
  'user-plus': 'M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z',
  'check-square': 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4',
  banknote: 'M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z',
  clipboard: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2',
  'thumbs-up': 'M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5',
  megaphone: 'M11 5.882V19.24a1.76 1.76 0 01-3.417.592l-2.147-6.15M18 13a3 3 0 100-6M5.436 13.683A4.001 4.001 0 017 6h1.832c4.1 0 7.625-1.234 9.168-3v14c-1.543-1.766-5.067-3-9.168-3H7a3.988 3.988 0 01-1.564-.317z',
}

function SectionFallback({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-10 text-center animate-fade-in">
      <div className="flex items-center justify-center h-11 w-11 rounded-xl bg-[var(--color-surface-hover)] mb-3">
        <svg className="h-5 w-5 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
        </svg>
      </div>
      <p className="text-sm font-medium text-[var(--color-text-secondary)]">{label} unavailable</p>
      <p className="text-xs text-[var(--color-text-tertiary)] mt-1 max-w-xs">
        This data source could not be reached. The rest of your dashboard is still up to date.
      </p>
    </div>
  )
}

// ── A. School Health ──────────────────────────────────────────────────

function HealthSection({ data }: { data: CommandCenterOverview['school_health'] }) {
  const navigate = useNavigate()
  if (!data.available) return <SectionFallback label="School health" />

  return (
    <section className="animate-fade-in-up" style={{ animationFillMode: 'both' }}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-[var(--color-text-primary)]">School Health</h2>
          <p className="text-sm text-[var(--color-text-tertiary)] mt-0.5">Key indicators at a glance</p>
        </div>
        <Badge variant="neutral" size="sm">Live</Badge>
      </div>

      {data.metrics.length === 0 ? (
        <p className="text-sm text-[var(--color-text-tertiary)] py-8 text-center">No metrics available yet.</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3">
          {data.metrics.map((m, i) => (
            <button
              key={m.key}
              onClick={() => m.drill_down && navigate(m.drill_down)}
              disabled={!m.drill_down}
              className={cn(
                'group relative overflow-hidden rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 text-left',
                'motion-safe:transition-all motion-safe:duration-[var(--motion-fast)] motion-safe:ease-[var(--ease-standard)]',
                'hover:-translate-y-0.5 hover:shadow-md hover:border-[var(--color-brand-accent)]/30 motion-reduce:hover:translate-y-0',
                m.drill_down ? 'cursor-pointer' : 'cursor-default',
                'animate-fade-in-up'
              )}
              style={{ animationDelay: `${i * 60}ms`, animationFillMode: 'both' }}
            >
              <div className={cn('absolute inset-x-0 top-0 h-0.5', metricRing[m.status])} aria-hidden="true" />
              <div className="flex items-center gap-1.5 mb-2">
                <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-text-tertiary)] truncate">
                  {m.label}
                </p>
              </div>
              <p className={cn('text-xl font-bold tabular-nums leading-none', metricAccent[m.status] || 'text-[var(--color-text-primary)]')}>
                <AnimatedCount value={m.value} duration={900 + i * 120} />
              </p>
              <p className="text-xs text-[var(--color-text-tertiary)] mt-1.5 truncate">
                {m.display}
                {m.drill_down && (
                  <span className="inline-flex items-center gap-0.5 ml-1 text-[var(--color-brand-accent)] opacity-0 group-hover:opacity-100 motion-safe:transition-opacity">
                    <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </span>
                )}
              </p>
            </button>
          ))}
        </div>
      )}

      {/* Trend sparklines where historical data exists */}
      {Object.keys(data.trends).length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
          {Object.entries(data.trends).map(([key, points]) => (
            <div key={key} className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
              <p className="text-xs font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider mb-3">
                {key === 'attendance' ? 'Attendance Trend · 14 days' : 'Collection Trend · 30 days'}
              </p>
              <Sparkline points={points.map((p) => p.value)} />
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function Sparkline({ points }: { points: number[] }) {
  if (points.length < 2) return <p className="text-xs text-[var(--color-text-tertiary)]">Not enough data yet.</p>
  const w = 600
  const h = 80
  const max = Math.max(...points)
  const min = Math.min(...points)
  const range = max - min || 1
  const step = w / (points.length - 1)
  const coords = points.map((v, i) => `${(i * step).toFixed(1)},${(h - 8 - ((v - min) / range) * (h - 16)).toFixed(1)}`)
  const path = `M${coords.join(' L')}`
  const area = `${path} L${w},${h} L0,${h} Z`

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-20" role="img" aria-label="Trend line">
      <defs>
        <linearGradient id={`spark-${points.length}-${Math.round(max * 100)}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--color-brand-accent)" stopOpacity="0.25" />
          <stop offset="100%" stopColor="var(--color-brand-accent)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#spark-${points.length}-${Math.round(max * 100)})`} />
      <path
        d={path}
        fill="none"
        stroke="var(--color-brand-accent)"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        className="animate-draw"
      />
    </svg>
  )
}

// ── B. Needs Attention ────────────────────────────────────────────────

function AttentionSection({ data }: { data: CommandCenterOverview['needs_attention'] }) {
  const navigate = useNavigate()
  if (!data.available) return <SectionFallback label="Alerts" />

  return (
    <section className="animate-fade-in-up" style={{ animationFillMode: 'both' }}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-[var(--color-text-primary)]">Needs Attention</h2>
          <p className="text-sm text-[var(--color-text-tertiary)] mt-0.5">Actionable items for today</p>
        </div>
        {data.alerts.length > 0 && (
          <Badge variant={data.alerts.some((a) => a.severity === 'critical') ? 'danger' : 'warning'} size="sm" dot>
            {data.alerts.length} item{data.alerts.length !== 1 ? 's' : ''}
          </Badge>
        )}
      </div>

      {data.alerts.length === 0 ? (
        <div className="rounded-2xl border border-[var(--color-success)]/20 bg-[var(--color-success)]/5 p-6 flex items-center gap-3">
          <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-success)]/10">
            <svg className="h-4.5 w-4.5 text-[var(--color-success)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-semibold text-[var(--color-success-dark)]">All clear</p>
            <p className="text-xs text-[var(--color-success)]/70">Nothing needs your attention right now.</p>
          </div>
        </div>
      ) : (
        <div className="space-y-2.5">
          {data.alerts.map((a, i) => (
            <div
              key={a.id}
              className={cn(
                'rounded-xl border p-4 motion-safe:transition-all motion-safe:duration-[var(--motion-fast)]',
                'hover:shadow-sm hover:-translate-y-0.5 motion-reduce:hover:translate-y-0',
                severityStyles[a.severity],
                'animate-fade-in-up'
              )}
              style={{ animationDelay: `${i * 70}ms`, animationFillMode: 'both' }}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3 min-w-0">
                  <span className={cn('mt-1.5 inline-block h-2 w-2 rounded-full flex-shrink-0', severityDot[a.severity])} aria-hidden="true" />
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-[var(--color-text-primary)]">{a.title}</p>
                    <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">{a.message}</p>
                  </div>
                </div>
                {a.drill_down && (
                  <button
                    onClick={() => navigate(a.drill_down!)}
                    className="flex-shrink-0 inline-flex items-center gap-1 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/40 hover:text-[var(--color-brand-accent)] motion-safe:transition-colors"
                  >
                    {a.action_label}
                    <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

// ── C. Today ──────────────────────────────────────────────────────────

function TodaySection({ data }: { data: CommandCenterOverview['today'] }) {
  const navigate = useNavigate()
  if (!data.available) return <SectionFallback label="Today's activity" />

  return (
    <section className="animate-fade-in-up" style={{ animationFillMode: 'both' }}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-[var(--color-text-primary)]">Today</h2>
          <p className="text-sm text-[var(--color-text-tertiary)] mt-0.5">What happened in your school today</p>
        </div>
        <Badge variant="info" size="sm" dot>Today</Badge>
      </div>

      {data.events.length === 0 ? (
        <p className="text-sm text-[var(--color-text-tertiary)] py-8 text-center">No events recorded today yet.</p>
      ) : (
        <div className="space-y-1">
          {data.events.map((e, i) => (
            <button
              key={e.id}
              onClick={() => e.drill_down && navigate(e.drill_down)}
              disabled={!e.drill_down}
              className={cn(
                'w-full flex items-center gap-3 rounded-xl px-3 py-3 text-left',
                'motion-safe:transition-colors motion-safe:duration-[var(--motion-fast)]',
                e.drill_down ? 'hover:bg-[var(--color-surface-hover)] cursor-pointer' : 'cursor-default',
                'animate-fade-in-left'
              )}
              style={{ animationDelay: `${i * 60}ms`, animationFillMode: 'both' }}
            >
              <div className={cn('flex items-center justify-center h-9 w-9 rounded-xl flex-shrink-0', eventColors[e.type])}>
                <svg className="h-4.5 w-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={eventIcons[e.type] || eventIcons.attendance} />
                </svg>
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-[var(--color-text-primary)] truncate">{e.title}</p>
                <p className="text-xs text-[var(--color-text-tertiary)] truncate">{e.description}</p>
              </div>
              {e.drill_down && (
                <svg className="h-3.5 w-3.5 text-[var(--color-text-muted)] flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              )}
            </button>
          ))}
        </div>
      )}
    </section>
  )
}

// ── D. Quick Actions ──────────────────────────────────────────────────

function QuickActionsSection({ actions }: { actions: CommandCenterOverview['quick_actions'] }) {
  const navigate = useNavigate()
  return (
    <section className="animate-fade-in-up" style={{ animationFillMode: 'both' }}>
      <div className="mb-4">
        <h2 className="text-base font-semibold text-[var(--color-text-primary)]">Quick Actions</h2>
        <p className="text-sm text-[var(--color-text-tertiary)] mt-0.5">Jump straight to common tasks</p>
      </div>
      {actions.length === 0 ? (
        <p className="text-sm text-[var(--color-text-tertiary)] py-8 text-center">No quick actions for your role.</p>
      ) : (
        <div className="grid grid-cols-2 gap-2.5">
          {actions.map((a, i) => (
            <button
              key={a.id}
              onClick={() => navigate(a.route)}
              className={cn(
                'group flex flex-col gap-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3.5 text-left',
                'motion-safe:transition-all motion-safe:duration-[var(--motion-fast)] motion-safe:ease-[var(--ease-spring)]',
                'hover:-translate-y-0.5 hover:shadow-md hover:border-[var(--color-brand-accent)]/30 motion-reduce:hover:translate-y-0',
                'animate-fade-in-up'
              )}
              style={{ animationDelay: `${i * 60}ms`, animationFillMode: 'both' }}
            >
              <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-[var(--color-brand-accent-subtle)] text-[var(--color-brand-accent)] group-hover:scale-110 motion-safe:transition-transform motion-safe:duration-[var(--motion-fast)]">
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={quickActionIcons[a.icon] || quickActionIcons['user-plus']} />
                </svg>
              </div>
              <div className="min-w-0">
                <p className="text-xs font-semibold text-[var(--color-text-primary)] truncate">{a.label}</p>
                <p className="text-[11px] text-[var(--color-text-tertiary)] truncate">{a.description}</p>
              </div>
            </button>
          ))}
        </div>
      )}
    </section>
  )
}

// ── E. Recent Activity (unified operational timeline) ────────────────

function ActivitySection() {
  return (
    <section className="animate-fade-in-up" style={{ animationFillMode: 'both' }}>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-[var(--color-text-primary)]">Recent Activity</h2>
          <p className="text-sm text-[var(--color-text-tertiary)] mt-0.5">Latest changes across the school</p>
        </div>
      </div>
      <Timeline params={{ entity_type: 'school' }} compact pageSize={10} maxVisible={6} />
    </section>
  )
}

// ── Full-page skeleton ────────────────────────────────────────────────

function CommandCenterSkeleton() {
  return (
    <div className="space-y-8 animate-fade-in" aria-busy="true" aria-label="Loading command center">
      <div className="space-y-3">
        <Skeleton className="h-8 w-72" />
        <Skeleton className="h-4 w-96" />
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-24 rounded-2xl" />
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Skeleton className="h-64 rounded-2xl" />
        <Skeleton className="h-64 rounded-2xl" />
      </div>
      <Skeleton className="h-40 rounded-2xl" />
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────

export function CommandCenterPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [data, setData] = useState<CommandCenterOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const fetchIdRef = useRef(0)
  const dataRef = useRef<CommandCenterOverview | null>(null)

  const load = useCallback(async (background = false) => {
    const fetchId = ++fetchIdRef.current
    if (background) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }
    setError(null)
    try {
      const overview = await commandCenterApi.getOverview()
      if (fetchId === fetchIdRef.current) {
        dataRef.current = overview
        setData(overview)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current && !dataRef.current) {
        setError(err?.detail || 'Failed to load the command center')
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
    // Auto-refresh every 5 minutes
    const timer = setInterval(() => load(true), REFRESH_MS)
    return () => {
      clearInterval(timer)
      fetchIdRef.current++
    }
  }, [load])

  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'

  const roleLabel = data?.role
    ? ({ admin: 'Administrator', principal: 'Principal', accountant: 'Accountant', staff: 'Staff', teacher: 'Teacher' } as Record<string, string>)[data.role] || data.role
    : ''

  return (
    <div className="space-y-8 animate-fade-in">
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
                {greeting}, {user?.display_name || user?.username || 'Leader'}
              </p>
              <h1 className="text-2xl lg:text-3xl font-extrabold text-white leading-tight tracking-tight">
                School Command Center
              </h1>
              <p className="text-white/50 text-sm max-w-xl leading-relaxed">
                {data?.academic_year
                  ? `${roleLabel} overview · Academic year ${data.academic_year}`
                  : `${roleLabel} overview`}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {data && (
                <span className="inline-flex items-center gap-1.5 text-xs text-white/40 mr-1">
                  <span className={cn('inline-block h-1.5 w-1.5 rounded-full', refreshing ? 'bg-[var(--color-brand-accent)] animate-pulse-soft' : 'bg-[var(--color-success)]')} aria-hidden="true" />
                  Updated {formatDateTime(data.generated_at)}
                </span>
              )}
              <button
                onClick={() => load(true)}
                disabled={refreshing}
                className={cn(
                  'inline-flex items-center gap-2 rounded-xl bg-white/10 px-4 py-2 text-sm font-medium text-white',
                  'hover:bg-white/20 motion-safe:transition-colors',
                  refreshing && 'opacity-60 cursor-wait'
                )}
                aria-label="Refresh command center"
              >
                <svg className={cn('h-4 w-4', refreshing && 'animate-spin')} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Refresh
              </button>
              <button
                onClick={() => navigate('/reports')}
                className="inline-flex items-center gap-2 rounded-xl bg-[var(--color-brand-accent)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--color-brand-accent-hover)] motion-safe:transition-colors shadow-lg shadow-[var(--color-brand-accent)]/20"
              >
                View Reports
              </button>
            </div>
          </div>
        </div>
      </div>

      {loading ? (
        <CommandCenterSkeleton />
      ) : error ? (
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
            <svg className="h-4 w-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Try Again
          </button>
        </div>
      ) : data ? (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-8">
              <HealthSection data={data.school_health} />
              <TodaySection data={data.today} />
            </div>
            <div className="space-y-8">
              <AttentionSection data={data.needs_attention} />
              <QuickActionsSection actions={data.quick_actions} />
            </div>
          </div>
          <ActivitySection />
        </>
      ) : null}
    </div>
  )
}

export default CommandCenterPage
