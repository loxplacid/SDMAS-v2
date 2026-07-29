import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../api/auth/auth-context'
import { studentApi } from '../../api/student/student-api'
import { analyticsApi } from '../../api/analytics/analytics-api'
import type { StudentResponse } from '../../api/generated/types'
import type { AnalyticsOverview } from '../../api/analytics/types'
import { Loading, ErrorState, AnimatedCount } from '../../components/ui'

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
      // Try to find the student record matching this user
      studentApi.list({ size: 200 }).then((result) => {
        if (fetchId !== fetchIdRef.current) return null
        // Try to match by email
        const match = result.items.find(
          (s) => s.email === user?.email || `${s.first_name} ${s.last_name}` === user?.display_name
        )
        return match || null
      }),
      // Load school overview
      analyticsApi.getOverview().catch(() => null),
    ])
      .then(([studentMatch, ov]) => {
        if (fetchId === fetchIdRef.current) {
          setStudent(studentMatch)
          setOverview(ov)
        }
      })
      .catch((err: any) => {
        if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load data')
      })
      .finally(() => {
        if (fetchId === fetchIdRef.current) setLoading(false)
      })
  }, [user])

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
      </div>
    )
  }

  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-violet-700 via-violet-600 to-purple-600 p-8 lg:p-10">
        <div className="absolute inset-0 opacity-[0.04]"
          style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.3) 1px, transparent 1px)', backgroundSize: '40px 40px' }}
        />
        <div className="relative">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            <div className="space-y-2">
              <p className="text-sm font-medium text-violet-200 tracking-wide">
                {greeting}, {student ? `${student.first_name} ${student.last_name}` : (user?.display_name || user?.username || 'Student')}
              </p>
              <h1 className="text-3xl lg:text-4xl font-extrabold text-white leading-tight tracking-tight">
                Your student dashboard
              </h1>
              <p className="text-white/60 text-base max-w-xl leading-relaxed">
                Track your attendance, view your fee status, and stay on top of your academic journey.
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => navigate(student ? `/attendance/student/${student.id}` : '/student/attendance')}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white text-violet-700 text-sm font-semibold hover:bg-violet-50 transition-colors shadow-lg"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2" />
                </svg>
                My Attendance
              </button>
              <button
                onClick={() => navigate('/student/fees')}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white/15 text-white text-sm font-medium hover:bg-white/25 transition-colors"
              >
                My Fees
              </button>
            </div>
          </div>

          {/* Quick Stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-8">
            {[
              { label: 'School Attendance', value: overview?.overall_attendance_percentage || 0, suffix: '%', accent: 'text-violet-300' },
              { label: 'Total Students', value: overview?.total_students || 0, accent: 'text-purple-300' },
              { label: 'Fee Collection', value: overview?.collection_percentage || 0, suffix: '%', accent: 'text-fuchsia-300' },
              { label: 'Status', value: student?.status === 'active' ? 'Active' : (student?.status || '—'), accent: 'text-violet-200' },
            ].map((m, i) => (
              <div
                key={m.label}
                className="bg-white/5 rounded-xl p-4 border border-white/[0.06] animate-fade-in-up"
                style={{ animationDelay: `${i * 80}ms`, animationFillMode: 'both' }}
              >
                <p className="text-xs text-white/40 font-medium tracking-wide uppercase">{m.label}</p>
                <p className={`text-2xl font-bold text-white mt-1 ${m.accent}`}>
                  {typeof m.value === 'number'
                    ? <><AnimatedCount value={m.value} duration={1000 + i * 200} />{m.suffix || ''}</>
                    : m.value}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Welcome Card */}
        <div className="lg:col-span-2 bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-6">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-base font-semibold text-[var(--color-text-primary)]">Welcome</h2>
              <p className="text-sm text-[var(--color-text-tertiary)] mt-0.5">Your academic journey at a glance</p>
            </div>
          </div>

          <div className="space-y-4">
            {student ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)]">
                  <p className="text-xs font-medium text-[var(--color-text-tertiary)] uppercase tracking-wide">Student Number</p>
                  <p className="text-lg font-bold text-[var(--color-text-primary)] mt-1">{student.student_number}</p>
                </div>
                <div className="p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)]">
                  <p className="text-xs font-medium text-[var(--color-text-tertiary)] uppercase tracking-wide">Email</p>
                  <p className="text-sm font-medium text-[var(--color-text-primary)] mt-1">{student.email || '—'}</p>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <div className="flex items-center justify-center h-12 w-12 rounded-xl bg-[var(--color-surface-hover)] mb-3">
                  <svg className="h-6 w-6 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197" />
                  </svg>
                </div>
                <p className="text-sm font-medium text-[var(--color-text-secondary)]">Student profile not linked</p>
                <p className="text-xs text-[var(--color-text-tertiary)] mt-1">Contact your administrator to link your account.</p>
              </div>
            )}
          </div>
        </div>

        {/* Quick Links */}
        <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-6">
          <h2 className="text-base font-semibold text-[var(--color-text-primary)] mb-5">Quick Links</h2>
          <div className="space-y-3">
            <button
              onClick={() => navigate(student ? `/attendance/student/${student.id}` : '/student/attendance')}
              className="w-full flex items-center gap-3 p-4 rounded-xl bg-[var(--color-brand-accent)]/5 border border-[var(--color-brand-accent)]/15 text-left hover:shadow-sm hover:-translate-y-0.5 transition-all duration-[var(--motion-fast)] motion-reduce:transition-none motion-reduce:hover:translate-y-0"
            >
              <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-brand-accent)]/10">
                <svg className="h-4.5 w-4.5 text-[var(--color-brand-accent)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-[var(--color-text-primary)]">View My Attendance</p>
                <p className="text-xs text-[var(--color-text-tertiary)]">Track your attendance record</p>
              </div>
            </button>

            <button
              onClick={() => navigate('/student/fees')}
              className="w-full flex items-center gap-3 p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)] text-left hover:shadow-sm hover:-translate-y-0.5 transition-all duration-[var(--motion-fast)] motion-reduce:transition-none motion-reduce:hover:translate-y-0"
            >
              <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-bg)]">
                <svg className="h-4.5 w-4.5 text-[var(--color-text-secondary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-[var(--color-text-primary)]">View My Fees</p>
                <p className="text-xs text-[var(--color-text-tertiary)]">Check fee status and dues</p>
              </div>
            </button>

            <button
              onClick={() => navigate('/student/schedule')}
              className="w-full flex items-center gap-3 p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)] text-left hover:shadow-sm hover:-translate-y-0.5 transition-all duration-[var(--motion-fast)] motion-reduce:transition-none motion-reduce:hover:translate-y-0"
            >
              <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-bg)]">
                <svg className="h-4.5 w-4.5 text-[var(--color-text-secondary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-[var(--color-text-primary)]">View Schedule</p>
                <p className="text-xs text-[var(--color-text-tertiary)]">See your class schedule</p>
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
