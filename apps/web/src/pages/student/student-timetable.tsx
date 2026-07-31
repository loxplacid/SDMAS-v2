import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { studentPortalApi } from '../../api/student/student-portal-api'
import type { StudentTimetableResponse, TimetableDayGroup } from '../../api/student/student-portal-api'
import { Loading, ErrorState, EmptyState, Card } from '../../components/ui'

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']

export function StudentTimetablePage() {
  const navigate = useNavigate()
  const [data, setData] = useState<StudentTimetableResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeDay, setActiveDay] = useState<number>(new Date().getDay() - 1)

  useEffect(() => {
    studentPortalApi.getTimetable()
      .then(setData)
      .catch((err: any) => setError(err?.detail || 'Failed to load timetable'))
      .finally(() => setLoading(false))
  }, [])

  // Default to today (Mon=0)
  const today = Math.max(0, Math.min(4, new Date().getDay() - 1))
  const day = activeDay >= 0 && activeDay < 5 ? activeDay : today

  if (loading) return <Loading text="Loading timetable..." />
  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />
  if (!data || data.days.length === 0) {
    return (
      <div className="min-h-screen bg-[var(--color-bg)] pb-24">
        <div className="sticky top-0 z-10 bg-[var(--color-surface)] border-b border-[var(--color-border)] px-4 py-3">
          <div className="flex items-center gap-3">
            <button onClick={() => navigate('/student')} className="flex items-center justify-center h-9 w-9 rounded-xl text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] transition-colors">
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
            </button>
            <h1 className="text-lg font-bold text-[var(--color-text-primary)]">Timetable</h1>
          </div>
        </div>
        <EmptyState title="No timetable yet" description="Your class schedule will appear here once it's configured." />
      </div>
    )
  }

  const dayGroups: { [key: number]: TimetableDayGroup } = {}
  data.days.forEach((d) => { dayGroups[d.day_of_week] = d })

  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-24">
      {/* Sticky header */}
      <div className="sticky top-0 z-10 bg-[var(--color-surface)] border-b border-[var(--color-border)]">
        <div className="px-4 py-3">
          <div className="flex items-center gap-3">
            <button onClick={() => navigate('/student')} className="flex items-center justify-center h-9 w-9 rounded-xl text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] transition-colors">
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
            </button>
            <div>
              <h1 className="text-lg font-bold text-[var(--color-text-primary)]">Timetable</h1>
              {data.enrollment && (
                <p className="text-xs text-[var(--color-text-tertiary)]">
                  {data.enrollment.class_name}{data.enrollment.section_name ? ` - ${data.enrollment.section_name}` : ''}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Day tabs */}
        <div className="px-4 pb-3 overflow-x-auto scrollbar-none">
          <div className="flex gap-2">
            {DAYS.map((name, i) => {
              const entries = dayGroups[i]?.entries || []
              const hasEntries = entries.length > 0
              return (
                <button
                  key={i}
                  onClick={() => setActiveDay(i)}
                  className={`shrink-0 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                    day === i
                      ? 'bg-[var(--color-brand-accent)] text-white shadow-sm'
                      : 'bg-[var(--color-surface)] text-[var(--color-text-secondary)] border border-[var(--color-border)] hover:bg-[var(--color-surface-hover)]'
                  }`}
                >
                  {name.substring(0, 3)}
                  {hasEntries && (
                    <span className="ml-1.5 inline-block h-1.5 w-1.5 rounded-full bg-current opacity-50" />
                  )}
                </button>
              )
            })}
          </div>
        </div>
      </div>

      {/* Day content */}
      <div className="px-4 py-4 space-y-3">
        <div className="flex items-center gap-2 mb-2">
          <h2 className="text-sm font-semibold text-[var(--color-text-primary)]">{DAYS[day]}</h2>
          <span className="text-xs text-[var(--color-text-tertiary)]">
            {(dayGroups[day]?.entries?.length || 0)} class{(dayGroups[day]?.entries?.length || 0) !== 1 ? 'es' : ''}
          </span>
        </div>

        {(!dayGroups[day] || dayGroups[day].entries.length === 0) ? (
          <Card className="p-8 text-center">
            <div className="flex items-center justify-center h-12 w-12 rounded-2xl bg-[var(--color-surface-hover)] mx-auto mb-3">
              <svg className="h-6 w-6 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
            <p className="text-sm font-medium text-[var(--color-text-secondary)]">No classes today</p>
            <p className="text-xs text-[var(--color-text-tertiary)] mt-1">Enjoy your free day!</p>
          </Card>
        ) : (
          dayGroups[day].entries
            .sort((a, b) => (a.start_time || '').localeCompare(b.start_time || ''))
            .map((entry, i) => (
              <div key={entry.id} className="relative pl-6">
                {/* Timeline line */}
                {i > 0 && <div className="absolute left-2.5 top-0 bottom-1/2 w-0.5 bg-[var(--color-border)]" />}
                {i < dayGroups[day].entries.length - 1 && (
                  <div className="absolute left-2.5 top-1/2 bottom-0 w-0.5 bg-[var(--color-border)]" />
                )}
                {/* Dot */}
                <div className={`absolute left-1.5 top-4 h-3 w-3 rounded-full border-2 ${
                  entry.subject_name ? 'border-[var(--color-brand-accent)] bg-[var(--color-brand-accent)]/20' : 'border-[var(--color-border)] bg-[var(--color-surface)]'
                }`} />

                <Card className="p-4 ml-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-[var(--color-text-primary)]">
                        {entry.subject_name || 'Untitled'}
                      </p>
                      {entry.subject_code && (
                        <p className="text-xs text-[var(--color-text-tertiary)]">{entry.subject_code}</p>
                      )}
                    </div>
                    <div className="text-right shrink-0">
                      {entry.start_time && (
                        <p className="text-xs font-medium text-[var(--color-brand-accent)]">
                          {entry.start_time}
                          {entry.end_time ? ` - ${entry.end_time}` : ''}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 mt-2 text-xs text-[var(--color-text-tertiary)]">
                    {entry.teacher_name && (
                      <span className="flex items-center gap-1">
                        <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                        </svg>
                        {entry.teacher_name}
                      </span>
                    )}
                    {entry.room_name && (
                      <span className="flex items-center gap-1">
                        <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5" />
                        </svg>
                        {entry.room_name}
                      </span>
                    )}
                  </div>
                </Card>
              </div>
            ))
        )}
      </div>
    </div>
  )
}

export default StudentTimetablePage
