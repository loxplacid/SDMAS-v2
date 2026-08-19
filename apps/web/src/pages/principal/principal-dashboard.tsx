import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../api/auth/auth-context'
import { analyticsApi } from '../../api/analytics/analytics-api'
import { attendanceAnalyticsApi } from '../../api/analytics/attendance-analytics-api'
import { financeAnalyticsApi } from '../../api/analytics/finance-analytics-api'
import type { AnalyticsOverview, AttendanceOverview, FinanceOverview } from '../../api/analytics/types'
import { ErrorState, PageHeader, Skeleton } from '../../components/ui'
import { formatCurrency, cn } from '../../lib/utils'

export function PrincipalDashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null)
  const [attendanceOverview, setAttendanceOverview] = useState<AttendanceOverview | null>(null)
  const [financeOverview, setFinanceOverview] = useState<FinanceOverview | null>(null)
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
      financeAnalyticsApi.getOverview().catch(() => null),
    ])
      .then(([ov, att, fin]) => {
        if (fetchId === fetchIdRef.current) { setOverview(ov); setAttendanceOverview(att); setFinanceOverview(fin) }
      })
      .catch((err: any) => { if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load dashboard') })
      .finally(() => { if (fetchId === fetchIdRef.current) setLoading(false) })
  }, [])

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="space-y-2"><Skeleton className="h-4 w-24" /><Skeleton className="h-7 w-56" /><Skeleton className="h-3 w-80" /></div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-20 rounded-xl" />)}</div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4"><Skeleton className="h-48 rounded-xl lg:col-span-2" /><Skeleton className="h-48 rounded-xl" /></div>
      </div>
    )
  }

  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />
  if (!overview) return <ErrorState message="Unable to load dashboard data." />

  const attendancePct = attendanceOverview?.attendance_percentage ?? overview.overall_attendance_percentage ?? 0
  const collectionPct = financeOverview?.collection_percentage ?? overview.collection_percentage ?? 0
  const isAttendanceGood = attendancePct >= 90
  const isCollectionGood = collectionPct >= 80

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <PageHeader
          eyebrow="Leadership"
          title={`Good ${new Date().getHours() < 12 ? 'morning' : new Date().getHours() < 17 ? 'afternoon' : 'evening'}, ${user?.display_name || 'Principal'}`}
          subtitle={`${overview.total_students} students, ${overview.total_teachers} teachers, ${overview.total_sections} sections`}
          compact
        />
        <div className="flex items-center gap-2 flex-shrink-0">
          <button onClick={() => navigate('/reports')} className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--color-brand-accent)] px-3 py-1.5 text-xs font-medium text-white hover:bg-[var(--color-brand-accent-hover)] motion-safe:transition-colors">View Reports</button>
          <button onClick={() => navigate('/analytics')} className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/30 hover:text-[var(--color-brand-accent)] motion-safe:transition-colors">Analytics</button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Students', value: overview.total_students },
          { label: 'Teachers', value: overview.total_teachers },
          { label: 'Sections', value: overview.total_sections },
          { label: 'Classes', value: overview.total_classes },
        ].map((m) => (
          <div key={m.label} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3.5">
            <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-text-tertiary)]">{m.label}</p>
            <p className="mt-1.5 text-xl font-bold tabular-nums leading-none text-[var(--color-text-primary)]">{m.value.toLocaleString()}</p>
          </div>
        ))}
      </div>

      {/* Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Attendance Pulse */}
        <div className="lg:col-span-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold text-[var(--color-text-primary)]">Attendance Pulse</h2>
              <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">Current period overview</p>
            </div>
            <span className={cn('text-sm font-semibold', isAttendanceGood ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]')}>
              {attendancePct}%
            </span>
          </div>
          {attendanceOverview && attendanceOverview.total_records > 0 ? (
            <div className="grid grid-cols-4 gap-2">
              {[
                { label: 'Present', count: attendanceOverview.present, color: 'text-[var(--color-success)]', bg: 'bg-[var(--color-success)]/5' },
                { label: 'Absent', count: attendanceOverview.absent, color: 'text-[var(--color-danger)]', bg: 'bg-[var(--color-danger)]/5' },
                { label: 'Late', count: attendanceOverview.late, color: 'text-[var(--color-warning)]', bg: 'bg-[var(--color-warning)]/5' },
                { label: 'Excused', count: attendanceOverview.excused, color: 'text-[var(--color-info)]', bg: 'bg-[var(--color-info)]/5' },
              ].map((s) => (
                <div key={s.label} className={cn('text-center p-3 rounded-lg', s.bg)}>
                  <p className={cn('text-lg font-bold tabular-nums', s.color)}>{s.count}</p>
                  <p className="text-[11px] text-[var(--color-text-tertiary)] mt-0.5">{s.label}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="py-6 text-center">
              <p className="text-xs text-[var(--color-text-tertiary)]">No attendance records yet.</p>
              <button onClick={() => navigate('/attendance/daily')} className="text-xs text-[var(--color-brand-accent)] hover:underline mt-1">Record attendance →</button>
            </div>
          )}
        </div>

        {/* Key Metrics */}
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <h2 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">Key Metrics</h2>
          <div className="space-y-2.5">
            {overview.low_attendance_count > 0 && (
              <div className="rounded-lg bg-[var(--color-danger)]/5 border border-[var(--color-danger)]/15 p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold text-[var(--color-danger-dark)]">Low Attendance</p>
                    <p className="text-[11px] text-[var(--color-danger)]">{overview.low_attendance_count} students below 90%</p>
                  </div>
                  <span className="text-lg font-bold text-[var(--color-danger)]">{overview.low_attendance_count}</span>
                </div>
              </div>
            )}
            <div className="rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] p-3">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[11px] font-medium text-[var(--color-text-tertiary)]">Fee Collection</span>
                <span className={cn('text-[11px] font-semibold', isCollectionGood ? 'text-[var(--color-success)]' : 'text-[var(--color-warning)]')}>{collectionPct}%</span>
              </div>
              <div className="h-1.5 rounded-full bg-[var(--color-border)] overflow-hidden">
                <div className={cn('h-full rounded-full', isCollectionGood ? 'bg-[var(--color-success)]' : 'bg-[var(--color-warning)]')} style={{ width: `${Math.min(collectionPct, 100)}%` }} />
              </div>
              <div className="flex justify-between mt-1.5">
                <p className="text-[10px] text-[var(--color-text-tertiary)]">{formatCurrency(financeOverview?.total_collected ?? overview.total_collected)} collected</p>
                <p className="text-[10px] text-[var(--color-text-tertiary)]">{formatCurrency(financeOverview?.total_outstanding ?? overview.total_outstanding)} outstanding</p>
              </div>
            </div>
            {(overview.unpaid_count > 0 || (financeOverview?.students_with_outstanding ?? 0) > 0) && (
              <div className="rounded-lg bg-[var(--color-warning)]/5 border border-[var(--color-warning)]/15 p-3">
                <p className="text-xs font-semibold text-[var(--color-warning-dark)]">Outstanding Fees</p>
                <p className="text-[11px] text-[var(--color-warning)]">{financeOverview?.students_with_outstanding ?? overview.unpaid_count} student(s) with outstanding</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Quick Access */}
      <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
        <h2 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">Quick Access</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {[
            { label: 'Students', path: '/students', icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197' },
            { label: 'Teachers', path: '/teachers', icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z' },
            { label: 'Academics', path: '/academic', icon: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3' },
            { label: 'Attendance', path: '/attendance', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2' },
            { label: 'Fees', path: '/fees', icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1' },
            { label: 'Reports', path: '/reports', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10' },
            { label: 'Analytics', path: '/analytics', icon: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6' },
            { label: 'Notifications', path: '/notifications', icon: 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341' },
          ].map((link) => (
            <button
              key={link.path}
              onClick={() => navigate(link.path)}
              className="flex items-center gap-2.5 p-3 rounded-lg border border-[var(--color-border)] text-left motion-safe:transition-colors motion-safe:duration-[var(--motion-fast)] hover:border-[var(--color-brand-accent)]/30"
            >
              <svg className="h-4 w-4 text-[var(--color-text-tertiary)] flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={link.icon} />
              </svg>
              <span className="text-xs font-medium text-[var(--color-text-secondary)]">{link.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
