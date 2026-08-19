import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../api/auth/auth-context'
import { teacherApi } from '../../api/academic/teacher-api'
import { teacherAssignmentApi } from '../../api/academic/teacher-assignment-api'
import { riskApi, type TeacherRiskSummary } from '../../api/risk/risk-api'
import type { TeacherResponse, TeacherAssignmentResponse } from '../../api/generated/types'
import { ErrorState, PageHeader, Badge, Skeleton } from '../../components/ui'
import { cn } from '../../lib/utils'

// ── Student Risk section ──────────────────────────────────────────────

const riskSeverityDot: Record<string, string> = {
  critical: 'bg-[var(--color-danger)]',
  high: 'bg-[var(--color-danger)]',
  medium: 'bg-[var(--color-warning)]',
  low: 'bg-[var(--color-info)]',
}

const riskSeverityTint: Record<string, string> = {
  critical: 'text-[var(--color-danger)]',
  high: 'text-[var(--color-danger)]',
  medium: 'text-[var(--color-warning)]',
  low: 'text-[var(--color-info)]',
}

const riskCategoryLabel: Record<string, string> = {
  attendance: 'Attendance',
  academic: 'Academic',
  documents: 'Documents',
  operational: 'Operational',
}

function StudentRiskSection({ summary, loading, error }: { summary: TeacherRiskSummary | null; loading: boolean; error: string | null }) {
  const navigate = useNavigate()

  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-semibold text-[var(--color-text-primary)]">Student Risk</h2>
          <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">Open attention flags for your students</p>
        </div>
        {summary && summary.total > 0 && (
          <Badge variant="danger" size="sm" dot>{summary.total} open</Badge>
        )}
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-14 rounded-lg" />)}
        </div>
      ) : error ? (
        <div className="flex items-center gap-3 rounded-lg border border-[var(--color-warning)]/20 bg-[var(--color-warning)]/5 p-3">
          <svg className="h-4 w-4 text-[var(--color-warning)] flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
          <p className="text-xs text-[var(--color-text-secondary)]">Risk data temporarily unavailable.</p>
        </div>
      ) : !summary || summary.findings.length === 0 ? (
        <div className="flex items-center gap-3 py-6 px-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]">
          <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-[var(--color-success)]/10 flex-shrink-0">
            <svg className="h-4 w-4 text-[var(--color-success)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <div>
            <p className="text-xs font-medium text-[var(--color-text-secondary)]">No open risk findings</p>
            <p className="text-[11px] text-[var(--color-text-tertiary)]">All students in your classes are on track.</p>
          </div>
        </div>
      ) : (
        <div className="space-y-1.5">
          {summary.findings.slice(0, 6).map((f) => (
            <div key={f.id} className="flex items-start gap-3 p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
              <span className={cn('mt-1.5 inline-block h-2 w-2 rounded-full flex-shrink-0', riskSeverityDot[f.severity])} aria-hidden="true" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-xs font-semibold text-[var(--color-text-primary)]">{f.student_name || `Student #${f.student_id}`}</p>
                  <span className="text-[10px] text-[var(--color-text-muted)]">{riskCategoryLabel[f.category] || f.category}</span>
                </div>
                <p className="text-[11px] text-[var(--color-text-tertiary)] mt-0.5 truncate">{f.reason}</p>
              </div>
              {f.student_id && (
                <button
                  onClick={() => navigate(`/students/${f.student_id}/360`)}
                  className="flex-shrink-0 text-[11px] font-medium text-[var(--color-brand-accent)] hover:underline"
                >
                  View
                </button>
              )}
            </div>
          ))}
          {summary.findings.length > 6 && (
            <p className="text-center text-[11px] text-[var(--color-text-tertiary)] pt-1">
              +{summary.findings.length - 6} more findings
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export function TeacherDashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [teacher, setTeacher] = useState<TeacherResponse | null>(null)
  const [assignments, setAssignments] = useState<TeacherAssignmentResponse[]>([])
  const [riskSummary, setRiskSummary] = useState<TeacherRiskSummary | null>(null)
  const [riskLoading, setRiskLoading] = useState(false)
  const [riskError, setRiskError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  useEffect(() => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)

    teacherApi.list({ size: 200 })
      .then(async (result) => {
        if (fetchId !== fetchIdRef.current) return
        const match = result.items.find(
          (t) => t.email === user?.email || `${t.first_name} ${t.last_name}` === user?.display_name
        )
        if (match) {
          setTeacher(match)
          const assignResult = await teacherAssignmentApi.list({ teacher_id: match.id, size: 100 })
          if (fetchId === fetchIdRef.current) setAssignments(assignResult.items)

          setRiskLoading(true)
          riskApi.getTeacherFindings(match.id)
            .then((summary) => { if (fetchId === fetchIdRef.current) setRiskSummary(summary) })
            .catch((err: any) => { if (fetchId === fetchIdRef.current) setRiskError(err?.detail || 'Risk data unavailable') })
            .finally(() => { if (fetchId === fetchIdRef.current) setRiskLoading(false) })
        }
      })
      .catch((err: any) => { if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load teacher data') })
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
          <Skeleton className="h-64 rounded-xl lg:col-span-2" />
          <Skeleton className="h-64 rounded-xl" />
        </div>
      </div>
    )
  }

  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />

  const activeAssignments = assignments.filter((a) => a.status === 'active')
  const subjects = new Set(assignments.filter((a) => a.subject_id).map((a) => a.subject_id))

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <PageHeader
          eyebrow="Workspace"
          title={`Good ${new Date().getHours() < 12 ? 'morning' : new Date().getHours() < 17 ? 'afternoon' : 'evening'}, ${teacher ? `${teacher.first_name} ${teacher.last_name}` : (user?.display_name || 'Teacher')}`}
          subtitle={assignments.length > 0 ? `${assignments.length} class assignment${assignments.length !== 1 ? 's' : ''}` : 'Welcome to your workspace'}
          compact
        />
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={() => navigate('/teacher/classes')}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--color-brand-accent)] px-3 py-1.5 text-xs font-medium text-white hover:bg-[var(--color-brand-accent-hover)] motion-safe:transition-colors"
          >
            My Classes
          </button>
          <button
            onClick={() => navigate('/attendance/daily')}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/30 hover:text-[var(--color-brand-accent)] motion-safe:transition-colors"
          >
            Mark Attendance
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Assignments', value: assignments.length },
          { label: 'Active Classes', value: activeAssignments.length, accent: 'text-[var(--color-success)]' },
          { label: 'Subjects', value: subjects.size },
          { label: 'Status', value: teacher?.status === 'active' ? 'Active' : 'Inactive', accent: teacher?.status === 'active' ? 'text-[var(--color-success)]' : 'text-[var(--color-warning)]' },
        ].map((m) => (
          <div key={m.label} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3.5">
            <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-text-tertiary)]">{m.label}</p>
            <p className={cn('mt-1.5 text-xl font-bold tabular-nums leading-none', m.accent || 'text-[var(--color-text-primary)]')}>
              {typeof m.value === 'number' ? m.value.toLocaleString() : m.value}
            </p>
          </div>
        ))}
      </div>

      {/* Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Assignments */}
        <div className="lg:col-span-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <h2 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">My Assigned Classes</h2>
          {assignments.length === 0 ? (
            <div className="py-8 text-center">
              <p className="text-xs text-[var(--color-text-tertiary)]">No assignments yet. Your class assignments will appear here once configured.</p>
            </div>
          ) : (
            <div className="space-y-1.5">
              {assignments.map((assignment) => (
                <div
                  key={assignment.id}
                  className="flex items-center justify-between p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-[var(--color-brand-accent)]/10 flex-shrink-0">
                      <svg className="h-4 w-4 text-[var(--color-brand-accent)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16" />
                      </svg>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-[var(--color-text-primary)]">Class #{assignment.class_id}</p>
                      <p className="text-[11px] text-[var(--color-text-tertiary)]">
                        {assignment.subject_id ? `Subject #${assignment.subject_id}` : 'No subject'}
                        {assignment.status !== 'active' && (
                          <span className="ml-1.5 text-[var(--color-warning)]">({assignment.status})</span>
                        )}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => navigate('/attendance/daily')}
                    className="text-[11px] font-medium text-[var(--color-brand-accent)] hover:underline"
                  >
                    Mark attendance →
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Quick Actions */}
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <h2 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">Quick Actions</h2>
          <div className="space-y-1.5">
            {[
              { label: 'Mark Daily Attendance', desc: "Record today's attendance", route: '/attendance/daily', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2' },
              { label: 'View Attendance Records', desc: 'Review past attendance', route: '/attendance/records', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2' },
              { label: 'View My Students', desc: 'See student list for your classes', route: '/teacher/students', icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197' },
              { label: 'My Profile', desc: 'View and edit your profile', route: '/profile', icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z' },
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

      {/* Student Risk */}
      {teacher && <StudentRiskSection summary={riskSummary} loading={riskLoading} error={riskError} />}
    </div>
  )
}
