import { useCallback, useEffect, useRef, useState } from 'react'
import { attendanceApi } from '../../api/attendance/attendance-api'
import { HubPage, HubSectionHeading } from '../../components/ui/hub-page'
import { Badge, Skeleton } from '../../components/ui'
import { capitalize, formatDateTime, plural } from '../../lib/utils'

const attendanceLinks = [
  { label: 'All Records', description: 'View and search attendance records', route: '/attendance/records', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01' },
  { label: 'Daily Attendance', description: 'Record attendance for a section by date', route: '/attendance/daily', icon: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z' },
  { label: 'Individual Record', description: 'Record attendance for individual students', route: '/attendance/record', icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z' },
  { label: 'Student Attendance', description: 'View attendance by student', route: '/attendance/student', icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z' },
  { label: 'Section Attendance', description: 'View attendance summary by section', route: '/attendance/section', icon: 'M4 6h16M4 10h16M4 14h16M4 18h16' },
  { label: 'Intelligence Hub', description: 'Period tracking, corrections, thresholds', route: '/attendance-intelligence', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
]

const statusColors: Record<string, 'success' | 'danger' | 'warning' | 'info'> = {
  present: 'success',
  absent: 'danger',
  late: 'warning',
  excused: 'info',
}

export function AttendancePage() {
  const [totalCount, setTotalCount] = useState(0)
  const [recentRecords, setRecentRecords] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const fetchIdRef = useRef(0)

  const load = useCallback(async () => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    try {
      const [totalRes, recentRes] = await Promise.all([
        attendanceApi.list({ page: 1, size: 1 }),
        attendanceApi.list({ page: 1, size: 8 }),
      ])
      if (fetchId !== fetchIdRef.current) return
      setTotalCount(totalRes.total)
      setRecentRecords(recentRes.items)
    } catch {
      // Silent
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    return () => { fetchIdRef.current++ }
  }, [load])

  const stats = [
    { label: 'Total Records', value: totalCount, route: '/attendance/records' },
  ]

  const recentSection = (
    <div>
      <HubSectionHeading title="Recent Records" subtitle={plural(totalCount, 'record total')} />
      <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
        {loading ? (
          <div className="p-4 space-y-3">
            {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-10 w-full" />)}
          </div>
        ) : recentRecords.length === 0 ? (
          <div className="p-6 text-center">
            <p className="text-xs text-[var(--color-text-tertiary)]">No attendance records yet.</p>
          </div>
        ) : (
          <table className="min-w-full">
            <thead>
              <tr className="border-b border-[var(--color-divider)]">
                <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">Student</th>
                <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">Status</th>
                <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">Section</th>
                <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-divider)]">
              {recentRecords.map((r: any) => (
                <tr key={r.id} className="hover:bg-[var(--color-surface-hover)] motion-safe:transition-colors">
                  <td className="px-4 py-2.5 text-sm font-medium text-[var(--color-text-primary)]">
                    Student #{r.student_id}
                  </td>
                  <td className="px-4 py-2.5">
                    <Badge variant={statusColors[r.status] || 'neutral'} size="sm" dot>
                      {capitalize(r.status)}
                    </Badge>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-[var(--color-text-secondary)]">
                    {r.section_id ? `Section #${r.section_id}` : '-'}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-[var(--color-text-tertiary)]">
                    {formatDateTime(r.attendance_date)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )

  return (
    <HubPage
      eyebrow="Operations"
      title="Attendance"
      subtitle="Manage attendance records and daily tracking"
      stats={stats}
      links={attendanceLinks}
      recentContent={recentSection}
      loading={loading}
    />
  )
}

export default AttendancePage
