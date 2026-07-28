import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../api/auth/auth-context'
import { analyticsApi } from '../api/analytics/analytics-api'
import { attendanceAnalyticsApi } from '../api/analytics/attendance-analytics-api'
import type { AnalyticsOverview, AttendanceOverview } from '../api/analytics/types'
import { Card, Loading, ErrorState } from '../components/ui'
import { KpiCard } from '../components/analytics/kpi-card'
import { AttendanceStatusChart } from '../components/analytics/attendance-status-chart'
import { formatCurrency } from '../lib/utils'

export function DashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const [overview, setOverview] = useState<AnalyticsOverview | null>(null)
  const [attendanceOverview, setAttendanceOverview] = useState<AttendanceOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  useEffect(() => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)

    Promise.all([
      analyticsApi.getOverview(),
      attendanceAnalyticsApi.getOverview().catch(() => null),
    ]).then(([ov, att]) => {
      if (fetchId === fetchIdRef.current) {
        setOverview(ov)
        setAttendanceOverview(att)
      }
    }).catch((err: any) => {
      if (fetchId === fetchIdRef.current) {
        setError(err?.detail || 'Failed to load dashboard')
      }
    }).finally(() => {
      if (fetchId === fetchIdRef.current) setLoading(false)
    })
  }, [])

  const quickLinks = [
    { label: 'Manage Students', path: '/students', icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z', color: 'blue' },
    { label: 'Academic Management', path: '/academic', icon: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4', color: 'green' },
    { label: 'Record Attendance', path: '/attendance/record', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01', color: 'purple' },
    { label: 'Fee Management', path: '/fees', icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z', color: 'yellow' },
    { label: 'View Reports', path: '/reports', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z', color: 'indigo' },
    { label: 'Analytics', path: '/analytics', icon: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6', color: 'red' },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Executive Dashboard</h1>
        <p className="text-gray-500 mt-1">
          Welcome back, {user?.display_name || user?.username}
          {overview?.current_academic_year && (
            <span> — Current Academic Year: <strong className="text-blue-600">{overview.current_academic_year}</strong></span>
          )}
        </p>
      </div>

      {error && <ErrorState message={error} onRetry={() => window.location.reload()} />}

      {loading ? (
        <Loading text="Loading dashboard..." />
      ) : overview ? (
        <>
          {/* Key Performance Indicators */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <KpiCard title="Total Students" value={overview.total_students} subtitle={`${overview.active_students} active`} color="blue" />
            <KpiCard title="Classes" value={overview.total_classes} color="green" />
            <KpiCard title="Sections" value={overview.total_sections} color="purple" />
            <KpiCard title="Teachers" value={overview.total_teachers} color="indigo" />
            <KpiCard title="Subjects" value={overview.total_subjects} color="yellow" />
            <KpiCard title="Attendance" value={`${overview.overall_attendance_percentage}%`} color="purple" />
          </div>

          {/* Financial KPIs */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <KpiCard title="Total Collected" value={formatCurrency(overview.total_collected)} color="green" />
            <KpiCard title="Outstanding" value={formatCurrency(overview.total_outstanding)} color="red" />
            <KpiCard title="Collection Rate" value={`${overview.collection_percentage}%`} color="purple" />
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-yellow-700">Unpaid Fees</p>
                <p className="text-lg font-bold text-yellow-800">{overview.unpaid_count} students</p>
              </div>
            </div>
          </div>

          {/* Charts and Alerts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Attendance Status */}
            <Card title="Attendance Overview">
              {attendanceOverview && attendanceOverview.total_records > 0 ? (
                <div className="space-y-3">
                  <AttendanceStatusChart data={attendanceOverview} loading={false} />
                  <div className="grid grid-cols-4 gap-2 text-center">
                    <div className="bg-green-50 p-2 rounded">
                      <p className="text-lg font-bold text-green-600">{attendanceOverview.present}</p>
                      <p className="text-xs text-gray-500">Present</p>
                    </div>
                    <div className="bg-red-50 p-2 rounded">
                      <p className="text-lg font-bold text-red-600">{attendanceOverview.absent}</p>
                      <p className="text-xs text-gray-500">Absent</p>
                    </div>
                    <div className="bg-yellow-50 p-2 rounded">
                      <p className="text-lg font-bold text-yellow-600">{attendanceOverview.late}</p>
                      <p className="text-xs text-gray-500">Late</p>
                    </div>
                    <div className="bg-purple-50 p-2 rounded">
                      <p className="text-lg font-bold text-purple-600">{attendanceOverview.excused}</p>
                      <p className="text-xs text-gray-500">Excused</p>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-gray-400 text-sm text-center py-8">No attendance data available.</p>
              )}
            </Card>

            {/* Alerts */}
            <Card title="Attention Areas">
              <div className="space-y-3">
                {overview.low_attendance_count > 0 ? (
                  <div className="flex items-center justify-between p-3 bg-red-50 rounded-lg border border-red-200">
                    <div>
                      <p className="text-sm font-medium text-red-800">Low Attendance</p>
                      <p className="text-xs text-red-600">{overview.low_attendance_count} students below 90% threshold</p>
                    </div>
                    <span className="text-2xl font-bold text-red-600">{overview.low_attendance_count}</span>
                  </div>
                ) : (
                  <div className="flex items-center justify-between p-3 bg-green-50 rounded-lg border border-green-200">
                    <div>
                      <p className="text-sm font-medium text-green-800">Attendance</p>
                      <p className="text-xs text-green-600">All students meet attendance threshold</p>
                    </div>
                    <svg className="w-6 h-6 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                )}

                {overview.unpaid_count > 0 && (
                  <div className="flex items-center justify-between p-3 bg-yellow-50 rounded-lg border border-yellow-200">
                    <div>
                      <p className="text-sm font-medium text-yellow-800">Unpaid Fees</p>
                      <p className="text-xs text-yellow-600">{overview.unpaid_count} students have unpaid fees</p>
                    </div>
                    <span className="text-2xl font-bold text-yellow-600">{overview.unpaid_count}</span>
                  </div>
                )}

                {overview.partially_paid_count > 0 && (
                  <div className="flex items-center justify-between p-3 bg-blue-50 rounded-lg border border-blue-200">
                    <div>
                      <p className="text-sm font-medium text-blue-800">Partially Paid</p>
                      <p className="text-xs text-blue-600">{overview.partially_paid_count} students with partial payments</p>
                    </div>
                    <span className="text-2xl font-bold text-blue-600">{overview.partially_paid_count}</span>
                  </div>
                )}

                {overview.active_students > 0 && (
                  <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200">
                    <div>
                      <p className="text-sm font-medium text-gray-800">Active Students</p>
                      <p className="text-xs text-gray-600">{overview.inactive_students} inactive of {overview.total_students} total</p>
                    </div>
                    <span className="text-2xl font-bold text-gray-600">{overview.active_students}</span>
                  </div>
                )}
              </div>
            </Card>
          </div>

          {/* Quick Actions */}
          <Card title="Quick Actions">
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              {quickLinks.map((link) => (
                <button
                  key={link.path}
                  onClick={() => navigate(link.path)}
                  className="flex flex-col items-center gap-2 p-3 rounded-lg border border-gray-200 hover:border-blue-300 hover:bg-blue-50 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <svg className={`w-6 h-6 text-${link.color}-600`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={link.icon} />
                  </svg>
                  <span className="text-xs text-gray-700 text-center">{link.label}</span>
                </button>
              ))}
            </div>
          </Card>
        </>
      ) : (
        <Card>
          <p className="text-gray-500 text-center py-8">Unable to load dashboard data. Check your connection and try again.</p>
        </Card>
      )}
    </div>
  )
}
