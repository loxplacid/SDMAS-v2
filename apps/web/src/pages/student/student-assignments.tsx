import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { studentPortalApi } from '../../api/student/student-portal-api'
import type { StudentAssignment } from '../../api/student/student-portal-api'
import { Loading, ErrorState, EmptyState, Card } from '../../components/ui'
import { formatDate } from '../../lib/utils'

type TabType = 'pending' | 'overdue' | 'submitted' | 'graded'

const TAB_LABELS: Record<TabType, string> = {
  pending: 'Pending',
  overdue: 'Overdue',
  submitted: 'Submitted',
  graded: 'Graded',
}

const getCount = (data: any, tab: TabType) => (data?.[tab]?.length || 0)

export function StudentAssignmentsPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<TabType>('pending')
  const [expandedId, setExpandedId] = useState<number | null>(null)

  useEffect(() => {
    studentPortalApi.getAssignments()
      .then(setData)
      .catch((err: any) => setError(err?.detail || 'Failed to load assignments'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Loading text="Loading assignments..." />
  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />

  const tabs: TabType[] = ['pending', 'overdue', 'submitted', 'graded']
  const totalCount = tabs.reduce((sum, t) => sum + getCount(data, t), 0)

  if (!data || totalCount === 0) {
    return (
      <div className="min-h-screen bg-[var(--color-bg)] pb-24">
        <div className="sticky top-0 z-10 bg-[var(--color-surface)] border-b border-[var(--color-border)] px-4 py-3">
          <div className="flex items-center gap-3">
            <button onClick={() => navigate('/student')} className="flex items-center justify-center h-9 w-9 rounded-xl text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] transition-colors">
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
            </button>
            <h1 className="text-lg font-bold text-[var(--color-text-primary)]">Assignments</h1>
          </div>
        </div>
        <EmptyState title="No assignments yet" description="Your assignments will appear here once they are published." />
      </div>
    )
  }

  const assignments: StudentAssignment[] = data[activeTab] || []

  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-24">
      <div className="sticky top-0 z-10 bg-[var(--color-surface)] border-b border-[var(--color-border)]">
        <div className="px-4 py-3">
          <div className="flex items-center gap-3">
            <button onClick={() => navigate('/student')} className="flex items-center justify-center h-9 w-9 rounded-xl text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] transition-colors">
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
            </button>
            <div><h1 className="text-lg font-bold text-[var(--color-text-primary)]">Assignments</h1></div>
          </div>
        </div>

        {/* Tab bar */}
        <div className="px-4 pb-3 overflow-x-auto scrollbar-none">
          <div className="flex gap-2">
            {tabs.map((tab) => {
              const count = getCount(data, tab)
              return (
                <button
                  key={tab}
                  onClick={() => { setActiveTab(tab); setExpandedId(null) }}
                  className={`relative shrink-0 px-4 py-2 rounded-xl text-xs font-medium transition-all ${
                    activeTab === tab
                      ? 'bg-[var(--color-brand-accent)] text-white shadow-sm'
                      : 'bg-[var(--color-surface)] text-[var(--color-text-secondary)] border border-[var(--color-border)]'
                  }`}
                >
                  {TAB_LABELS[tab]}
                  {count > 0 && (
                    <span className={`ml-1.5 inline-flex items-center justify-center h-4 min-w-[16px] px-1 rounded-full text-[10px] font-bold ${
                      activeTab === tab ? 'bg-white/20 text-white' : 'bg-[var(--color-surface-hover)] text-[var(--color-text-tertiary)]'
                    }`}>
                      {count}
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        </div>
      </div>

      <div className="px-4 py-4 space-y-3">
        {assignments.length === 0 ? (
          <Card className="p-8 text-center">
            <p className="text-sm text-[var(--color-text-tertiary)]">No {TAB_LABELS[activeTab].toLowerCase()} assignments</p>
          </Card>
        ) : (
          assignments.map((assignment) => (
            <Card key={assignment.id} className={`p-4 ${
              activeTab === 'overdue' ? 'border-l-4 border-l-rose-500' :
              activeTab === 'pending' ? 'border-l-4 border-l-amber-500' :
              activeTab === 'graded' ? 'border-l-4 border-l-emerald-500' : ''
            }`}>
              <button
                onClick={() => setExpandedId(expandedId === assignment.id ? null : assignment.id)}
                className="w-full text-left"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-[var(--color-text-primary)]">{assignment.title}</p>
                    <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">
                      {assignment.subject_name}
                      {assignment.teacher_name && ` · ${assignment.teacher_name}`}
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    {assignment.due_at && (
                      <p className={`text-xs font-medium ${activeTab === 'overdue' ? 'text-rose-500' : 'text-[var(--color-text-tertiary)]'}`}>
                        Due {formatDate(assignment.due_at)}
                      </p>
                    )}
                    {assignment.max_score && (
                      <p className="text-xs text-[var(--color-text-tertiary)]">{assignment.max_score} pts</p>
                    )}
                  </div>
                </div>

                {expandedId === assignment.id && (
                  <div className="mt-3 pt-3 border-t border-[var(--color-border)] space-y-3">
                    {assignment.description && (
                      <p className="text-sm text-[var(--color-text-secondary)]">{assignment.description}</p>
                    )}
                    {assignment.instructions && (
                      <div className="rounded-xl bg-[var(--color-bg)] p-3">
                        <p className="text-xs font-medium text-[var(--color-text-primary)] mb-1">Instructions:</p>
                        <p className="text-xs text-[var(--color-text-secondary)] whitespace-pre-wrap">{assignment.instructions}</p>
                      </div>
                    )}
                    {assignment.submission_status && (
                      <div className={`rounded-xl p-3 text-xs ${
                        assignment.is_late ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400' :
                        assignment.submission_status === 'graded' ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' :
                        'bg-blue-500/10 text-blue-600 dark:text-blue-400'
                      }`}>
                        {assignment.is_late && <span className="font-medium">Late submission · </span>}
                        {assignment.submission_status === 'graded' ? (
                          <>Score: {assignment.score}/{assignment.max_score} · Grade: {assignment.grade}</>
                        ) : (
                          <>Submitted {assignment.submitted_at ? formatDate(assignment.submitted_at) : ''} — awaiting grading</>
                        )}
                      </div>
                    )}
                    {assignment.feedback && (
                      <div className="rounded-xl bg-amber-500/10 p-3">
                        <p className="text-xs font-medium text-amber-700 dark:text-amber-300 mb-1">Feedback:</p>
                        <p className="text-xs text-amber-600 dark:text-amber-400">{assignment.feedback}</p>
                      </div>
                    )}
                  </div>
                )}
              </button>
            </Card>
          ))
        )}
      </div>
    </div>
  )
}

export default StudentAssignmentsPage
