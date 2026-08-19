import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../api/auth/auth-context'
import { analyticsApi } from '../../api/analytics/analytics-api'
import { attendanceAnalyticsApi } from '../../api/analytics/attendance-analytics-api'
import type { AnalyticsOverview, AttendanceOverview } from '../../api/analytics/types'
import { ErrorState, PageHeader, Skeleton } from '../../components/ui'
import { cn } from '../../lib/utils'

export function StaffDashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null)
  const [attendanceOverview, setAttendanceOverview] = useState<AttendanceOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  useEffect(() => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)
    Promise.all([analyticsApi.getOverview(), attendanceAnalyticsApi.getOverview().catch(() => null)])
      .then(([ov, att]) => { if (fetchId === fetchIdRef.current) { setOverview(ov); setAttendanceOverview(att) } })
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
  const isAttendanceGood = attendancePct >= 90

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <PageHeader
          eyebrow="Operations"
          title={`Good ${new Date().getHours() < 12 ? 'morning' : new Date().getHours() < 17 ? 'afternoon' : 'evening'}, ${user?.display_name || 'Staff'}`}
          subtitle={`${overview.total_students} students, ${overview.total_teachers} teachers, ${overview.total_sections} sections`}
          compact
        />
        <div className="flex items-center gap-2 flex-shrink-0">
          <button onClick={() => navigate('/attendance/daily')} className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--color-brand-accent)] px-3 py-1.5 text-xs font-medium text-white hover:bg-[var(--color-brand-accent-hover)] motion-safe:transition-colors">Attendance</button>
          <button onClick={() => navigate('/notifications')} className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/30 hover:text-[var(--color-brand-accent)] motion-safe:transition-colors">Notifications</button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Students', value: overview.total_students },
          { label: 'Teachers', value: overview.total_teachers },
          { label: 'Sections', value: overview.total_sections },
          { label: 'Subjects', value: overview.total_subjects },
        ].map((m) => (
          <div key={m.label} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3.5">
            <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-text-tertiary)]">{m.label}</p>
            <p className="mt-1.5 text-xl font-bold tabular-nums leading-none text-[var(--color-text-primary)]">{m.value.toLocaleString()}</p>
          </div>
        ))}
      </div>

      {/* Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Today's Overview */}
        <div className="lg:col-span-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold text-[var(--color-text-primary)]">Today's Overview</h2>
              <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">School-wide metrics at a glance</p>
            </div>
            <span className={cn('text-sm font-semibold', isAttendanceGood ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]')}>{attendancePct}%</span>
          </div>
          {attendanceOverview && attendanceOverview.total_records > 0 ? (
            <div className="grid grid-cols-4 gap-2">
              {[
                { label: 'Present', count: attendanceOverview.present, color: 'text-[var(--color-success)]', bg: 'bg-[var(--color-success)]/5' },
                { label: 'Absent', count: attendanceOverview.absent, color: 'text-[var(--color-danger)]', bg: 'bg-[var(--color-danger)]/5' },
                { label: 'Late', count: attendanceOverview.late, color: 'text-[var(--color-warning)]', bg: 'bg-[var(--color-warning)]/5' },
                { label: 'Records', count: attendanceOverview.total_records, color: 'text-[var(--color-info)]', bg: 'bg-[var(--color-info)]/5' },
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
            </div>
          )}
          <div className="grid grid-cols-3 gap-2 mt-4">
            <div className="p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
              <p className="text-[11px] text-[var(--color-text-tertiary)]">Active Students</p>
              <p className="text-sm font-bold text-[var(--color-text-primary)] mt-0.5">{overview.active_students} / {overview.total_students}</p>
            </div>
            <div className="p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
              <p className="text-[11px] text-[var(--color-text-tertiary)]">Academic Year</p>
              <p className="text-xs font-semibold text-[var(--color-text-primary)] mt-0.5">{overview.current_academic_year || 'Not set'}</p>
            </div>
            <div className="p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
              <p className="text-[11px] text-[var(--color-text-tertiary)]">Classes</p>
              <p className="text-sm font-bold text-[var(--color-text-primary)] mt-0.5">{overview.total_classes}</p>
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <h2 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">Quick Actions</h2>
          <div className="space-y-1.5">
            {[
              { label: 'Mark Daily Attendance', desc: "Record today's attendance", route: '/attendance/daily', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4' },
              { label: 'View Records', desc: 'Browse attendance records', route: '/attendance/records', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2' },
              { label: 'Notifications', desc: 'View system notifications', route: '/notifications', icon: 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9' },
              { label: 'Leave Requests', desc: 'Submit or track leave', route: '/leave', icon: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z' },
              { label: 'My Profile', desc: 'View your account details', route: '/profile', icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z' },
            ].map((a) => (
              <button key={a.route} onClick={() => navigate(a.route)} className="w-full flex items-center gap-3 p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-left motion-safe:transition-colors motion-safe:duration-[var(--motion-fast)] hover:border-[var(--color-brand-accent)]/30">
                <svg className="h-4 w-4 text-[var(--color-text-tertiary)] flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={a.icon} /></svg>
                <div className="min-w-0">
                  <p className="text-xs font-medium text-[var(--color-text-primary)]">{a.label}</p>
                  <p className="text-[11px] text-[var(--color-text-tertiary)]">{a.desc}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
