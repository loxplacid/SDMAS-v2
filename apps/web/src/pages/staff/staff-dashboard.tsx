import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../api/auth/auth-context'
import { analyticsApi } from '../../api/analytics/analytics-api'
import { attendanceAnalyticsApi } from '../../api/analytics/attendance-analytics-api'
import type { AnalyticsOverview, AttendanceOverview } from '../../api/analytics/types'
import { Loading, ErrorState, AnimatedCount } from '../../components/ui'

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

    Promise.all([
      analyticsApi.getOverview(),
      attendanceAnalyticsApi.getOverview().catch(() => null),
    ])
      .then(([ov, att]) => {
        if (fetchId === fetchIdRef.current) {
          setOverview(ov)
          setAttendanceOverview(att)
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
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 rounded-2xl bg-[var(--color-border)] animate-skeleton" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 h-48 rounded-2xl bg-[var(--color-border)] animate-skeleton" />
          <div className="h-48 rounded-2xl bg-[var(--color-border)] animate-skeleton" />
        </div>
      </div>
    )
  }

  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />
  if (!overview) return <ErrorState message="Unable to load dashboard data." />

  const attendancePct = attendanceOverview?.attendance_percentage ?? overview.overall_attendance_percentage ?? 0
  const isAttendanceGood = attendancePct >= 90

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-teal-700 via-teal-600 to-emerald-600 p-8 lg:p-10">
        <div className="absolute inset-0 opacity-[0.04]"
          style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.3) 1px, transparent 1px)', backgroundSize: '40px 40px' }}
        />
        <div className="relative">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            <div className="space-y-2">
              <p className="text-sm font-medium text-teal-200 tracking-wide">
                {greeting}, {user?.display_name || user?.username || 'Staff'}
              </p>
              <h1 className="text-3xl lg:text-4xl font-extrabold text-white leading-tight tracking-tight">
                Staff operations
              </h1>
              <p className="text-white/60 text-base max-w-xl leading-relaxed">
                {`${overview.total_students} student${overview.total_students !== 1 ? 's' : ''}, ${overview.total_teachers} teacher${overview.total_teachers !== 1 ? 's' : ''}, and ${overview.total_sections} section${overview.total_sections !== 1 ? 's' : ''}.`}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => navigate('/attendance/daily')}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white text-teal-700 text-sm font-semibold hover:bg-teal-50 transition-colors shadow-lg"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
                Attendance
              </button>
              <button
                onClick={() => navigate('/notifications')}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white/15 text-white text-sm font-medium hover:bg-white/25 transition-colors"
              >
                Notifications
              </button>
            </div>
          </div>

          {/* KPI Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-8">
            {[
              { label: 'Students', value: overview.total_students, accent: 'text-teal-200' },
              { label: 'Teachers', value: overview.total_teachers, accent: 'text-emerald-300' },
              { label: 'Sections', value: overview.total_sections, accent: 'text-cyan-300' },
              { label: 'Subjects', value: overview.total_subjects, accent: 'text-amber-300' },
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

      {/* Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Attendance Overview */}
        <div className="lg:col-span-2 bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-6">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-base font-semibold text-[var(--color-text-primary)]">Today's Overview</h2>
              <p className="text-sm text-[var(--color-text-tertiary)] mt-0.5">School-wide metrics at a glance</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1.5 text-sm font-semibold text-[var(--color-text-primary)]">
                <span className={`inline-block h-2 w-2 rounded-full ${isAttendanceGood ? 'bg-[var(--color-success)]' : 'bg-[var(--color-danger)]'} animate-pulse-soft`} />
                {attendancePct}%
              </span>
            </div>
          </div>

          {attendanceOverview && attendanceOverview.total_records > 0 ? (
            <div className="grid grid-cols-4 gap-3">
              {[
                { label: 'Present', count: attendanceOverview.present, color: 'text-[var(--color-success)]', bg: 'bg-[var(--color-success)]/5' },
                { label: 'Absent', count: attendanceOverview.absent, color: 'text-[var(--color-danger)]', bg: 'bg-[var(--color-danger)]/5' },
                { label: 'Late', count: attendanceOverview.late, color: 'text-[var(--color-warning)]', bg: 'bg-[var(--color-warning)]/5' },
                { label: 'Records', count: attendanceOverview.total_records, color: 'text-[var(--color-info)]', bg: 'bg-[var(--color-info)]/5' },
              ].map((s) => (
                <div key={s.label} className={`text-center p-4 rounded-xl ${s.bg}`}>
                  <p className={`text-2xl font-bold ${s.color}`}>
                    <AnimatedCount value={s.count} duration={800} />
                  </p>
                  <p className="text-xs text-[var(--color-text-tertiary)] mt-1">{s.label}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8">
              <div className="flex items-center justify-center h-12 w-12 rounded-xl bg-[var(--color-surface-hover)] mb-3">
                <svg className="h-6 w-6 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
              </div>
              <p className="text-sm font-medium text-[var(--color-text-secondary)]">No attendance records yet</p>
              <p className="text-xs text-[var(--color-text-tertiary)] mt-1">Attendance data will appear here as it's recorded.</p>
            </div>
          )}

          {/* School Stats */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-6">
            <div className="p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)]">
              <p className="text-xs font-medium text-[var(--color-text-tertiary)] uppercase tracking-wide">Active Students</p>
              <p className="text-xl font-bold text-[var(--color-text-primary)] mt-1">{overview.active_students} / {overview.total_students}</p>
            </div>
            <div className="p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)]">
              <p className="text-xs font-medium text-[var(--color-text-tertiary)] uppercase tracking-wide">Academic Year</p>
              <p className="text-sm font-semibold text-[var(--color-text-primary)] mt-1">{overview.current_academic_year || 'Not set'}</p>
            </div>
            <div className="p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)]">
              <p className="text-xs font-medium text-[var(--color-text-tertiary)] uppercase tracking-wide">Classes</p>
              <p className="text-xl font-bold text-[var(--color-text-primary)] mt-1">{overview.total_classes}</p>
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-6">
          <h2 className="text-base font-semibold text-[var(--color-text-primary)] mb-5">Quick Actions</h2>
          <div className="space-y-3">
            <button
              onClick={() => navigate('/attendance/daily')}
              className="w-full flex items-center gap-3 p-4 rounded-xl bg-[var(--color-brand-accent)]/5 border border-[var(--color-brand-accent)]/15 text-left hover:shadow-sm hover:-translate-y-0.5 transition-all duration-[var(--motion-fast)] motion-reduce:transition-none motion-reduce:hover:translate-y-0"
            >
              <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-brand-accent)]/10">
                <svg className="h-4.5 w-4.5 text-[var(--color-brand-accent)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-[var(--color-text-primary)]">Mark Daily Attendance</p>
                <p className="text-xs text-[var(--color-text-tertiary)]">Record today's attendance</p>
              </div>
            </button>

            <button
              onClick={() => navigate('/attendance/records')}
              className="w-full flex items-center gap-3 p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)] text-left hover:shadow-sm hover:-translate-y-0.5 transition-all duration-[var(--motion-fast)] motion-reduce:transition-none motion-reduce:hover:translate-y-0"
            >
              <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-bg)]">
                <svg className="h-4.5 w-4.5 text-[var(--color-text-secondary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-[var(--color-text-primary)]">View Records</p>
                <p className="text-xs text-[var(--color-text-tertiary)]">Browse attendance records</p>
              </div>
            </button>

            <button
              onClick={() => navigate('/notifications')}
              className="w-full flex items-center gap-3 p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)] text-left hover:shadow-sm hover:-translate-y-0.5 transition-all duration-[var(--motion-fast)] motion-reduce:transition-none motion-reduce:hover:translate-y-0"
            >
              <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-bg)]">
                <svg className="h-4.5 w-4.5 text-[var(--color-text-secondary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-[var(--color-text-primary)]">Notifications</p>
                <p className="text-xs text-[var(--color-text-tertiary)]">View system notifications</p>
              </div>
            </button>

            <button
              onClick={() => navigate('/leave')}
              className="w-full flex items-center gap-3 p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)] text-left hover:shadow-sm hover:-translate-y-0.5 transition-all duration-[var(--motion-fast)] motion-reduce:transition-none motion-reduce:hover:translate-y-0"
            >
              <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-bg)]">
                <svg className="h-4.5 w-4.5 text-[var(--color-text-secondary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-[var(--color-text-primary)]">Leave Requests</p>
                <p className="text-xs text-[var(--color-text-tertiary)]">Submit or track leave requests</p>
              </div>
            </button>

            <button
              onClick={() => navigate('/profile')}
              className="w-full flex items-center gap-3 p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)] text-left hover:shadow-sm hover:-translate-y-0.5 transition-all duration-[var(--motion-fast)] motion-reduce:transition-none motion-reduce:hover:translate-y-0"
            >
              <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-bg)]">
                <svg className="h-4.5 w-4.5 text-[var(--color-text-secondary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-[var(--color-text-primary)]">My Profile</p>
                <p className="text-xs text-[var(--color-text-tertiary)]">View your account details</p>
              </div>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
