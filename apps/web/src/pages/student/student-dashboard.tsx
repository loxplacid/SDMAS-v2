import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../api/auth/auth-context'
import { studentApi } from '../../api/student/student-api'
import { analyticsApi } from '../../api/analytics/analytics-api'
import type { StudentResponse } from '../../api/generated/types'
import type { AnalyticsOverview } from '../../api/analytics/types'
import { ErrorState, PageHeader, Skeleton } from '../../components/ui'
import { cn } from '../../lib/utils'

export function StudentDashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [student, setStudent] = useState<StudentResponse | null>(null)
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  useEffect(() => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)

    Promise.all([
      studentApi.list({ size: 200 }).then((result) => {
        if (fetchId !== fetchIdRef.current) return null
        return result.items.find(
          (s) => s.email === user?.email || `${s.first_name} ${s.last_name}` === user?.display_name
        ) || null
      }),
      analyticsApi.getOverview().catch(() => null),
    ])
      .then(([studentMatch, ov]) => {
        if (fetchId === fetchIdRef.current) { setStudent(studentMatch); setOverview(ov) }
      })
      .catch((err: any) => { if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load data') })
      .finally(() => { if (fetchId === fetchIdRef.current) setLoading(false) })
  }, [user])

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="space-y-2">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-7 w-56" />
          <Skeleton className="h-3 w-80" />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-20 rounded-xl" />)}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Skeleton className="h-48 rounded-xl lg:col-span-2" />
          <Skeleton className="h-48 rounded-xl" />
        </div>
      </div>
    )
  }

  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <PageHeader
          eyebrow="Workspace"
          title={`Good ${new Date().getHours() < 12 ? 'morning' : new Date().getHours() < 17 ? 'afternoon' : 'evening'}, ${student ? `${student.first_name} ${student.last_name}` : (user?.display_name || 'Student')}`}
          subtitle="Track your attendance, fees, and academic journey"
          compact
        />
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={() => navigate(student ? `/attendance/student/${student.id}` : '/student/attendance')}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--color-brand-accent)] px-3 py-1.5 text-xs font-medium text-white hover:bg-[var(--color-brand-accent-hover)] motion-safe:transition-colors"
          >
            My Attendance
          </button>
          <button
            onClick={() => navigate('/student/fees')}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/30 hover:text-[var(--color-brand-accent)] motion-safe:transition-colors"
          >
            My Fees
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Attendance', value: `${overview?.overall_attendance_percentage || 0}%` },
          { label: 'Total Students', value: overview?.total_students || 0 },
          { label: 'Collection', value: `${overview?.collection_percentage || 0}%` },
          { label: 'Status', value: student?.status === 'active' ? 'Active' : (student?.status || '—'), accent: student?.status === 'active' ? 'text-[var(--color-success)]' : 'text-[var(--color-text-tertiary)]' },
        ].map((m) => (
          <div key={m.label} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3.5">
            <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-text-tertiary)]">{m.label}</p>
            <p className={cn('mt-1.5 text-xl font-bold tabular-nums leading-none', m.accent || 'text-[var(--color-text-primary)]')}>
              {typeof m.value === 'number' ? m.value.toLocaleString() : m.value}
            </p>
          </div>
        ))}
      </div>

      {/* Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Student Info */}
        <div className="lg:col-span-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <h2 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">My Information</h2>
          {student ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
                <p className="text-[11px] font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider">Student Number</p>
                <p className="text-sm font-bold text-[var(--color-text-primary)] mt-1">{student.student_number}</p>
              </div>
              <div className="p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
                <p className="text-[11px] font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider">Email</p>
                <p className="text-sm font-medium text-[var(--color-text-primary)] mt-1">{student.email || '—'}</p>
              </div>
            </div>
          ) : (
            <div className="py-8 text-center">
              <p className="text-xs text-[var(--color-text-tertiary)]">Student profile not linked. Contact your administrator.</p>
            </div>
          )}
        </div>

        {/* Quick Links */}
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <h2 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">Quick Links</h2>
          <div className="space-y-1.5">
            {[
              { label: 'My Attendance', desc: 'Track your attendance record', route: student ? `/attendance/student/${student.id}` : '/student/attendance', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2' },
              { label: 'My Fees', desc: 'Check fee status and dues', route: '/student/fees', icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2' },
              { label: 'View Schedule', desc: 'See your class schedule', route: '/student/timetable', icon: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z' },
              { label: 'My Profile', desc: 'View your account details', route: '/profile', icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z' },
            ].map((a) => (
              <button
                key={a.route}
                onClick={() => navigate(a.route)}
                className="w-full flex items-center gap-3 p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-left motion-safe:transition-colors motion-safe:duration-[var(--motion-fast)] hover:border-[var(--color-brand-accent)]/30"
              >
                <svg className="h-4 w-4 text-[var(--color-text-tertiary)] flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={a.icon} />
                </svg>
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
