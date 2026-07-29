import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { attendanceApi } from '../../api/attendance/attendance-api'
import type { AttendanceRecordResponse, StudentAttendanceSummary } from '../../api/generated/types'
import { Card, Table, Pagination, Badge, Button, Input, Select, ErrorState } from '../../components/ui'
import { ATTENDANCE_STATUSES, capitalize } from '../../lib/utils'

const statusBadge: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
  present: 'success',
  absent: 'danger',
  late: 'warning',
  excused: 'info',
}

export function StudentAttendancePage() {
  const { studentId } = useParams<{ studentId: string }>()
  const navigate = useNavigate()
  const sid = Number(studentId)

  const [records, setRecords] = useState<AttendanceRecordResponse[]>([])
  const [summary, setSummary] = useState<StudentAttendanceSummary | null>(null)
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(0)
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(20)
  const [statusFilter, setStatusFilter] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate] = useState(new Date().toISOString().split('T')[0])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [summaryLoading, setSummaryLoading] = useState(false)

  useEffect(() => {
    if (!sid) return
    setLoading(true)
    setError(null)
    attendanceApi.getStudentAttendance(sid, {
      page, size,
      status: statusFilter || undefined,
      start_date: startDate || undefined,
      end_date: endDate || undefined,
    })
      .then((result) => { setRecords(result.items); setTotal(result.total); setPages(result.pages); setPage(result.page) })
      .catch((err) => setError(err?.detail || 'Failed to load records'))
      .finally(() => setLoading(false))
  }, [sid, page, size, statusFilter, startDate])

  useEffect(() => {
    if (!sid || !startDate || !endDate) return
    setSummaryLoading(true)
    attendanceApi.getStudentSummary(sid, startDate, endDate)
      .then(setSummary)
      .catch(() => {})
      .finally(() => setSummaryLoading(false))
  }, [sid, startDate, endDate])

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <button onClick={() => navigate('/attendance/records')} className="text-sm text-[var(--color-brand-accent)] hover:text-[var(--color-brand-accent-hover)] transition-colors mb-1">
          &larr; Back to Records
        </button>
        <div className="text-[var(--color-brand-accent)] text-xs font-semibold uppercase tracking-wider mt-1">Attendance</div>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)] mt-1">Student Attendance</h1>
        <p className="text-sm text-[var(--color-text-tertiary)] mt-1">Student ID: {sid}</p>
      </div>

      <div className="flex flex-wrap gap-4 items-end">
        <Input
          label="Start Date"
          type="date"
          value={startDate}
          onChange={(e) => { setStartDate(e.target.value); setPage(1) }}
        />
        <Input
          label="End Date"
          type="date"
          value={endDate}
          disabled
        />
        <Select
          label="Status"
          options={ATTENDANCE_STATUSES.map((s) => ({ value: s, label: capitalize(s) }))}
          placeholder="All statuses"
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
        />
      </div>

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none"><div className="text-center"><p className="text-2xl font-bold text-[var(--color-text-primary)]">{summary.total}</p><p className="text-xs text-[var(--color-text-tertiary)]">Total</p></div></Card>
          <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none"><div className="text-center"><p className="text-2xl font-bold text-green-600">{summary.present}</p><p className="text-xs text-[var(--color-text-tertiary)]">Present</p></div></Card>
          <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none"><div className="text-center"><p className="text-2xl font-bold text-red-600">{summary.absent}</p><p className="text-xs text-[var(--color-text-tertiary)]">Absent</p></div></Card>
          <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none"><div className="text-center"><p className="text-2xl font-bold text-yellow-600">{summary.late}</p><p className="text-xs text-[var(--color-text-tertiary)]">Late</p></div></Card>
          <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none"><div className="text-center"><p className="text-2xl font-bold text-blue-600">{summary.excused}</p><p className="text-xs text-[var(--color-text-tertiary)]">Excused</p></div></Card>
        </div>
      )}

      <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
        {loading ? <Table columns={[]} data={[]} loading={true} keyExtractor={() => ''} emptyMessage="" /> : error ? <ErrorState message={error} /> : (
          <>
            <Table
              columns={[
                { key: 'attendance_date', header: 'Date' },
                {
                  key: 'status',
                  header: 'Status',
                  render: (r: AttendanceRecordResponse) => (
                    <Badge variant={statusBadge[r.status]}>{capitalize(r.status)}</Badge>
                  ),
                },
                { key: 'notes', header: 'Notes', render: (r: AttendanceRecordResponse) => r.notes || '-' },
              ]}
              data={records}
              keyExtractor={(r) => r.id}
              emptyMessage="No attendance records for this student."
            />
            <Pagination page={page} size={size} total={total} pages={pages} onPageChange={setPage} onSizeChange={(s) => { setSize(s); setPage(1) }} />
          </>
        )}
      </Card>
    </div>
  )
}