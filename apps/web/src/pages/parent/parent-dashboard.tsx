import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../api/auth/auth-context'
import { studentApi } from '../../api/student/student-api'
import { attendanceApi } from '../../api/attendance/attendance-api'
import { summaryApi } from '../../api/fees/summary-api'
import { academicYearApi } from '../../api/academic/academic-year-api'
import type { StudentResponse, StudentAttendanceSummary, StudentFinancialSummary } from '../../api/generated/types'
import { useParentChildren } from '../../hooks/use-parent-children'
import { LinkChildDialog } from '../../components/ui/link-child-dialog'
import { Loading, ErrorState, AnimatedCount } from '../../components/ui'
import { formatCurrency } from '../../lib/utils'

interface ChildWithData {
  student: StudentResponse
  attendance: StudentAttendanceSummary | null
  financial: StudentFinancialSummary | null
}

export function ParentDashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const { linkedIds, linkStudent, linkMultiple, count } = useParentChildren()
  const [childrenData, setChildrenData] = useState<ChildWithData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const fetchIdRef = useRef(0)

  const fetchChildrenData = useCallback(async () => {
    if (linkedIds.length === 0) {
      setChildrenData([])
      setLoading(false)
      return
    }

    try {
      // Find the current active academic year
      let activeYearId: number | null = null
      try {
        const yearResult = await academicYearApi.list({ status: 'active', size: 1 })
        if (yearResult.items.length > 0) {
          activeYearId = yearResult.items[0].id
        }
      } catch {
        // No active academic year found — fee data will be unavailable
      }

      const result = await studentApi.list({ size: 200 })
      const linkedStudents = result.items.filter((s) => linkedIds.includes(s.id))

      const childDataPromises = linkedStudents.map(async (student) => {
        try {
          const [attendance, financial] = await Promise.all([
            attendanceApi.getStudentSummary(
              student.id,
              new Date(new Date().getFullYear(), 0, 1).toISOString().split('T')[0],
              new Date().toISOString().split('T')[0],
            ).catch(() => null),
            activeYearId
              ? summaryApi.getStudentSummary(student.id, activeYearId).catch(() => null)
              : Promise.resolve(null),
          ])
          return { student, attendance, financial }
        } catch {
          return { student, attendance: null, financial: null }
        }
      })

      const results = await Promise.all(childDataPromises)
      setChildrenData(results)
    } catch (err: any) {
      setError(err?.detail || 'Failed to load children data')
    } finally {
      setLoading(false)
    }
  }, [linkedIds])

  useEffect(() => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)
    fetchChildrenData().then(() => {
      if (fetchId !== fetchIdRef.current) return
    })
  }, [fetchChildrenData])

  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'

  // Aggregate stats across linked children
  const totalAttendance = childrenData.reduce((sum, c) => sum + (c.attendance?.percentage || 0), 0)
  const avgAttendance = childrenData.length > 0 ? Math.round(totalAttendance / childrenData.length) : 0
  const totalOutstanding = childrenData.reduce((sum, c) => sum + (c.financial?.total_outstanding || 0), 0)
  const totalPaid = childrenData.reduce((sum, c) => sum + (c.financial?.total_paid || 0), 0)

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
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-amber-700 via-amber-600 to-orange-600 p-8 lg:p-10">
        <div className="absolute inset-0 opacity-[0.04]"
          style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.3) 1px, transparent 1px)', backgroundSize: '40px 40px' }}
        />
        <div className="relative">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            <div className="space-y-2">
              <p className="text-sm font-medium text-amber-200 tracking-wide">
                {greeting}, {user?.display_name || user?.username || 'Parent'}
              </p>
              <h1 className="text-3xl lg:text-4xl font-extrabold text-white leading-tight tracking-tight">
                Parent portal
              </h1>
              <p className="text-white/60 text-base max-w-xl leading-relaxed">
                {count > 0
                  ? `Keep track of your ${count} linked child${count !== 1 ? 'ren' : ''}'s academic journey.`
                  : 'Link your children to see their attendance, fees, and progress — all in one place.'}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setDialogOpen(true)}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white text-amber-700 text-sm font-semibold hover:bg-amber-50 transition-colors shadow-lg"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197" />
                </svg>
                {count > 0 ? 'Manage Children' : 'Link a Child'}
              </button>
              <button
                onClick={() => navigate('/parent/payments')}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white/15 text-white text-sm font-medium hover:bg-white/25 transition-colors"
              >
                Payments
              </button>
            </div>
          </div>

          {/* Personalized Quick Stats */}
          {count > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-8">
              {[
                { label: 'Linked Children', value: count, accent: 'text-amber-300' },
                { label: 'Avg Attendance', value: avgAttendance, suffix: '%', accent: avgAttendance >= 90 ? 'text-emerald-300' : 'text-rose-300' },
                { label: 'Total Paid', value: totalPaid, fmt: true, accent: 'text-emerald-300' },
                { label: 'Outstanding', value: totalOutstanding, fmt: true, accent: totalOutstanding > 0 ? 'text-rose-300' : 'text-amber-300' },
              ].map((m, i) => (
                <div
                  key={m.label}
                  className="bg-white/5 rounded-xl p-4 border border-white/[0.06] animate-fade-in-up"
                  style={{ animationDelay: `${i * 80}ms`, animationFillMode: 'both' }}
                >
                  <p className="text-xs text-white/40 font-medium tracking-wide uppercase">{m.label}</p>
                  <p className={`text-2xl font-bold text-white mt-1 ${m.accent}`}>
                    {(m as any).fmt ? (
                      formatCurrency(m.value as number)
                    ) : (
                      <><AnimatedCount value={m.value as number} duration={1000 + i * 200} />{(m as any).suffix || ''}</>
                    )}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Linked Children */}
        <div className="lg:col-span-2 bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-6">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-base font-semibold text-[var(--color-text-primary)]">
                {count > 0 ? 'Your Children' : 'No Children Linked'}
              </h2>
              <p className="text-sm text-[var(--color-text-tertiary)] mt-0.5">
                {count > 0 ? 'Personalized view of their academic data' : 'Link students to see personalized data here'}
              </p>
            </div>
            {count > 0 && (
              <button
                onClick={() => navigate('/parent/children')}
                className="text-xs font-medium text-[var(--color-brand-accent)] hover:text-[var(--color-brand-accent-hover)] transition-colors"
              >
                Manage &rarr;
              </button>
            )}
          </div>

          {count === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-center">
              <div className="flex items-center justify-center h-14 w-14 rounded-2xl bg-[var(--color-surface-hover)] mb-4">
                <svg className="h-7 w-7 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197" />
                </svg>
              </div>
              <p className="text-sm font-medium text-[var(--color-text-secondary)] mb-1">Link your first child</p>
              <p className="text-xs text-[var(--color-text-tertiary)] mb-5 max-w-xs">
                Search for your child's name or student number to link them to your parent account.
              </p>
              <button
                onClick={() => setDialogOpen(true)}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[var(--color-brand-accent)] text-white text-sm font-medium hover:bg-[var(--color-brand-accent-hover)] transition-colors"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Link a Child
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {childrenData.map((child) => {
                const { student, attendance, financial } = child
                const attendancePct = attendance?.percentage ?? null
                const outstanding = financial?.total_outstanding ?? null
                const paid = financial?.total_paid ?? null

                return (
                  <div
                    key={student.id}
                    className="flex items-center justify-between p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)] hover:shadow-sm hover:-translate-y-0.5 transition-all duration-[var(--motion-fast)] motion-reduce:transition-none motion-reduce:hover:translate-y-0"
                  >
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-brand-accent)]/10 flex-shrink-0">
                        <span className="text-xs font-bold text-[var(--color-brand-accent)]">
                          {student.first_name.charAt(0)}{student.last_name.charAt(0)}
                        </span>
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-[var(--color-text-primary)] truncate">
                          {student.first_name} {student.last_name}
                        </p>
                        <div className="flex items-center gap-3 text-xs text-[var(--color-text-tertiary)] mt-0.5">
                          <span className={`flex items-center gap-1 ${attendancePct !== null ? (attendancePct >= 90 ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]') : ''}`}>
                            <span className={`inline-block h-1.5 w-1.5 rounded-full ${attendancePct !== null ? (attendancePct >= 90 ? 'bg-[var(--color-success)]' : 'bg-[var(--color-danger)]') : 'bg-[var(--color-text-muted)]'}`} />
                            {attendancePct !== null ? `${attendancePct}%` : 'No data'}
                          </span>
                          {paid !== null && (
                            <span className="text-[var(--color-success)]">{formatCurrency(paid)} paid</span>
                          )}
                          {outstanding !== null && outstanding > 0 && (
                            <span className="text-[var(--color-danger)]">{formatCurrency(outstanding)} due</span>
                          )}
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => navigate(`/students/${student.id}`)}
                      className="text-xs font-medium text-[var(--color-brand-accent)] hover:text-[var(--color-brand-accent-hover)] transition-colors flex-shrink-0 ml-3"
                    >
                      View &rarr;
                    </button>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Quick Actions */}
        <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-6">
          <h2 className="text-base font-semibold text-[var(--color-text-primary)] mb-5">Quick Actions</h2>
          <div className="space-y-3">
            <button
              onClick={() => setDialogOpen(true)}
              className="w-full flex items-center gap-3 p-4 rounded-xl bg-[var(--color-brand-accent)]/5 border border-[var(--color-brand-accent)]/15 text-left hover:shadow-sm hover:-translate-y-0.5 transition-all duration-[var(--motion-fast)] motion-reduce:transition-none motion-reduce:hover:translate-y-0"
            >
              <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-brand-accent)]/10">
                <svg className="h-4.5 w-4.5 text-[var(--color-brand-accent)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-[var(--color-text-primary)]">{count > 0 ? 'Link Another Child' : 'Link a Child'}</p>
                <p className="text-xs text-[var(--color-text-tertiary)]">Search and add students to your view</p>
              </div>
            </button>

            <button
              onClick={() => navigate('/parent/children')}
              className="w-full flex items-center gap-3 p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)] text-left hover:shadow-sm hover:-translate-y-0.5 transition-all duration-[var(--motion-fast)] motion-reduce:transition-none motion-reduce:hover:translate-y-0"
            >
              <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-bg)]">
                <svg className="h-4.5 w-4.5 text-[var(--color-text-secondary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-[var(--color-text-primary)]">Manage Children</p>
                <p className="text-xs text-[var(--color-text-tertiary)]">View and remove linked students</p>
              </div>
            </button>

            <button
              onClick={() => navigate('/parent/payments')}
              className="w-full flex items-center gap-3 p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)] text-left hover:shadow-sm hover:-translate-y-0.5 transition-all duration-[var(--motion-fast)] motion-reduce:transition-none motion-reduce:hover:translate-y-0"
            >
              <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-bg)]">
                <svg className="h-4.5 w-4.5 text-[var(--color-text-secondary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-[var(--color-text-primary)]">Fee Payments</p>
                <p className="text-xs text-[var(--color-text-tertiary)]">View payment status</p>
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
                <p className="text-xs text-[var(--color-text-tertiary)]">View school updates</p>
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

      {/* Link Child Dialog */}
      <LinkChildDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        linkedIds={linkedIds}
        onLink={linkStudent}
        onLinkMultiple={linkMultiple}
      />
    </div>
  )
}
