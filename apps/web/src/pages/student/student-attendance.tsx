import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { studentPortalApi } from '../../api/student/student-portal-api'
import type { StudentAttendanceResponse } from '../../api/student/student-portal-api'
import { Loading, ErrorState, EmptyState, Card } from '../../components/ui'
import { formatDate } from '../../lib/utils'

const STATUS_BADGE: Record<string, string> = {
  present: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  absent: 'bg-rose-500/10 text-rose-600 dark:text-rose-400',
  late: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
  excused: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
}

export function StudentAttendancePage() {
  const navigate = useNavigate()
  const [data, setData] = useState<StudentAttendanceResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    studentPortalApi.getAttendance(365)
      .then(setData)
      .catch((err: any) => setError(err?.detail || 'Failed to load attendance'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Loading text="Loading attendance..." />
  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />
  if (!data) return <EmptyState title="No data" description="Attendance data is not available yet." />

  const { summary, records, current_streak, monthly_breakdown } = data

  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-24">
      <div className="sticky top-0 z-10 bg-[var(--color-surface)] border-b border-[var(--color-border)] px-4 py-3">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/student')} className="flex items-center justify-center h-9 w-9 rounded-xl text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] transition-colors">
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
          </button>
          <div><h1 className="text-lg font-bold text-[var(--color-text-primary)]">My Attendance</h1></div>
        </div>
      </div>

      <div className="px-4 py-4 space-y-4">
        {/* Stats grid */}
        <div className="grid grid-cols-2 gap-3">
          <Card className="p-4 text-center">
            <p className={`text-3xl font-bold ${summary.percentage >= 90 ? 'text-emerald-500' : summary.percentage >= 75 ? 'text-amber-500' : 'text-rose-500'}`}>
              {summary.percentage}%
            </p>
            <p className="text-xs text-[var(--color-text-tertiary)] mt-1">Attendance Rate</p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-3xl font-bold text-[var(--color-brand-accent)]">{current_streak}</p>
            <p className="text-xs text-[var(--color-text-tertiary)] mt-1">Day Streak</p>
          </Card>
        </div>

        {/* Breakdown */}
        <Card className="p-4">
          <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">Breakdown</h3>
          <div className="space-y-3">
            {[
              { label: 'Present', count: summary.present, color: 'bg-emerald-500' },
              { label: 'Absent', count: summary.absent, color: 'bg-rose-500' },
              { label: 'Late', count: summary.late, color: 'bg-amber-500' },
              { label: 'Excused', count: summary.excused, color: 'bg-blue-500' },
            ].map((item) => {
              const pct = summary.total > 0 ? Math.round((item.count / summary.total) * 100) : 0
              return (
                <div key={item.label} className="flex items-center gap-3">
                  <span className={`h-2.5 w-2.5 rounded-full ${item.color} shrink-0`} />
                  <span className="text-sm text-[var(--color-text-secondary)] w-16">{item.label}</span>
                  <div className="flex-1 h-2 rounded-full bg-[var(--color-border)] overflow-hidden">
                    <div className={`h-full rounded-full ${item.color} transition-all duration-500`} style={{ width: `${pct}%` }} />
                  </div>
                  <span className="text-sm font-medium text-[var(--color-text-primary)] w-10 text-right">{item.count}</span>
                </div>
              )
            })}
          </div>
        </Card>

        {/* Monthly breakdown */}
        {monthly_breakdown.length > 0 && (
          <Card className="p-4">
            <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">Monthly Trend</h3>
            <div className="space-y-2">
              {monthly_breakdown.map((m) => (
                <div key={m.month} className="flex items-center gap-3">
                  <span className="text-xs text-[var(--color-text-secondary)] w-16">{m.month}</span>
                  <div className="flex-1 h-3 rounded-full bg-[var(--color-border)] overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        m.percentage >= 90 ? 'bg-emerald-500' : m.percentage >= 75 ? 'bg-amber-500' : 'bg-rose-500'
                      }`}
                      style={{ width: `${m.percentage}%` }}
                    />
                  </div>
                  <span className="text-xs font-medium text-[var(--color-text-primary)] w-10 text-right">{m.percentage}%</span>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Recent records */}
        <Card className="p-4">
          <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">Recent Records</h3>
          {records.length === 0 ? (
            <p className="text-sm text-[var(--color-text-tertiary)] text-center py-4">No records yet</p>
          ) : (
            <div className="space-y-1 max-h-80 overflow-y-auto">
              {records.map((r) => (
                <div key={r.id} className="flex items-center justify-between p-3 rounded-xl bg-[var(--color-bg)]">
                  <span className="text-sm text-[var(--color-text-primary)]">{formatDate(r.attendance_date)}</span>
                  <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${STATUS_BADGE[r.status] || ''}`}>
                    {r.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}

export default StudentAttendancePage
