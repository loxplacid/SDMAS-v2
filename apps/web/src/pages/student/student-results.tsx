import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { studentPortalApi } from '../../api/student/student-portal-api'
import type { StudentResultsResponse, TermResult } from '../../api/student/student-portal-api'
import { Loading, ErrorState, EmptyState, Card } from '../../components/ui'

export function StudentResultsPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<StudentResultsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTerm, setActiveTerm] = useState<string | null>(null)

  useEffect(() => {
    studentPortalApi.getResults()
      .then((res) => {
        setData(res)
        if (res.terms.length > 0) setActiveTerm(res.terms[0].term_name)
      })
      .catch((err: any) => setError(err?.detail || 'Failed to load results'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Loading text="Loading results..." />
  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />

  if (!data || data.terms.length === 0) {
    return (
      <div className="min-h-screen bg-[var(--color-bg)] pb-24">
        <div className="sticky top-0 z-10 bg-[var(--color-surface)] border-b border-[var(--color-border)] px-4 py-3">
          <div className="flex items-center gap-3">
            <button onClick={() => navigate('/student')} className="flex items-center justify-center h-9 w-9 rounded-xl text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] transition-colors">
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
            </button>
            <h1 className="text-lg font-bold text-[var(--color-text-primary)]">Academic Results</h1>
          </div>
        </div>
        <EmptyState title="No results yet" description="Your academic results will appear here once they are published." />
      </div>
    )
  }

  const termData = data.terms.find((t) => t.term_name === activeTerm) || data.terms[0]

  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-24">
      <div className="sticky top-0 z-10 bg-[var(--color-surface)] border-b border-[var(--color-border)] px-4 py-3">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/student')} className="flex items-center justify-center h-9 w-9 rounded-xl text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] transition-colors">
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
          </button>
          <div>
            <h1 className="text-lg font-bold text-[var(--color-text-primary)]">Academic Results</h1>
            {data.enrollment && <p className="text-xs text-[var(--color-text-tertiary)]">{data.enrollment.class_name}</p>}
          </div>
        </div>

        {/* Term tabs */}
        {data.terms.length > 1 && (
          <div className="flex gap-2 mt-3 overflow-x-auto scrollbar-none">
            {data.terms.map((t) => (
              <button
                key={t.term_name}
                onClick={() => setActiveTerm(t.term_name)}
                className={`shrink-0 px-4 py-2 rounded-xl text-xs font-medium transition-all ${
                  activeTerm === t.term_name
                    ? 'bg-[var(--color-brand-accent)] text-white shadow-sm'
                    : 'bg-[var(--color-surface)] text-[var(--color-text-secondary)] border border-[var(--color-border)]'
                }`}
              >
                {t.term_name}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="px-4 py-4 space-y-4">
        {/* Overall stats */}
        <div className="grid grid-cols-2 gap-3">
          <Card className="p-4 text-center">
            <p className="text-2xl font-bold text-[var(--color-brand-accent)]">{data.overall_percentage}%</p>
            <p className="text-xs text-[var(--color-text-tertiary)] mt-1">Overall</p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-2xl font-bold text-[var(--color-text-primary)]">
              {data.overall_grade_point_average?.toFixed(2) || '—'}
            </p>
            <p className="text-xs text-[var(--color-text-tertiary)] mt-1">GPA</p>
          </Card>
        </div>

        {/* Term summary */}
        <Card className="p-4 bg-gradient-to-br from-violet-50 to-indigo-50 dark:from-violet-900/20 dark:to-indigo-900/20 border-violet-200 dark:border-violet-800">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-violet-600 dark:text-violet-400 uppercase tracking-wide">{termData.term_name}</p>
              <p className="text-sm font-semibold text-violet-800 dark:text-violet-200 mt-0.5">
                {termData.percentage}% · GPA: {termData.grade_point_average?.toFixed(2) || '—'}
              </p>
            </div>
            <p className="text-xs text-violet-500">
              {termData.total_marks}/{termData.total_max_marks}
            </p>
          </div>
        </Card>

        {/* Subject grades */}
        <div className="space-y-3">
          {termData.subjects.map((subject, i) => (
            <Card key={i} className="p-4">
              <div className="flex items-center justify-between">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-[var(--color-text-primary)]">{subject.subject_name}</p>
                  <p className="text-xs text-[var(--color-text-tertiary)]">{subject.subject_code}</p>
                </div>
                <div className="text-right shrink-0 ml-3">
                  <div className="flex items-center gap-2">
                    {subject.grade && (
                      <span className="text-xl font-bold text-[var(--color-brand-accent)]">{subject.grade}</span>
                    )}
                    <div className="text-xs text-[var(--color-text-tertiary)]">
                      {subject.marks_obtained !== null && (
                        <p>{subject.marks_obtained}/{subject.max_marks}</p>
                      )}
                    </div>
                  </div>
                  {subject.remarks && (
                    <p className="text-xs text-[var(--color-text-muted)] mt-0.5">{subject.remarks}</p>
                  )}
                </div>
              </div>
              {subject.marks_obtained !== null && (
                <div className="mt-2 h-1.5 rounded-full bg-[var(--color-border)] overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      (subject.marks_obtained / subject.max_marks) >= 0.8 ? 'bg-emerald-500' :
                      (subject.marks_obtained / subject.max_marks) >= 0.5 ? 'bg-amber-500' : 'bg-rose-500'
                    }`}
                    style={{ width: `${(subject.marks_obtained / subject.max_marks) * 100}%` }}
                  />
                </div>
              )}
            </Card>
          ))}
        </div>
      </div>
    </div>
  )
}

export default StudentResultsPage
