import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { attendanceApi } from '../../api/attendance/attendance-api'
import type { AttendanceRecordResponse, SectionAttendanceSummary } from '../../api/generated/types'
import { Card, Input, Button, Badge, Loading, ErrorState } from '../../components/ui'
import { capitalize, ATTENDANCE_STATUSES } from '../../lib/utils'

const statusBadge: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
  present: 'success', absent: 'danger', late: 'warning', excused: 'info',
}

export function SectionAttendancePage() {
  const navigate = useNavigate()
  const [sectionId, setSectionId] = useState('')
  const [attendanceDate, setAttendanceDate] = useState(new Date().toISOString().split('T')[0])
  const [records, setRecords] = useState<AttendanceRecordResponse[]>([])
  const [summary, setSummary] = useState<SectionAttendanceSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleLoad = async () => {
    if (!sectionId || !attendanceDate) return
    setLoading(true); setError(null)
    try {
      const [sectionRecords, sectionSummary] = await Promise.all([
        attendanceApi.getSectionAttendance(Number(sectionId), attendanceDate),
        attendanceApi.getSectionSummary(Number(sectionId), attendanceDate),
      ])
      setRecords(sectionRecords)
      setSummary(sectionSummary)
    } catch (err: any) { setError(err?.detail || 'Failed to load section attendance') }
    finally { setLoading(false) }
  }

  return (
    <div className="space-y-6">
      <div>
        <button onClick={() => navigate('/attendance')} className="text-sm text-blue-600 hover:text-blue-800 mb-1">
          &larr; Back to Attendance
        </button>
        <h1 className="text-2xl font-bold text-gray-900">Section Attendance</h1>
      </div>

      <Card>
        <div className="flex gap-4 items-end">
          <Input label="Section ID" type="number" value={sectionId} onChange={(e) => setSectionId(e.target.value)} required />
          <Input label="Date" type="date" value={attendanceDate} onChange={(e) => setAttendanceDate(e.target.value)} required />
          <Button onClick={handleLoad} loading={loading}>Load</Button>
        </div>
      </Card>

      {error && <ErrorState message={error} />}

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <Card><div className="text-center"><p className="text-2xl font-bold">{summary.total_students}</p><p className="text-xs text-gray-500">Total</p></div></Card>
          <Card><div className="text-center"><p className="text-2xl font-bold text-green-600">{summary.present}</p><p className="text-xs text-gray-500">Present</p></div></Card>
          <Card><div className="text-center"><p className="text-2xl font-bold text-red-600">{summary.absent}</p><p className="text-xs text-gray-500">Absent</p></div></Card>
          <Card><div className="text-center"><p className="text-2xl font-bold text-yellow-600">{summary.late}</p><p className="text-xs text-gray-500">Late</p></div></Card>
          <Card><div className="text-center"><p className="text-2xl font-bold text-blue-600">{summary.total_marked}</p><p className="text-xs text-gray-500">Marked</p></div></Card>
        </div>
      )}

      {records.length > 0 && (
        <Card title={`Records for Section ${sectionId} on ${attendanceDate}`}>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left font-medium text-gray-500">Student ID</th>
                  <th className="px-4 py-2 text-left font-medium text-gray-500">Status</th>
                  <th className="px-4 py-2 text-left font-medium text-gray-500">Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {records.map((r) => (
                  <tr key={r.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2">{r.student_id}</td>
                    <td className="px-4 py-2"><Badge variant={statusBadge[r.status]}>{capitalize(r.status)}</Badge></td>
                    <td className="px-4 py-2">{r.notes || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {!loading && !error && sectionId && records.length === 0 && (
        <Card><p className="text-gray-500 text-center py-4">No attendance records found for this section and date.</p></Card>
      )}
    </div>
  )
}