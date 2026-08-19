import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { parentApi } from '../../api/parent/parent-api'
import type { LinkedChild, ParentAcademicResponse } from '../../api/parent/parent-api'
import { Loading, ErrorState, EmptyState, Card } from '../../components/ui'
import { useParentChildren } from '../../hooks/use-parent-children'

export function ParentAcademicPage() {
  const navigate = useNavigate()
  const { linkedIds } = useParentChildren()
  const [children, setChildren] = useState<LinkedChild[]>([])
  const [selectedChildId, setSelectedChildId] = useState<number | null>(null)
  const [academicData, setAcademicData] = useState<ParentAcademicResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (linkedIds.length === 0) { setLoading(false); return }
    parentApi.listChildren()
      .then((kids) => { setChildren(kids); if (kids.length > 0) setSelectedChildId(kids[0].id) })
      .catch((err: any) => setError(err?.detail || 'Failed to load children'))
      .finally(() => setLoading(false))
  }, [linkedIds])

  useEffect(() => {
    if (!selectedChildId) return
    setLoading(true)
    parentApi.getChildAcademic(selectedChildId)
      .then(setAcademicData)
      .catch((err: any) => setError(err?.detail || 'Failed to load academic data'))
      .finally(() => setLoading(false))
  }, [selectedChildId])

  if (loading) return <Loading text="Loading academic data..." />
  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />
  if (children.length === 0) {
    return (
      <EmptyState
        title="No children linked"
        description="Link your children first to see their academic performance."
        action={{ label: 'Go to Dashboard', onClick: () => navigate('/parent') }}
      />
    )
  }

  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-24">
      {/* Mobile header */}
      <div className="sticky top-0 z-10 bg-[var(--color-surface)] border-b border-[var(--color-border)] px-4 py-3">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/parent')} className="flex items-center justify-center h-9 w-9 rounded-xl text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] transition-colors">
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div>
            <h1 className="text-lg font-bold text-[var(--color-text-primary)]">Academic Performance</h1>
            <p className="text-xs text-[var(--color-text-tertiary)]">Grades, history & progress</p>
          </div>
        </div>
      </div>

      {/* Child tabs */}
      {children.length > 1 && (
        <div className="px-4 py-3 overflow-x-auto scrollbar-none">
          <div className="flex gap-2">
            {children.map((child) => (
              <button
                key={child.id}
                onClick={() => setSelectedChildId(child.id)}
                className={`shrink-0 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                  selectedChildId === child.id
                    ? 'bg-[var(--color-brand-accent)] text-white shadow-sm'
                    : 'bg-[var(--color-surface)] text-[var(--color-text-secondary)] border border-[var(--color-border)] hover:bg-[var(--color-surface-hover)]'
                }`}
              >
                {child.first_name} {child.last_name}
              </button>
            ))}
          </div>
        </div>
      )}

      {academicData && (
        <div className="px-4 space-y-4">
          {/* Current enrollment */}
          {academicData.current_enrollment && (
            <Card className="p-4">
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center h-10 w-10 rounded-xl bg-indigo-500/10">
                  <svg className="h-5 w-5 text-indigo-600 dark:text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-semibold text-indigo-800 dark:text-indigo-200">Current Enrollment</p>
                  <p className="text-xs text-indigo-600 dark:text-indigo-400 mt-0.5">
                    {academicData.current_enrollment.class_name}
                    {academicData.current_enrollment.section_name && ` · ${academicData.current_enrollment.section_name}`}
                    {academicData.current_enrollment.academic_year_name && ` · ${academicData.current_enrollment.academic_year_name}`}
                  </p>
                </div>
              </div>
            </Card>
          )}

          {/* Attendance summary */}
          <Card className="p-4">
            <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">Attendance</h3>
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <div className="flex items-baseline gap-1">
                  <span className="text-2xl font-bold text-[var(--color-brand-accent)]">{academicData.attendance_summary.percentage}%</span>
                  <span className="text-xs text-[var(--color-text-tertiary)]">overall</span>
                </div>
                <p className="text-xs text-[var(--color-text-tertiary)] mt-1">
                  {academicData.attendance_summary.present} present · {academicData.attendance_summary.absent} absent · {academicData.attendance_summary.late} late
                </p>
              </div>
              {/* Attendance ring */}
              <div className="relative h-14 w-14">
                <svg className="h-14 w-14 -rotate-90" viewBox="0 0 36 36">
                  <circle cx="18" cy="18" r="16" fill="none" stroke="currentColor" strokeWidth="3" className="text-[var(--color-border)]" />
                  <circle cx="18" cy="18" r="16" fill="none" stroke="currentColor" strokeWidth="3"
                    strokeDasharray={`${academicData.attendance_summary.percentage} ${100 - academicData.attendance_summary.percentage}`}
                    className="text-[var(--color-brand-accent)]" strokeLinecap="round" />
                </svg>
              </div>
            </div>
          </Card>

          {/* Grades */}
          <Card className="p-4">
            <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">Subject Grades</h3>
            {academicData.grades.length === 0 ? (
              <p className="text-sm text-[var(--color-text-tertiary)] text-center py-4">No grades recorded yet</p>
            ) : (
              <div className="space-y-3">
                {academicData.grades.map((grade, i) => (
                  <div key={i} className="flex items-center justify-between p-3 rounded-xl bg-[var(--color-bg)]">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-[var(--color-text-primary)]">{grade.subject_name}</p>
                      {grade.remarks && <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">{grade.remarks}</p>}
                    </div>
                    <div className="text-right shrink-0 ml-3">
                      {grade.grade && (
                        <span className="text-lg font-bold text-[var(--color-brand-accent)]">{grade.grade}</span>
                      )}
                      {grade.score !== null && (
                        <span className="text-sm text-[var(--color-text-secondary)] ml-1">({grade.score}%)</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Academic History */}
          {academicData.academic_history.length > 0 && (
            <Card className="p-4">
              <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">Academic History</h3>
              <div className="space-y-2">
                {academicData.academic_history.map((record, i) => (
                  <div key={i} className="flex items-center gap-3 p-3 rounded-xl bg-[var(--color-bg)]">
                    <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-[var(--color-surface-hover)] shrink-0">
                      <span className="text-xs font-bold text-[var(--color-text-secondary)]">{i + 1}</span>
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-[var(--color-text-primary)]">
                        {record.class_name}
                        {record.section_name && ` - ${record.section_name}`}
                      </p>
                      <p className="text-xs text-[var(--color-text-tertiary)]">
                        {record.academic_year_name}
                        <span className={`ml-2 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${
                          record.status === 'active' ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' : 'bg-[var(--color-surface-hover)] text-[var(--color-text-tertiary)]'
                        }`}>
                          {record.status}
                        </span>
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}

export default ParentAcademicPage
