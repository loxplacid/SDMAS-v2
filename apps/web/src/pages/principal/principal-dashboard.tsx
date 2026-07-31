import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../api/auth/auth-context'
import { analyticsApi } from '../../api/analytics/analytics-api'
import { attendanceAnalyticsApi } from '../../api/analytics/attendance-analytics-api'
import { financeAnalyticsApi } from '../../api/analytics/finance-analytics-api'
import type { AnalyticsOverview, AttendanceOverview, FinanceOverview } from '../../api/analytics/types'
import { Loading, ErrorState, AnimatedCount } from '../../components/ui'
import { formatCurrency } from '../../lib/utils'

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
        if (fetchId === fetchIdRef.current) {
          setOverview(ov)
          setAttendanceOverview(att)
          setFinanceOverview(fin)
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
          <div className="lg:col-span-2 h-64 rounded-2xl bg-[var(--color-border)] animate-skeleton" />
          <div className="h-64 rounded-2xl bg-[var(--color-border)] animate-skeleton" />
        </div>
      </div>
    )
  }

  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />
  if (!overview) return <ErrorState message="Unable to load dashboard data." />

  const isAttendanceGood = (attendanceOverview?.attendance_percentage ?? overview.overall_attendance_percentage) >= 90
  const attendancePct = attendanceOverview?.attendance_percentage ?? overview.overall_attendance_percentage ?? 0
  const collectionPct = financeOverview?.collection_percentage ?? overview.collection_percentage ?? 0
  const isCollectionGood = collectionPct >= 80

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-indigo-800 via-indigo-700 to-indigo-600 p-8 lg:p-10">
        <div className="absolute inset-0 opacity-[0.04]"
          style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.3) 1px, transparent 1px)', backgroundSize: '40px 40px' }}
        />
        <div className="relative">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            <div className="space-y-2">
              <p className="text-sm font-medium text-indigo-200 tracking-wide">
                {greeting}, {user?.display_name || user?.username || 'Principal'}
              </p>
              <h1 className="text-3xl lg:text-4xl font-extrabold text-white leading-tight tracking-tight">
                School leadership overview
              </h1>
              <p className="text-white/60 text-base max-w-xl leading-relaxed">
                {`${overview.total_students} student${overview.total_students !== 1 ? 's' : ''}, ${overview.total_teachers} teacher${overview.total_teachers !== 1 ? 's' : ''}, ${overview.total_sections} section${overview.total_sections !== 1 ? 's' : ''}. `}
                {overview.current_academic_year && `Current year: ${overview.current_academic_year}.`}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => navigate('/reports')}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white text-indigo-700 text-sm font-semibold hover:bg-indigo-50 transition-colors shadow-lg"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                View Reports
              </button>
              <button
                onClick={() => navigate('/analytics')}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white/15 text-white text-sm font-medium hover:bg-white/25 transition-colors"
              >
                Analytics
              </button>
            </div>
          </div>

          {/* KPI Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-8">
            {[
              { label: 'Total Students', value: overview.total_students, accent: 'text-indigo-200' },
              { label: 'Teachers', value: overview.total_teachers, accent: 'text-sky-300' },
              { label: 'Sections', value: overview.total_sections, accent: 'text-violet-300' },
              { label: 'Classes', value: overview.total_classes, accent: 'text-rose-300' },
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

      {/* Pulse Areas */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Attendance Pulse */}
        <div className="lg:col-span-2 bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-6">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-base font-semibold text-[var(--color-text-primary)]">Attendance Pulse</h2>
              <p className="text-sm text-[var(--color-text-tertiary)] mt-0.5">Current period overview</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-[var(--color-text-primary)]">
                <span className={`inline-block h-2 w-2 rounded-full ${isAttendanceGood ? 'bg-[var(--color-success)]' : 'bg-[var(--color-danger)]'} animate-pulse-soft mr-1.5`} />
                <AnimatedCount value={attendancePct} duration={1000} suffix="%" />
              </span>
            </div>
          </div>

          {attendanceOverview && attendanceOverview.total_records > 0 ? (
            <div>
              <div className="grid grid-cols-4 gap-3">
                {[
                  { label: 'Present', count: attendanceOverview.present, color: 'text-[var(--color-success)]', bg: 'bg-[var(--color-success)]/5' },
                  { label: 'Absent', count: attendanceOverview.absent, color: 'text-[var(--color-danger)]', bg: 'bg-[var(--color-danger)]/5' },
                  { label: 'Late', count: attendanceOverview.late, color: 'text-[var(--color-warning)]', bg: 'bg-[var(--color-warning)]/5' },
                  { label: 'Excused', count: attendanceOverview.excused, color: 'text-[var(--color-info)]', bg: 'bg-[var(--color-info)]/5' },
                ].map((s) => (
                  <div key={s.label} className={`text-center p-4 rounded-xl ${s.bg}`}>
                    <p className={`text-2xl font-bold ${s.color}`}>
                      <AnimatedCount value={s.count} duration={800} />
                    </p>
                    <p className="text-xs text-[var(--color-text-tertiary)] mt-1">{s.label}</p>
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

        {/* Attention & Financials */}
        <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-6">
          <h2 className="text-base font-semibold text-[var(--color-text-primary)] mb-5">Key Metrics</h2>
          <div className="space-y-3">
            {/* Attendance Alert */}
            {overview.low_attendance_count > 0 && (
              <div className="rounded-xl bg-[var(--color-danger)]/5 border border-[var(--color-danger)]/15 p-4">
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
            )}

            {/* Collection Rate */}
            <div className="rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)] p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-[var(--color-text-tertiary)]">Fee Collection</span>
                <span className={`text-xs font-semibold ${isCollectionGood ? 'text-[var(--color-success)]' : 'text-[var(--color-warning)]'}`}>
                  <AnimatedCount value={collectionPct} duration={1000} suffix="%" />
                </span>
              </div>
              <div className="h-2 rounded-full bg-[var(--color-border)] overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-1000 ${isCollectionGood ? 'bg-[var(--color-success)]' : 'bg-[var(--color-warning)]'}`}
                  style={{ width: `${Math.min(collectionPct, 100)}%` }}
                />
              </div>
              <div className="flex justify-between mt-2">
                <p className="text-xs text-[var(--color-text-tertiary)]">{formatCurrency(financeOverview?.total_collected ?? overview.total_collected)} collected</p>
                <p className="text-xs text-[var(--color-text-tertiary)]">{formatCurrency(financeOverview?.total_outstanding ?? overview.total_outstanding)} outstanding</p>
              </div>
            </div>

            {/* Unpaid / Partially Paid */}
            {(overview.unpaid_count > 0 || (financeOverview?.students_with_outstanding ?? 0) > 0) && (
              <div className="rounded-xl bg-[var(--color-warning)]/5 border border-[var(--color-warning)]/15 p-4">
                <div className="flex items-center gap-3">
                  <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-warning)]/10">
                    <svg className="h-4.5 w-4.5 text-[var(--color-warning)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-[var(--color-warning-dark)]">Outstanding Fees</p>
                    <p className="text-xs text-[var(--color-warning)]/70">
                      {financeOverview?.students_with_outstanding ?? overview.unpaid_count} student{(financeOverview?.students_with_outstanding ?? overview.unpaid_count) !== 1 ? 's' : ''} with outstanding
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Quick Navigation */}
      <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-semibold text-[var(--color-text-primary)]">Quick Access</h2>
            <p className="text-sm text-[var(--color-text-tertiary)] mt-0.5">Navigate to key areas</p>
          </div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'Students', path: '/students', icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197' },
            { label: 'Teachers', path: '/teachers', icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z' },
            { label: 'Academics', path: '/academic', icon: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3' },
            { label: 'Attendance', path: '/attendance', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2' },
            { label: 'Fees', path: '/fees', icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1' },
            { label: 'Reports', path: '/reports', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10' },
            { label: 'Analytics', path: '/analytics', icon: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6' },
            { label: 'Notifications', path: '/notifications', icon: 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341' },
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
