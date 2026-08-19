import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { studentPortalApi } from '../../api/student/student-portal-api'
import type { EnrolledSubject } from '../../api/student/student-portal-api'
import { Loading, ErrorState, EmptyState, Card } from '../../components/ui'

export function StudentSubjectsPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<{ subjects: EnrolledSubject[]; enrollment: any } | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    studentPortalApi.getSubjects()
      .then(setData)
      .catch((err: any) => setError(err?.detail || 'Failed to load subjects'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Loading text="Loading subjects..." />
  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />

  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-24">
      <div className="sticky top-0 z-10 bg-[var(--color-surface)] border-b border-[var(--color-border)] px-4 py-3">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/student')} className="flex items-center justify-center h-9 w-9 rounded-xl text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] transition-colors">
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
          </button>
          <div>
            <h1 className="text-lg font-bold text-[var(--color-text-primary)]">My Subjects</h1>
            {data?.enrollment && <p className="text-xs text-[var(--color-text-tertiary)]">{data.enrollment.class_name}</p>}
          </div>
        </div>
      </div>

      <div className="px-4 py-4 space-y-3">
        {(!data || data.subjects.length === 0) ? (
          <EmptyState title="No subjects assigned" description="Your subjects will appear here once they are configured." />
        ) : (
          data.subjects.map((subj) => (
            <Card key={subj.id} className="p-4 group">
              <div className="flex items-start gap-3">
                <div className="flex items-center justify-center h-10 w-10 rounded-lg bg-[var(--color-brand-accent)]/10 text-[var(--color-brand-accent)] text-xs font-bold shrink-0">
                  {subj.name.substring(0, 2).toUpperCase()}
                </div>
                <div className="min-w-0 flex-1">
                  <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">{subj.name}</h3>
                  <p className="text-xs text-[var(--color-text-tertiary)]">{subj.code}</p>
                  {subj.teacher_name && (
                    <p className="text-xs text-[var(--color-text-muted)] mt-1.5 flex items-center gap-1">
                      <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                      </svg>
                      {subj.teacher_name}
                    </p>
                  )}
                </div>
              </div>

              {(subj.syllabus || subj.textbook) && (
                <div className="mt-3 pt-3 border-t border-[var(--color-border)] space-y-1">
                  {subj.textbook && (
                    <p className="text-xs text-[var(--color-text-tertiary)]">
                      <span className="font-medium">Textbook:</span> {subj.textbook}
                    </p>
                  )}
                  {subj.total_hours && (
                    <p className="text-xs text-[var(--color-text-tertiary)]">
                      <span className="font-medium">Total Hours:</span> {subj.total_hours}
                    </p>
                  )}
                </div>
              )}
            </Card>
          ))
        )}
      </div>
    </div>
  )
}

export default StudentSubjectsPage
