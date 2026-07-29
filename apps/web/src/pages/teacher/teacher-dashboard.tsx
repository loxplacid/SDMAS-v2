import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../api/auth/auth-context'
import { teacherApi } from '../../api/academic/teacher-api'
import { teacherAssignmentApi } from '../../api/academic/teacher-assignment-api'
import type { TeacherResponse, TeacherAssignmentResponse } from '../../api/generated/types'
import { Loading, ErrorState, AnimatedCount } from '../../components/ui'

export function TeacherDashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [teacher, setTeacher] = useState<TeacherResponse | null>(null)
  const [assignments, setAssignments] = useState<TeacherAssignmentResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  useEffect(() => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)

    // Find the teacher record matching this user
    // We'll search for teachers and look for a match
    teacherApi.list({ size: 200 })
      .then(async (result) => {
        if (fetchId !== fetchIdRef.current) return
        // Try to match the teacher by email or name
        const match = result.items.find(
          (t) => t.email === user?.email || `${t.first_name} ${t.last_name}` === user?.display_name
        )
        if (match) {
          setTeacher(match)
          // Load their assignments
          const assignResult = await teacherAssignmentApi.list({ teacher_id: match.id, size: 100 })
          if (fetchId === fetchIdRef.current) {
            setAssignments(assignResult.items)
          }
        }
      })
      .catch((err: any) => {
        if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load teacher data')
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
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-emerald-700 via-emerald-600 to-teal-600 p-8 lg:p-10">
        <div className="absolute inset-0 opacity-[0.04]"
          style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.3) 1px, transparent 1px)', backgroundSize: '40px 40px' }}
        />
        <div className="relative">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            <div className="space-y-2">
              <p className="text-sm font-medium text-emerald-200 tracking-wide">
                {greeting}, {teacher ? `${teacher.first_name} ${teacher.last_name}` : (user?.display_name || user?.username || 'Teacher')}
              </p>
              <h1 className="text-3xl lg:text-4xl font-extrabold text-white leading-tight tracking-tight">
                Your teaching workspace
              </h1>
              <p className="text-white/60 text-base max-w-xl leading-relaxed">
                {assignments.length > 0
                  ? `You have ${assignments.length} class assignment${assignments.length !== 1 ? 's' : ''}. Mark attendance, view students, and manage your classes.`
                  : 'Welcome to your workspace. Your class assignments will appear here once they\'re set up.'}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => navigate('/teacher/classes')}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white text-emerald-700 text-sm font-semibold hover:bg-emerald-50 transition-colors shadow-lg"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16" />
                </svg>
                My Classes
              </button>
              <button
                onClick={() => navigate('/attendance/daily')}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white/15 text-white text-sm font-medium hover:bg-white/25 transition-colors"
              >
                Mark Attendance
              </button>
            </div>
          </div>

          {/* Quick Stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-8">
            {[
              { label: 'Assignments', value: assignments.length, accent: 'text-emerald-300' },
              { label: 'Active Classes', value: assignments.filter((a) => a.status === 'active').length, accent: 'text-teal-300' },
              { label: 'Subjects', value: new Set(assignments.filter((a) => a.subject_id).map((a) => a.subject_id)).size, accent: 'text-cyan-300' },
              { label: 'Status', value: teacher?.status === 'active' ? 'Active' : 'Inactive', accent: teacher?.status === 'active' ? 'text-emerald-300' : 'text-amber-300' },
            ].map((m, i) => (
              <div
                key={m.label}
                className="bg-white/5 rounded-xl p-4 border border-white/[0.06] animate-fade-in-up"
                style={{ animationDelay: `${i * 80}ms`, animationFillMode: 'both' }}
              >
                <p className="text-xs text-white/40 font-medium tracking-wide uppercase">{m.label}</p>
                <p className={`text-2xl font-bold text-white mt-1 ${m.accent}`}>
                  {typeof m.value === 'number' ? <AnimatedCount value={m.value} duration={1000 + i * 200} /> : m.value}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Assignments List */}
        <div className="lg:col-span-2 bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-6">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-base font-semibold text-[var(--color-text-primary)]">My Assigned Classes</h2>
              <p className="text-sm text-[var(--color-text-tertiary)] mt-0.5">Your current teaching assignments</p>
            </div>
          </div>

          {assignments.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-center">
              <div className="flex items-center justify-center h-12 w-12 rounded-xl bg-[var(--color-surface-hover)] mb-3">
                <svg className="h-6 w-6 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16" />
                </svg>
              </div>
              <p className="text-sm font-medium text-[var(--color-text-secondary)]">No assignments yet</p>
              <p className="text-xs text-[var(--color-text-tertiary)] mt-1">Your class assignments will appear here once configured.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {assignments.map((assignment) => (
                <div
                  key={assignment.id}
                  className="flex items-center justify-between p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)] hover:shadow-sm hover:-translate-y-0.5 transition-all duration-[var(--motion-fast)] motion-reduce:transition-none motion-reduce:hover:translate-y-0"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-brand-accent)]/10">
                      <svg className="h-4.5 w-4.5 text-[var(--color-brand-accent)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16" />
                      </svg>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-[var(--color-text-primary)]">Class #{assignment.class_id}</p>
                      <p className="text-xs text-[var(--color-text-tertiary)]">
                        {assignment.subject_id ? `Subject #${assignment.subject_id}` : 'No subject assigned'}
                        {assignment.status !== 'active' && (
                          <span className="ml-2 text-[var(--color-warning)]">({assignment.status})</span>
                        )}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => navigate(`/attendance/daily`)}
                    className="text-xs font-medium text-[var(--color-brand-accent)] hover:text-[var(--color-brand-accent-hover)] transition-colors"
                  >
                    Mark attendance &rarr;
                  </button>
                </div>
              ))}
            </div>
          )}
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
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2" />
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
                <p className="text-sm font-semibold text-[var(--color-text-primary)]">View Attendance Records</p>
                <p className="text-xs text-[var(--color-text-tertiary)]">Review past attendance</p>
              </div>
            </button>

            <button
              onClick={() => navigate('/teacher/classes')}
              className="w-full flex items-center gap-3 p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)] text-left hover:shadow-sm hover:-translate-y-0.5 transition-all duration-[var(--motion-fast)] motion-reduce:transition-none motion-reduce:hover:translate-y-0"
            >
              <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-bg)]">
                <svg className="h-4.5 w-4.5 text-[var(--color-text-secondary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-[var(--color-text-primary)]">View My Students</p>
                <p className="text-xs text-[var(--color-text-tertiary)]">See student list for your classes</p>
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
                <p className="text-xs text-[var(--color-text-tertiary)]">View and edit your profile</p>
              </div>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
