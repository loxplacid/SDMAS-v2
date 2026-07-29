import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { attendanceApi, type AttendanceListParams } from '../../api/attendance/attendance-api'
import type { AttendanceRecordResponse } from '../../api/generated/types'
import { Card, Table, Pagination, Input, Select, Button, Badge, ErrorState, useToast } from '../../components/ui'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'
import { ATTENDANCE_STATUSES, capitalize, debounce, formatDate } from '../../lib/utils'

const statusBadge: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
  present: 'success',
  absent: 'danger',
  late: 'warning',
  excused: 'info',
}

const columns = [
  { key: 'id', header: 'ID', render: (r: AttendanceRecordResponse) => `#${r.id}` },
  { key: 'student_id', header: 'Student ID' },
  { key: 'attendance_date', header: 'Date', render: (r: AttendanceRecordResponse) => r.attendance_date },
  {
    key: 'status',
    header: 'Status',
    render: (r: AttendanceRecordResponse) => (
      <Badge variant={statusBadge[r.status] || 'default'}>{capitalize(r.status)}</Badge>
    ),
  },
  { key: 'section_id', header: 'Section' },
]

export function AttendanceRecordsPage() {
  const navigate = useNavigate()
  const { showToast } = useToast()
  const firstFilterRef = useRef<HTMLInputElement>(null)

  useKeyboardShortcut({
    '/': (e) => { e.preventDefault(); firstFilterRef.current?.focus(); },
    'n': () => navigate('/attendance/record'),
  }, [navigate])

  const [data, setData] = useState<AttendanceRecordResponse[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(0)
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(20)
  const [statusFilter, setStatusFilter] = useState('')
  const [dateFilter, setDateFilter] = useState('')
  const [studentIdFilter, setStudentIdFilter] = useState('')
  const [sectionIdFilter, setSectionIdFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchIdRef = useRef(0)

  const fetch = useCallback(async (params: AttendanceListParams) => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)
    try {
      const result = await attendanceApi.list(params)
      if (fetchId === fetchIdRef.current) {
        setData(result.items); setTotal(result.total); setPages(result.pages); setPage(result.page)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load attendance records')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const params: AttendanceListParams = { page, size }
    if (statusFilter) params.status = statusFilter
    if (dateFilter) params.attendance_date = dateFilter
    if (studentIdFilter) params.student_id = Number(studentIdFilter)
    if (sectionIdFilter) params.section_id = Number(sectionIdFilter)
    fetch(params)
  }, [page, size, statusFilter, dateFilter, studentIdFilter, sectionIdFilter, fetch])

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-[var(--color-brand-accent)] tracking-wide mb-1">Attendance</p>
          <h1 className="text-2xl font-bold text-[var(--color-text-primary)] tracking-tight">Attendance Records</h1>
          <p className="text-sm text-[var(--color-text-tertiary)] mt-1">{total} record{total !== 1 ? 's' : ''}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate('/attendance/daily')}>
            Daily Attendance
          </Button>
          <Button onClick={() => navigate('/attendance/record')}>
            Record Attendance
            <kbd className="ml-2 hidden sm:inline-flex items-center px-1.5 py-0.5 rounded bg-white/20 text-[10px] font-medium text-white/80">N</kbd>
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <Input
          ref={firstFilterRef}
          placeholder="Student ID"
          type="number"
          value={studentIdFilter}
          onChange={(e) => { setStudentIdFilter(e.target.value); setPage(1) }}
          className="w-32"
        />
        <Input
          placeholder="Section ID"
          type="number"
          value={sectionIdFilter}
          onChange={(e) => { setSectionIdFilter(e.target.value); setPage(1) }}
          className="w-32"
        />
        <Input
          type="date"
          value={dateFilter}
          onChange={(e) => { setDateFilter(e.target.value); setPage(1) }}
          className="w-40"
        />
        <Select
          options={ATTENDANCE_STATUSES.map((s) => ({ value: s, label: capitalize(s) }))}
          placeholder="All statuses"
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
        />
      </div>

      <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
        {error ? <ErrorState message={error} onRetry={() => fetch({ page, size })} /> : (
          <>
            <Table
              columns={[
                ...columns,
                {
                  key: 'actions', header: 'Actions',
                  render: (r: AttendanceRecordResponse) => (
                    <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                      <Button variant="ghost" size="sm" onClick={() => navigate(`/attendance/records/${r.id}`)}>View</Button>
                    </div>
                  ),
                },
              ]}
              data={data}
              keyExtractor={(r) => r.id}
              emptyMessage="No attendance records found."
              onRowClick={(r) => navigate(`/attendance/records/${r.id}`)}
              loading={loading}
            />
            <Pagination page={page} size={size} total={total} pages={pages} onPageChange={setPage} onSizeChange={(s) => { setSize(s); setPage(1) }} />
          </>
        )}
      </Card>
    </div>
  )
}