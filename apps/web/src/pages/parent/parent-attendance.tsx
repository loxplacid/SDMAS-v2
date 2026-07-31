import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { parentApi } from '../../api/parent/parent-api'
import type { LinkedChild, ParentAttendanceResponse } from '../../api/parent/parent-api'
import { Loading, ErrorState, EmptyState, Card } from '../../components/ui'
import { useParentChildren } from '../../hooks/use-parent-children'
import { formatDate } from '../../lib/utils'

const STATUS_COLORS: Record<string, string> = {
  present: 'bg-emerald-500',
  absent: 'bg-rose-500',
  late: 'bg-amber-500',
  excused: 'bg-blue-500',
}

const STATUS_LABELS: Record<string, string> = {
  present: 'Present',
  absent: 'Absent',
  late: 'Late',
  excused: 'Excused',
}

export function ParentAttendancePage() {
  const navigate = useNavigate()
  const { linkedIds } = useParentChildren()
  const [children, setChildren] = useState<LinkedChild[]>([])
  const [selectedChildId, setSelectedChildId] = useState<number | null>(null)
  const [attendanceData, setAttendanceData] = useState<ParentAttendanceResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (linkedIds.length === 0) {
      setLoading(false)
      return
    }
    parentApi.listChildren()
      .then((kids) => {
        setChildren(kids)
        if (kids.length > 0) {
          setSelectedChildId(kids[0].id)
        }
      })
      .catch((err: any) => setError(err?.detail || 'Failed to load children'))
      .finally(() => setLoading(false))
  }, [linkedIds])

  useEffect(() => {
    if (!selectedChildId) return
    setLoading(true)
    parentApi.getChildAttendance(selectedChildId, 90)
      .then(setAttendanceData)
      .catch((err: any) => setError(err?.detail || 'Failed to load attendance'))
      .finally(() => setLoading(false))
  }, [selectedChildId])

  if (loading) return <Loading text="Loading attendance..." />
  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />
  if (children.length === 0) {
    return (
      <EmptyState
        title="No children linked"
        description="Link your children first to see their attendance."
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
            <h1 className="text-lg font-bold text-[var(--color-text-primary)]">Attendance</h1>
            <p className="text-xs text-[var(--color-text-tertiary)]">Track your child's attendance</p>
          </div>
        </div>
      </div>

      {/* Child selector — mobile-friendly tabs */}
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

      {attendanceData && (
        <div className="px-4 space-y-4">
          {/* Summary cards */}
          <div className="grid grid-cols-2 gap-3">
            <Card className="p-4 text-center">
              <p className="text-3xl font-bold text-[var(--color-brand-accent)]">
                {attendanceData.summary.percentage}%
              </p>
              <p className="text-xs text-[var(--color-text-tertiary)] mt-1">Attendance Rate</p>
            </Card>
            <Card className="p-4 text-center">
              <p className="text-3xl font-bold text-[var(--color-text-primary)]">
                {attendanceData.current_streak}
              </p>
              <p className="text-xs text-[var(--color-text-tertiary)] mt-1">Day Streak</p>
            </Card>
          </div>

          {/* Stats breakdown */}
          <Card className="p-4">
            <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">Breakdown</h3>
            <div className="space-y-3">
              {['present', 'absent', 'late', 'excused'].map((status) => {
                const count = (attendanceData.summary as any)[status] as number
                const total = attendanceData.summary.total
                const pct = total > 0 ? Math.round((count / total) * 100) : 0
                return (
                  <div key={status} className="flex items-center gap-3">
                    <span className={`h-2.5 w-2.5 rounded-full ${STATUS_COLORS[status]} shrink-0`} />
                    <span className="text-sm text-[var(--color-text-secondary)] w-20">{STATUS_LABELS[status]}</span>
                    <div className="flex-1 h-2 rounded-full bg-[var(--color-border)] overflow-hidden">
                      <div
                        className={`h-full rounded-full ${STATUS_COLORS[status]} transition-all duration-500`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="text-sm font-medium text-[var(--color-text-primary)] w-12 text-right">{count}</span>
                  </div>
                )
              })}
            </div>
          </Card>

          {/* Recent records */}
          <Card className="p-4">
            <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">Recent Records</h3>
            {attendanceData.records.length === 0 ? (
              <p className="text-sm text-[var(--color-text-tertiary)] text-center py-4">No attendance records yet</p>
            ) : (
              <div className="space-y-1">
                {attendanceData.records.map((record) => (
                  <div
                    key={record.id}
                    className="flex items-center justify-between p-3 rounded-xl bg-[var(--color-bg)]"
                  >
                    <span className="text-sm text-[var(--color-text-primary)]">
                      {formatDate(record.attendance_date)}
                    </span>
                    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${
                      record.status === 'present' ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' :
                      record.status === 'absent' ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400' :
                      record.status === 'late' ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400' :
                      'bg-blue-500/10 text-blue-600 dark:text-blue-400'
                    }`}>
                      {STATUS_LABELS[record.status] || record.status}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Days since last absence */}
          {attendanceData.days_since_last_absence > 0 && (
            <Card className="p-4 bg-gradient-to-br from-emerald-50 to-emerald-100 dark:from-emerald-900/20 dark:to-emerald-800/20 border-emerald-200 dark:border-emerald-800">
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center h-10 w-10 rounded-xl bg-emerald-500/10">
                  <svg className="h-5 w-5 text-emerald-600 dark:text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-semibold text-emerald-800 dark:text-emerald-200">
                    {attendanceData.days_since_last_absence} day{attendanceData.days_since_last_absence !== 1 ? 's' : ''} since last absence
                  </p>
                  <p className="text-xs text-emerald-600 dark:text-emerald-400">Keep it up!</p>
                </div>
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}

export default ParentAttendancePage
