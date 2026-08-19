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
import { Loading, ErrorState } from '../../components/ui'
import { PageHeader } from '../../components/ui/page-header'
import { HubStatCard } from '../../components/ui/hub-page'
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
      let activeYearId: number | null = null
      try {
        const yearResult = await academicYearApi.list({ status: 'active', size: 1 })
        if (yearResult.items.length > 0) {
          activeYearId = yearResult.items[0].id
        }
      } catch {
        // No active academic year found
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

  const totalAttendance = childrenData.reduce((sum, c) => sum + (c.attendance?.percentage || 0), 0)
  const avgAttendance = childrenData.length > 0 ? Math.round(totalAttendance / childrenData.length) : 0
  const totalOutstanding = childrenData.reduce((sum, c) => sum + (c.financial?.total_outstanding || 0), 0)
  const totalPaid = childrenData.reduce((sum, c) => sum + (c.financial?.total_paid || 0), 0)

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="space-y-2">
          <div className="h-5 w-48 rounded bg-[var(--color-border)] animate-skeleton" />
          <div className="h-3 w-72 rounded bg-[var(--color-border)] animate-skeleton" />
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-20 rounded-xl bg-[var(--color-border)] animate-skeleton" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 h-64 rounded-xl bg-[var(--color-border)] animate-skeleton" />
          <div className="h-64 rounded-xl bg-[var(--color-border)] animate-skeleton" />
        </div>
      </div>
    )
  }

  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />

  return (
    <div className="space-y-4">
      <PageHeader
        title={count > 0 ? `Welcome back, ${user?.display_name || user?.username}` : 'Parent Portal'}
        subtitle={count > 0 ? `Tracking ${count} linked child${count !== 1 ? 'ren' : ''}` : 'Link your children to see their academic data'}
        actions={
          <div className="flex gap-2">
            <button
              onClick={() => setDialogOpen(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--color-brand-accent)] text-white text-sm font-medium hover:bg-[var(--color-brand-accent-hover)] transition-colors"
            >
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              {count > 0 ? 'Link Child' : 'Link a Child'}
            </button>
            {count > 0 && (
              <button
                onClick={() => navigate('/parent/payments')}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-secondary)] text-sm font-medium hover:bg-[var(--color-surface-hover)] transition-colors"
              >
                Payments
              </button>
            )}
          </div>
        }
      />

      {count > 0 && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <HubStatCard
            stat={{ label: 'Linked Children', value: count, route: '/parent/children' }}
          />
          <HubStatCard
            stat={{ label: 'Avg Attendance', value: `${avgAttendance}%`, route: '/parent/children' }}
          />
          <HubStatCard
            stat={{ label: 'Total Paid', value: formatCurrency(totalPaid), route: '/parent/payments' }}
          />
          <HubStatCard
            stat={{ label: 'Outstanding', value: formatCurrency(totalOutstanding), route: '/parent/payments' }}
          />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Children list */}
        <div className="lg:col-span-2 bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)] p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-sm font-semibold text-[var(--color-text-primary)]">
                {count > 0 ? 'Your Children' : 'No Children Linked'}
              </h2>
              <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">
                {count > 0 ? 'Academic data for linked students' : 'Link students to see personalized data'}
              </p>
            </div>
            {count > 0 && (
              <button
                onClick={() => navigate('/parent/children')}
                className="text-xs font-medium text-[var(--color-brand-accent)] hover:text-[var(--color-brand-accent-hover)] transition-colors"
              >
                Manage →
              </button>
            )}
          </div>

          {count === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-center">
              <div className="flex items-center justify-center h-12 w-12 rounded-xl bg-[var(--color-surface-hover)] mb-3">
                <svg className="h-6 w-6 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197" />
                </svg>
              </div>
              <p className="text-sm font-medium text-[var(--color-text-secondary)] mb-1">Link your first child</p>
              <p className="text-xs text-[var(--color-text-tertiary)] mb-4 max-w-xs">
                Search for your child's name or student number to link them to your account.
              </p>
              <button
                onClick={() => setDialogOpen(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--color-brand-accent)] text-white text-sm font-medium hover:bg-[var(--color-brand-accent-hover)] transition-colors"
              >
                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Link a Child
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              {childrenData.map((child) => {
                const { student, attendance, financial } = child
                const attendancePct = attendance?.percentage ?? null
                const outstanding = financial?.total_outstanding ?? null
                const paid = financial?.total_paid ?? null

                return (
                  <div
                    key={student.id}
                    className="flex items-center justify-between p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] hover:border-[var(--color-brand-accent)]/30 transition-colors"
                  >
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-[var(--color-brand-accent)]/10 flex-shrink-0">
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
                      View →
                    </button>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Quick Actions */}
        <div className="bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)] p-4">
          <h2 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">Quick Actions</h2>
          <div className="space-y-1.5">
            {[
              {
                label: 'Link a Child',
                desc: 'Search and add students',
                onClick: () => setDialogOpen(true),
                icon: (
                  <svg className="h-4 w-4 text-[var(--color-brand-accent)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197" />
                  </svg>
                ),
              },
              {
                label: 'Fee Payments',
                desc: 'View payment status',
                onClick: () => navigate('/parent/payments'),
                icon: (
                  <svg className="h-4 w-4 text-[var(--color-text-secondary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2" />
                  </svg>
                ),
              },
              {
                label: 'Notifications',
                desc: 'View school updates',
                onClick: () => navigate('/notifications'),
                icon: (
                  <svg className="h-4 w-4 text-[var(--color-text-secondary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                  </svg>
                ),
              },
              {
                label: 'My Profile',
                desc: 'Account details',
                onClick: () => navigate('/profile'),
                icon: (
                  <svg className="h-4 w-4 text-[var(--color-text-secondary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                ),
              },
            ].map((item) => (
              <button
                key={item.label}
                onClick={item.onClick}
                className="w-full flex items-center gap-3 p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-left hover:border-[var(--color-brand-accent)]/30 transition-colors"
              >
                {item.icon}
                <div>
                  <p className="text-sm font-medium text-[var(--color-text-primary)]">{item.label}</p>
                  <p className="text-xs text-[var(--color-text-tertiary)]">{item.desc}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

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
