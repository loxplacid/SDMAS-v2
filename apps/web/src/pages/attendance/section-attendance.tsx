import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { attendanceApi } from '../../api/attendance/attendance-api'
import type { AttendanceRecordResponse, SectionAttendanceSummary } from '../../api/generated/types'
import { Card, Input, Button, Badge, ErrorState, Table } from '../../components/ui'
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
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <button onClick={() => navigate('/attendance')} className="text-sm text-[var(--color-brand-accent)] hover:text-[var(--color-brand-accent-hover)] transition-colors mb-1">
          &larr; Back to Attendance
        </button>
        <div className="text-[var(--color-brand-accent)] text-xs font-semibold uppercase tracking-wider mt-1">Attendance</div>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)] mt-1">Section Attendance</h1>
      </div>

      <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
        <div className="flex gap-4 items-end">
          <Input label="Section ID" type="number" value={sectionId} onChange={(e) => setSectionId(e.target.value)} required />
          <Input label="Date" type="date" value={attendanceDate} onChange={(e) => setAttendanceDate(e.target.value)} required />
          <Button onClick={handleLoad} loading={loading}>Load</Button>
        </div>
      </Card>

      {error && <ErrorState message={error} />}

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none"><div className="text-center"><p className="text-2xl font-bold text-[var(--color-text-primary)]">{summary.total_students}</p><p className="text-xs text-[var(--color-text-tertiary)]">Total</p></div></Card>
          <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none"><div className="text-center"><p className="text-2xl font-bold text-green-600">{summary.present}</p><p className="text-xs text-[var(--color-text-tertiary)]">Present</p></div></Card>
          <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none"><div className="text-center"><p className="text-2xl font-bold text-red-600">{summary.absent}</p><p className="text-xs text-[var(--color-text-tertiary)]">Absent</p></div></Card>
          <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none"><div className="text-center"><p className="text-2xl font-bold text-yellow-600">{summary.late}</p><p className="text-xs text-[var(--color-text-tertiary)]">Late</p></div></Card>
          <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none"><div className="text-center"><p className="text-2xl font-bold text-blue-600">{summary.total_marked}</p><p className="text-xs text-[var(--color-text-tertiary)]">Marked</p></div></Card>
        </div>
      )}

      {records.length > 0 && (
        <Card title={`Records for Section ${sectionId} on ${attendanceDate}`} className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
          <Table
            columns={[
              { key: 'student_id', header: 'Student ID' },
              { key: 'status', header: 'Status', render: (r: AttendanceRecordResponse) => <Badge variant={statusBadge[r.status]}>{capitalize(r.status)}</Badge> },
              { key: 'notes', header: 'Notes', render: (r: AttendanceRecordResponse) => r.notes || '-' },
            ]}
            data={records}
            keyExtractor={(r: AttendanceRecordResponse) => r.id}
          />
        </Card>
      )}

      {!loading && !error && sectionId && records.length === 0 && (
        <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none"><p className="text-[var(--color-text-tertiary)] text-center py-4">No attendance records found for this section and date.</p></Card>
      )}
    </div>
  )
}