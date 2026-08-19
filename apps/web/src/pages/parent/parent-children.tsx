import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { studentApi } from '../../api/student/student-api'
import type { StudentResponse } from '../../api/generated/types'
import { useParentChildren } from '../../hooks/use-parent-children'
import { LinkChildDialog } from '../../components/ui/link-child-dialog'
import { Loading, ErrorState, EmptyState, AnimatedCount } from '../../components/ui'
import { formatCurrency } from '../../lib/utils'
import { attendanceApi } from '../../api/attendance/attendance-api'
import { summaryApi } from '../../api/fees/summary-api'
import { academicYearApi } from '../../api/academic/academic-year-api'
import type { StudentAttendanceSummary, StudentFinancialSummary } from '../../api/generated/types'

/** Per-child extended data */
interface ChildData {
  student: StudentResponse
  attendance: StudentAttendanceSummary | null
  financial: StudentFinancialSummary | null
}

export function ParentChildrenPage() {
  const navigate = useNavigate()
  const { linkedIds, linkStudent, linkMultiple, unlinkStudent } = useParentChildren()
  const [childrenData, setChildrenData] = useState<ChildData[]>([])
  const [allStudents, setAllStudents] = useState<StudentResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const fetchIdRef = useRef(0)

  // Fetch all students (for looking up linked IDs)
  const fetchStudents = useRef(async () => {
    try {
      const result = await studentApi.list({ size: 200 })
      return result.items
    } catch {
      return [] as StudentResponse[]
    }
  }).current

  // Fetch all students to look up linked IDs
  useEffect(() => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)

    const loadData = async () => {
      try {
        const result = await studentApi.list({ size: 200 })
        if (fetchId !== fetchIdRef.current) return
        setAllStudents(result.items)

        if (linkedIds.length === 0) {
          setChildrenData([])
          setLoading(false)
          return
        }

        // Get linked students
        const linkedStudents = result.items.filter((s) => linkedIds.includes(s.id))

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

        // Fetch per-child data
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
        if (fetchId === fetchIdRef.current) {
          setChildrenData(results)
          setLoading(false)
        }
      } catch (err: any) {
        if (fetchId === fetchIdRef.current) {
          setError(err?.detail || 'Failed to load data')
          setLoading(false)
        }
      }
    }

    loadData()
  }, [linkedIds])

  if (loading) {
    return (
      <div className="space-y-8 animate-fade-in">
        <div className="h-8 w-48 rounded-lg bg-[var(--color-border)] animate-skeleton" />
        <div className="space-y-4">
          {[1, 2].map((i) => (
            <div key={i} className="h-32 rounded-xl bg-[var(--color-border)] animate-skeleton" />
          ))}
        </div>
      </div>
    )
  }

  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[var(--color-text-primary)]">My Children</h1>
          <p className="text-sm text-[var(--color-text-tertiary)] mt-0.5">
            {childrenData.length > 0
              ? `You have ${childrenData.length} linked child${childrenData.length !== 1 ? 'ren' : ''}`
              : 'Link students to see their data in your dashboard'}
          </p>
        </div>
        <button
          onClick={() => setDialogOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[var(--color-brand-accent)] text-white text-sm font-medium hover:bg-[var(--color-brand-accent-hover)] transition-colors shadow-sm"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Add Child
        </button>
      </div>

      {/* Children List */}
      {childrenData.length === 0 ? (
        <EmptyState
          title="No children linked yet"
          description="Search for students to add them to your parent view."
          action={{ label: 'Link a Child', onClick: () => setDialogOpen(true) }}
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {childrenData.map((child) => {
            const { student, attendance, financial } = child
            const attendancePct = attendance?.percentage ?? null
            const outstanding = financial?.total_outstanding ?? null
            const totalPaid = financial?.total_paid ?? null

            return (
              <div
                key={student.id}
                className="bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)] p-4 hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none"
              >
                {/* Student Header */}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="flex items-center justify-center h-10 w-10 rounded-xl bg-[var(--color-brand-accent)]/10">
                      <span className="text-sm font-bold text-[var(--color-brand-accent)]">
                        {student.first_name.charAt(0)}{student.last_name.charAt(0)}
                      </span>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-[var(--color-text-primary)]">
                        {student.first_name} {student.last_name}
                      </p>
                      <p className="text-xs text-[var(--color-text-tertiary)]">
                        {student.student_number}
                        {student.status !== 'active' && (
                          <span className="ml-2 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-[var(--color-warning)]/10 text-[var(--color-warning-dark)]">
                            {student.status}
                          </span>
                        )}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => unlinkStudent(student.id)}
                    className="flex items-center justify-center h-8 w-8 rounded-lg text-[var(--color-text-tertiary)] hover:bg-[var(--color-danger-light)] hover:text-[var(--color-danger)] transition-colors"
                    title="Unlink student"
                  >
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-3 gap-3 mb-4">
                  <div className="rounded-xl bg-[var(--color-bg)] p-3 text-center">
                    <p className={`text-lg font-bold ${attendancePct !== null && attendancePct >= 90 ? 'text-[var(--color-success)]' : attendancePct !== null ? 'text-[var(--color-danger)]' : 'text-[var(--color-text-muted)]'}`}>
                      {attendancePct !== null ? (
                        <><AnimatedCount value={attendancePct} duration={800} />%</>
                      ) : (
                        '—'
                      )}
                    </p>
                    <p className="text-[10px] text-[var(--color-text-tertiary)] uppercase tracking-wide font-medium">Attendance</p>
                  </div>
                  <div className="rounded-xl bg-[var(--color-bg)] p-3 text-center">
                    <p className="text-lg font-bold text-[var(--color-success)]">
                      {totalPaid !== null ? formatCurrency(totalPaid) : '—'}
                    </p>
                    <p className="text-[10px] text-[var(--color-text-tertiary)] uppercase tracking-wide font-medium">Paid</p>
                  </div>
                  <div className="rounded-xl bg-[var(--color-bg)] p-3 text-center">
                    <p className={`text-lg font-bold ${outstanding !== null && outstanding > 0 ? 'text-[var(--color-danger)]' : 'text-[var(--color-text-muted)]'}`}>
                      {outstanding !== null ? formatCurrency(outstanding) : '—'}
                    </p>
                    <p className="text-[10px] text-[var(--color-text-tertiary)] uppercase tracking-wide font-medium">Outstanding</p>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex gap-2">
                  <button
                    onClick={() => navigate(`/students/${student.id}`)}
                    className="flex-1 text-center py-2 rounded-xl text-xs font-medium text-[var(--color-brand-accent)] bg-[var(--color-brand-accent-subtle)] hover:bg-[var(--color-brand-accent)]/15 transition-colors"
                  >
                    View Profile
                  </button>
                  <button
                    onClick={() => navigate(`/attendance/student/${student.id}`)}
                    className="flex-1 text-center py-2 rounded-xl text-xs font-medium text-[var(--color-text-secondary)] bg-[var(--color-bg)] hover:bg-[var(--color-surface-hover)] transition-colors"
                  >
                    Attendance
                  </button>
                  <button
                    onClick={() => navigate(`/fees/student-fees`)}
                    className="flex-1 text-center py-2 rounded-xl text-xs font-medium text-[var(--color-text-secondary)] bg-[var(--color-bg)] hover:bg-[var(--color-surface-hover)] transition-colors"
                  >
                    Fees
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

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
