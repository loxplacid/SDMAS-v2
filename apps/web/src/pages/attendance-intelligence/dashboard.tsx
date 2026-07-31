import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { attendanceIntelligenceApi, type AttendanceIntelligenceDashboard, type ChronicAbsenteeismRecord, type LowAttendanceAlertItem } from '../../api/attendance-intelligence/attendance-intelligence-api'
import { Card, PageHeader, Loading, ErrorState, Badge, Table } from '../../components/ui'
import { capitalize } from '../../lib/utils'

export function AttendanceIntelligenceDashboardPage() {
  const navigate = useNavigate()
  const [dashboard, setDashboard] = useState<AttendanceIntelligenceDashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  const fetchData = useCallback(async () => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)
    try {
      const data = await attendanceIntelligenceApi.getDashboard()
      if (fetchId === fetchIdRef.current) setDashboard(data)
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load dashboard')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  if (loading) return <Loading text="Loading intelligence dashboard..." />
  if (error) return <ErrorState message={error} onRetry={fetchData} />
  if (!dashboard) return null

  const kpiCards = [
    { label: 'Overall Attendance', value: `${dashboard.overall_attendance_percentage}%`, color: 'from-blue-500 to-blue-600' },
    { label: 'Present Today', value: dashboard.present_today, color: 'from-emerald-500 to-emerald-600' },
    { label: 'Absent Today', value: dashboard.absent_today, color: 'from-red-500 to-red-600' },
    { label: 'Late Today', value: dashboard.late_today, color: 'from-amber-500 to-amber-600' },
    { label: 'Chronic Cases', value: dashboard.chronic_count, color: 'from-rose-500 to-rose-600' },
    { label: 'Total Students', value: dashboard.total_students, color: 'from-indigo-500 to-indigo-600' },
  ]

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        title="Attendance Intelligence Dashboard"
        subtitle="Real-time attendance KPIs, chronic absenteeism, and alerts"
        actions={
          <div className="flex gap-2">
            <button className="px-3 py-1.5 text-sm rounded-lg bg-[var(--color-surface-hover)] hover:bg-[var(--color-surface-active)] transition-colors" onClick={() => navigate('/attendance-intelligence')}>Hub</button>
            <button className="px-3 py-1.5 text-sm rounded-lg bg-[var(--color-surface-hover)] hover:bg-[var(--color-surface-active)] transition-colors" onClick={() => navigate('/attendance-intelligence/period')}>Period Attendance</button>
          </div>
        }
      />

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        {kpiCards.map((kpi) => (
          <Card key={kpi.label} className="text-center">
            <p className="text-xs font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider">{kpi.label}</p>
            <p className={`text-2xl font-bold mt-1 bg-gradient-to-br ${kpi.color} bg-clip-text text-transparent`}>{kpi.value}</p>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Low Attendance Alerts">
          {dashboard.low_attendance_alerts.length === 0 ? (
            <p className="text-sm text-[var(--color-text-tertiary)] py-4 text-center">No alerts</p>
          ) : (
            <div className="space-y-2">
              {dashboard.low_attendance_alerts.map((alert, i) => (
                <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-[var(--color-surface-hover)]">
                  <div>
                    <p className="text-sm font-medium">Student #{alert.student_id}</p>
                    <p className="text-xs text-[var(--color-text-tertiary)]">{alert.threshold_name}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold text-red-500">{alert.attendance_percentage}%</p>
                    <p className="text-xs text-[var(--color-text-tertiary)]">{alert.total_absences} absences</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Chronic Absenteeism">
          {dashboard.top_absenteeism.length === 0 ? (
            <p className="text-sm text-[var(--color-text-tertiary)] py-4 text-center">No chronic cases</p>
          ) : (
            <div className="space-y-2">
              {dashboard.top_absenteeism.map((item, i) => (
                <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-[var(--color-surface-hover)]">
                  <div>
                    <p className="text-sm font-medium">Student #{item.student_id}</p>
                    <p className="text-xs text-[var(--color-text-tertiary)]">{item.consecutive_absences} consecutive absences</p>
                  </div>
                  <Badge variant={item.attendance_percentage < 50 ? 'danger' : 'warning'}>{item.attendance_percentage}%</Badge>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}

export default AttendanceIntelligenceDashboardPage
