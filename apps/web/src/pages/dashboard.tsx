import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../api/auth/auth-context'
import { analyticsApi } from '../api/analytics/analytics-api'
import { attendanceAnalyticsApi } from '../api/analytics/attendance-analytics-api'
import { commandCenterApi } from '../api/command-center/command-center-api'
import type { AnalyticsOverview, AttendanceOverview } from '../api/analytics/types'
import type { AttentionAlert, CommandCenterOverview } from '../api/command-center/command-center-api'
import { Loading, ErrorState, AnimatedCount, Badge } from '../components/ui'
import { AttendanceStatusChart } from '../components/analytics/attendance-status-chart'
import { cn } from '../lib/utils'
import { formatCurrency } from '../lib/utils'

const alertSeverityStyles: Record<string, string> = {
  critical: 'border-[var(--color-danger)]/25 bg-[var(--color-danger)]/5',
  warning: 'border-[var(--color-warning)]/25 bg-[var(--color-warning)]/5',
  info: 'border-[var(--color-info)]/25 bg-[var(--color-info)]/5',
}

const alertSeverityDot: Record<string, string> = {
  critical: 'bg-[var(--color-danger)]',
  warning: 'bg-[var(--color-warning)]',
  info: 'bg-[var(--color-info)]',
}

const alertSeverityLabel: Record<string, string> = {
  critical: 'Critical',
  warning: 'Warning',
  info: 'Info',
}

const severityRank: Record<string, number> = { critical: 0, warning: 1, info: 2 }

export function DashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null)
  const [attendanceOverview, setAttendanceOverview] = useState<AttendanceOverview | null>(null)
  const [attentionAlerts, setAttentionAlerts] = useState<AttentionAlert[]>([])
  const [attentionFeedState, setAttentionFeedState] = useState<'ok' | 'unavailable'>('ok')
  const [commandCenter, setCommandCenter] = useState<CommandCenterOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  useEffect(() => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)

    Promise.all([
      analyticsApi.getOverview(),
      attendanceAnalyticsApi.getOverview().catch(() => null),
      // Real operational attention feed (non-fatal — the analytics surface
      // is the primary dashboard; if the command center is down we fall
      // back to the analytics-derived cards below).
      commandCenterApi.getOverview().catch(() => null),
    ])
      .then(([ov, att, cmd]) => {
        if (fetchId === fetchIdRef.current) {
          setOverview(ov)
          setAttendanceOverview(att)
          setCommandCenter(cmd)
          if (cmd && cmd.needs_attention.available) {
            setAttentionAlerts(cmd.needs_attention.alerts)
            setAttentionFeedState('ok')
          } else {
            // Either the feed failed to load or its section is off — never
            // claim "all clear" on a feed we couldn't read.
            setAttentionAlerts([])
            setAttentionFeedState('unavailable')
          }
        }
      })
      .catch((err: any) => {
        if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load dashboard')
      })
      .finally(() => {
        if (fetchId === fetchIdRef.current) setLoading(false)
      })
  }, [])

  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'

  if (loading) {
    return (
      <div className="space-y-8 animate-fade-in">
        <div className="space-y-3">
          <div className="h-8 w-72 rounded-lg bg-[var(--color-border)] animate-skeleton" />
          <div className="h-5 w-96 rounded bg-[var(--color-border)] animate-skeleton" />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 h-48 rounded-2xl bg-[var(--color-border)] animate-skeleton" />
          <div className="h-48 rounded-2xl bg-[var(--color-border)] animate-skeleton" />
        </div>
        <div className="h-64 rounded-2xl bg-[var(--color-border)] animate-skeleton" />
      </div>
    )
  }

  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />
  if (!overview) return <ErrorState message="Unable to load dashboard data." />

  const isAttendanceGood = (overview.overall_attendance_percentage || 0) >= 90
  const isCollectionGood = (overview.collection_percentage || 0) >= 80

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Hero / Command Center */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-[var(--color-brand-navy)] via-[var(--color-brand-navy-light)] to-[var(--color-brand-navy-mid)] p-8 lg:p-10">
        <div className="absolute inset-0 opacity-[0.03]"
          style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.3) 1px, transparent 1px)', backgroundSize: '40px 40px' }}
        />
        <div className="relative">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            <div className="space-y-2">
              <p className="text-sm font-medium text-[var(--color-brand-accent)] tracking-wide">
                {greeting}, {user?.display_name || user?.username || 'Administrator'}
              </p>
              <h1 className="text-3xl lg:text-4xl font-extrabold text-white leading-tight tracking-tight">
                Your school command center
              </h1>
              <p className="text-white/50 text-base max-w-xl leading-relaxed">
                {`Your school has ${overview.total_students} student${overview.total_students !== 1 ? 's' : ''} across ${overview.total_sections} section${overview.total_sections !== 1 ? 's' : ''}. Attendance is ${overview.overall_attendance_percentage}% ${isAttendanceGood ? '— looking great.' : '— needs attention.'}`}
                {overview.total_outstanding > 0 && (
                  <> {formatCurrency(overview.total_outstanding)} is outstanding across {overview.unpaid_count} student{overview.unpaid_count !== 1 ? 's' : ''}.</>
                )}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => navigate('/students')}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[var(--color-brand-accent)] text-white text-sm font-medium hover:bg-[var(--color-brand-accent-hover)] transition-colors shadow-lg shadow-[var(--color-brand-accent)]/20"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Quick Actions
              </button>
              <button
                onClick={() => navigate('/reports')}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white/10 text-white text-sm font-medium hover:bg-white/20 transition-colors"
              >
                View Reports
              </button>
            </div>
          </div>

          {/* Mini metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-8">
            {[
              { label: 'Total Students', value: overview.total_students, accent: 'text-[var(--color-brand-accent)]' },
              { label: 'Teachers', value: overview.total_teachers, accent: 'text-emerald-400' },
              { label: 'Classes', value: overview.total_classes, accent: 'text-amber-400' },
              { label: 'Subjects', value: overview.total_subjects, accent: 'text-rose-400' },
            ].map((m, i) => (
              <div
                key={m.label}
                className="bg-white/5 rounded-xl p-4 border border-white/[0.06] animate-fade-in-up"
                style={{ animationDelay: `${i * 80}ms`, animationFillMode: 'both' }}
              >
                <p className="text-xs text-white/40 font-medium tracking-wide uppercase">{m.label}</p>
                <p className={`text-2xl font-bold text-white mt-1 ${m.accent}`}>
                  <AnimatedCount value={m.value} duration={1000 + i * 200} />
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* School Health Score — deterministic composite, explainable dimensions */}
      {commandCenter?.school_health?.score?.available && commandCenter.school_health.score.overall != null && (
        <section aria-label="School health score">
          <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
            <div className="flex flex-col lg:flex-row lg:items-center gap-6">
              {/* Composite score */}
              <div className="flex items-center gap-4 flex-shrink-0">
                <div
                  className={cn(
                    'flex items-center justify-center h-20 w-20 rounded-2xl border text-2xl font-extrabold tabular-nums',
                    (commandCenter.school_health.score.overall ?? 0) >= 85
                      ? 'border-[var(--color-success)]/30 bg-[var(--color-success)]/10 text-[var(--color-success)]'
                      : (commandCenter.school_health.score.overall ?? 0) >= 70
                        ? 'border-[var(--color-warning)]/30 bg-[var(--color-warning)]/10 text-[var(--color-warning)]'
                        : 'border-[var(--color-danger)]/30 bg-[var(--color-danger)]/10 text-[var(--color-danger)]'
                  )}
                >
                  {Math.round(commandCenter.school_health.score.overall)}
                </div>
                <div>
                  <h2 className="text-base font-semibold text-[var(--color-text-primary)]">School Health Score</h2>
                  <p className="text-sm text-[var(--color-text-tertiary)] mt-0.5">
                    Deterministic weighted composite · what changed
                  </p>
                  <button
                    onClick={() => navigate('/command-center')}
                    className="mt-1.5 text-xs font-medium text-[var(--color-brand-accent)] hover:text-[var(--color-brand-accent-hover)] motion-safe:transition-colors"
                  >
                    Open Command Center
                    <svg className="h-3 w-3 inline-block ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </button>
                </div>
              </div>

              {/* Dimension scores with trend deltas */}
              <div className="flex-1 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                {commandCenter.school_health.score.dimensions.map((d) => (
                  <button
                    key={d.key}
                    onClick={() => d.drill_down && navigate(d.drill_down)}
                    disabled={!d.drill_down}
                    className={cn(
                      'rounded-xl border border-[var(--color-border)] bg-[var(--color-bg)] p-3 text-left',
                      'motion-safe:transition-all motion-safe:duration-[var(--motion-fast)]',
                      d.drill_down && 'hover:border-[var(--color-brand-accent)]/30 hover:shadow-sm cursor-pointer'
                    )}
                  >
                    <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-text-tertiary)]">
                      {d.label}
                    </p>
                    <p className="mt-1 text-lg font-bold tabular-nums text-[var(--color-text-primary)]">
                      {Math.round(d.score)}
                    </p>
                    {(() => {
                      const metric = d.metrics?.[0]
                      const trend = metric?.trend
                      if (trend == null) return <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">current</p>
                      const up = trend >= 0
                      return (
                        <p className={cn('text-[11px] font-medium mt-0.5 tabular-nums', up ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]')}>
                          {up ? '↑' : '↓'} {Math.abs(trend).toFixed(1)}{typeof metric?.display === 'string' && metric.display.includes('%') ? '%' : ''} vs last period
                        </p>
                      )
                    })()}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Attention Required — real operational feed from the command center */}
      <section aria-label="Attention required">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-base font-semibold text-[var(--color-text-primary)]">Attention Required</h2>
            <p className="text-sm text-[var(--color-text-tertiary)] mt-0.5">
              {attentionFeedState === 'unavailable'
                ? 'Live alert feed could not be loaded'
                : attentionAlerts.length > 0
                  ? 'Highest-priority items from live school data'
                  : 'The most important things you should look at'}
            </p>
          </div>
          <button
            onClick={() => navigate('/action-center')}
            className="inline-flex items-center gap-1 text-sm font-medium text-[var(--color-brand-accent)] hover:text-[var(--color-brand-accent-hover)] motion-safe:transition-colors"
          >
            View all
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>

        {attentionFeedState === 'unavailable' ? (
          <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 flex items-center gap-3">
            <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-surface-hover)] flex-shrink-0">
              <svg className="h-4.5 w-4.5 text-[var(--color-text-tertiary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-semibold text-[var(--color-text-primary)]">Attention feed unavailable</p>
              <p className="text-xs text-[var(--color-text-tertiary)]">Couldn't load live alerts — the rest of your dashboard is up to date.</p>
            </div>
          </div>
        ) : attentionAlerts.length === 0 ? (
          <div className="rounded-2xl border border-[var(--color-success)]/20 bg-[var(--color-success)]/5 p-6 flex items-center gap-3">
            <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-success)]/10 flex-shrink-0">
              <svg className="h-4.5 w-4.5 text-[var(--color-success)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-semibold text-[var(--color-success-dark)]">All clear</p>
              <p className="text-xs text-[var(--color-success)]/70">No operational alerts right now.</p>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-2.5">
            {[...attentionAlerts]
              .sort((a, b) => (severityRank[a.severity] ?? 9) - (severityRank[b.severity] ?? 9))
              .slice(0, 5)
              .map((a) => (
                <button
                  key={a.id}
                  onClick={() => a.drill_down && navigate(a.drill_down)}
                  disabled={!a.drill_down}
                  className={cn(
                    'group flex items-start gap-3 rounded-xl border p-4 text-left',
                    'motion-safe:transition-all motion-safe:duration-[var(--motion-fast)]',
                    'hover:shadow-sm hover:-translate-y-0.5 motion-reduce:hover:translate-y-0',
                    alertSeverityStyles[a.severity],
                    a.drill_down ? 'cursor-pointer' : 'cursor-default'
                  )}
                >
                  <span className={cn('mt-1.5 inline-block h-2 w-2 rounded-full flex-shrink-0', alertSeverityDot[a.severity])} aria-hidden="true" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-sm font-semibold text-[var(--color-text-primary)]">{a.title}</p>
                      <Badge
                        variant={a.severity === 'critical' ? 'danger' : a.severity === 'warning' ? 'warning' : 'info'}
                        size="sm"
                      >
                        {alertSeverityLabel[a.severity]}
                      </Badge>
                    </div>
                    <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">{a.message}</p>
                  </div>
                  {a.drill_down && (
                    <svg className="h-3.5 w-3.5 text-[var(--color-text-muted)] flex-shrink-0 opacity-0 group-hover:opacity-100 motion-safe:transition-opacity" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  )}
                </button>
              ))}
          </div>
        )}
      </section>

      {/* Pulse Areas */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Attendance Pulse */}
        <div className="lg:col-span-2 bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-6 hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-base font-semibold text-[var(--color-text-primary)]">Attendance Pulse</h2>
              <p className="text-sm text-[var(--color-text-tertiary)] mt-0.5">Current period overview</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1.5 text-sm font-semibold text-[var(--color-text-primary)]">
                <span className={`inline-block h-2 w-2 rounded-full ${isAttendanceGood ? 'bg-[var(--color-success)]' : 'bg-[var(--color-danger)]'} animate-pulse-soft`} />
                <AnimatedCount value={overview.overall_attendance_percentage || 0} duration={1000} suffix="%" />
              </span>
            </div>
          </div>

          {attendanceOverview && attendanceOverview.total_records > 0 ? (
            <div className="space-y-5">
              <AttendanceStatusChart data={attendanceOverview} loading={false} />
              <div className="grid grid-cols-4 gap-2">
                {[
                  { label: 'Present', count: attendanceOverview.present, color: 'text-[var(--color-success)]', bg: 'bg-[var(--color-success)]/5' },
                  { label: 'Absent', count: attendanceOverview.absent, color: 'text-[var(--color-danger)]', bg: 'bg-[var(--color-danger)]/5' },
                  { label: 'Late', count: attendanceOverview.late, color: 'text-[var(--color-warning)]', bg: 'bg-[var(--color-warning)]/5' },
                  { label: 'Excused', count: attendanceOverview.excused, color: 'text-[var(--color-info)]', bg: 'bg-[var(--color-info)]/5' },
                ].map((s) => (
                  <div key={s.label} className={`text-center p-3 rounded-xl ${s.bg}`}>
                    <p className={`text-xl font-bold ${s.color}`}>
                      <AnimatedCount value={s.count} duration={800} />
                    </p>
                    <p className="text-xs text-[var(--color-text-tertiary)]">{s.label}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8">
              <p className="text-sm text-[var(--color-text-tertiary)]">No attendance records yet.</p>
              <button onClick={() => navigate('/attendance/daily')} className="text-sm text-[var(--color-brand-accent)] hover:underline mt-2">
                Record attendance &rarr;
              </button>
            </div>
          )}
        </div>

        {/* Attention Zone */}
        <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-6">
          <h2 className="text-base font-semibold text-[var(--color-text-primary)] mb-5">Needs Attention</h2>
          <div className="space-y-3">
            {/* Low attendance */}
            {overview.low_attendance_count > 0 ? (
              <div className="rounded-xl bg-[var(--color-danger)]/5 border border-[var(--color-danger)]/15 p-4 hover:shadow-sm hover:-translate-y-0.5 transition-all duration-[var(--motion-fast)] motion-reduce:transition-none motion-reduce:hover:translate-y-0">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-danger)]/10">
                      <svg className="h-4.5 w-4.5 text-[var(--color-danger)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01" />
                      </svg>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-[var(--color-danger-dark)]">Low Attendance</p>
                      <p className="text-xs text-[var(--color-danger)]/70">{overview.low_attendance_count} students below 90%</p>
                    </div>
                  </div>
                  <span className="text-xl font-bold text-[var(--color-danger)]">
                    <AnimatedCount value={overview.low_attendance_count} duration={800} />
                  </span>
                </div>
              </div>
            ) : (
              <div className="rounded-xl bg-[var(--color-success)]/5 border border-[var(--color-success)]/15 p-4 hover:shadow-sm hover:-translate-y-0.5 transition-all duration-[var(--motion-fast)] motion-reduce:transition-none motion-reduce:hover:translate-y-0">
                <div className="flex items-center gap-3">
                  <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-success)]/10">
                    <svg className="h-4.5 w-4.5 text-[var(--color-success)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-[var(--color-success-dark)]">All clear</p>
                    <p className="text-xs text-[var(--color-success)]/70">All students meet attendance threshold</p>
                  </div>
                </div>
              </div>
            )}

            {/* Unpaid Fees */}
            {overview.unpaid_count > 0 && (
              <div className="rounded-xl bg-[var(--color-warning)]/5 border border-[var(--color-warning)]/15 p-4 hover:shadow-sm hover:-translate-y-0.5 transition-all duration-[var(--motion-fast)] motion-reduce:transition-none motion-reduce:hover:translate-y-0">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-warning)]/10">
                      <svg className="h-4.5 w-4.5 text-[var(--color-warning)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1" />
                      </svg>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-[var(--color-warning-dark)]">Unpaid Fees</p>
                      <p className="text-xs text-[var(--color-warning)]/70">{overview.unpaid_count} students with no payments</p>
                    </div>
                  </div>
                  <span className="text-xl font-bold text-[var(--color-warning)]">
                    <AnimatedCount value={overview.unpaid_count} duration={800} />
                  </span>
                </div>
              </div>
            )}

            {/* Partially Paid */}
            {overview.partially_paid_count > 0 && (
              <div className="rounded-xl bg-[var(--color-info)]/5 border border-[var(--color-info)]/15 p-4 hover:shadow-sm hover:-translate-y-0.5 transition-all duration-[var(--motion-fast)] motion-reduce:transition-none motion-reduce:hover:translate-y-0">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-info)]/10">
                      <svg className="h-4.5 w-4.5 text-[var(--color-info)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01" />
                      </svg>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-[var(--color-info-dark)]">Partial Payments</p>
                      <p className="text-xs text-[var(--color-info)]/70">{overview.partially_paid_count} students partially paid</p>
                    </div>
                  </div>
                  <span className="text-xl font-bold text-[var(--color-info)]">
                    <AnimatedCount value={overview.partially_paid_count} duration={800} />
                  </span>
                </div>
              </div>
            )}

            {/* Financial Status */}
            <div className="rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)] p-4 hover:shadow-sm hover:-translate-y-0.5 transition-all duration-[var(--motion-fast)] motion-reduce:transition-none motion-reduce:hover:translate-y-0">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-[var(--color-text-tertiary)]">Fees Collected</span>
                <span className="text-xs font-semibold text-[var(--color-text-primary)]">
                  <AnimatedCount value={overview.collection_percentage || 0} duration={1000} suffix="%" />
                </span>
              </div>
              <div className="h-2 rounded-full bg-[var(--color-border)] overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-1000 ${isCollectionGood ? 'bg-[var(--color-success)]' : 'bg-[var(--color-warning)]'}`}
                  style={{ width: `${Math.min(overview.collection_percentage, 100)}%` }}
                />
              </div>
              <div className="flex justify-between mt-2">
                <p className="text-xs text-[var(--color-text-tertiary)]">{formatCurrency(overview.total_collected)} collected</p>
                <p className="text-xs text-[var(--color-text-tertiary)]">{formatCurrency(overview.total_outstanding)} outstanding</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Navigation */}
      <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-6 hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-semibold text-[var(--color-text-primary)]">Quick Navigation</h2>
            <p className="text-sm text-[var(--color-text-tertiary)] mt-0.5">Press <kbd className="inline-flex items-center px-1.5 py-0.5 rounded bg-[var(--color-bg)] border border-[var(--color-border)] text-[10px] font-medium">⌘K</kbd> to access all pages</p>
          </div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
          {[
            { label: 'Students', path: '/students', icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197' },
            { label: 'Teachers', path: '/teachers', icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z' },
            { label: 'Academics', path: '/academic', icon: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3' },
            { label: 'Attendance', path: '/attendance', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2' },
            { label: 'Fees', path: '/fees', icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1' },
            { label: 'Reports', path: '/reports', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10' },
            { label: 'Analytics', path: '/analytics', icon: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6' },
            { label: 'Operations', path: '/operations', icon: 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581' },
          ].map((link, i) => (
            <button
              key={link.path}
              onClick={() => navigate(link.path)}
              className="flex flex-col items-center gap-2 p-4 rounded-xl border border-[var(--color-border)] hover:border-[var(--color-brand-accent)]/30 hover:bg-[var(--color-brand-accent-subtle)] hover:-translate-y-0.5 transition-all motion-reduce:transition-none duration-[var(--motion-fast)] animate-fade-in"
              style={{ animationDelay: `${i * 60}ms`, animationFillMode: 'both' }}
            >
              <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-bg)]">
                <svg className="h-4.5 w-4.5 text-[var(--color-text-tertiary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={link.icon} />
                </svg>
              </div>
              <span className="text-xs font-medium text-[var(--color-text-secondary)]">{link.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
