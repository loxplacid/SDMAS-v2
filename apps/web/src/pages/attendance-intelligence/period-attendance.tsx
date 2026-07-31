import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { attendanceIntelligenceApi, type PeriodAttendanceResponse, type AttendanceIntelligenceListParams } from '../../api/attendance-intelligence/attendance-intelligence-api'
import { Card, Table, PageHeader, Input, Select, Button, Badge, Pagination, Loading, ErrorState } from '../../components/ui'
import { capitalize, formatDate } from '../../lib/utils'

const statusBadge: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
  present: 'success', absent: 'danger', late: 'warning', excused: 'info',
}

const columns = [
  { key: 'id', header: 'ID', render: (r: PeriodAttendanceResponse) => `#${r.id}` },
  { key: 'attendance_date', header: 'Date', render: (r: PeriodAttendanceResponse) => r.attendance_date },
  { key: 'period_number', header: 'Period' },
  { key: 'start_time', header: 'Start' },
  { key: 'end_time', header: 'End' },
  { key: 'section_id', header: 'Section' },
  { key: 'subject_id', header: 'Subject' },
  { key: 'status', header: 'Status', render: (r: PeriodAttendanceResponse) => <Badge variant={statusBadge[r.status] || 'default'}>{capitalize(r.status)}</Badge> },
  {
    key: 'records',
    header: 'Records',
    render: (r: PeriodAttendanceResponse) => <span className="text-sm text-[var(--color-text-tertiary)]">{r.records?.length || 0} student(s)</span>,
  },
]

export function PeriodAttendancePage() {
  const navigate = useNavigate()
  const [data, setData] = useState<PeriodAttendanceResponse[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(20)
  const [sectionFilter, setSectionFilter] = useState('')
  const [dateFilter, setDateFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  const fetch = useCallback(async (params: AttendanceIntelligenceListParams) => {
    const fetchId = ++fetchIdRef.current
    setLoading(true); setError(null)
    try {
      const result = await attendanceIntelligenceApi.listPeriodAttendance(params)
      if (fetchId === fetchIdRef.current) { setData(result.items); setTotal(result.total); setPage(result.page); setSize(result.size) }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load')
    } finally { if (fetchId === fetchIdRef.current) setLoading(false) }
  }, [])

  useEffect(() => {
    const params: AttendanceIntelligenceListParams = { page, size }
    if (sectionFilter) params.section_id = Number(sectionFilter)
    if (dateFilter) params.from_date = dateFilter
    fetch(params)
  }, [page, size, sectionFilter, dateFilter, fetch])

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        title="Period Attendance"
        subtitle="Per-period attendance tracking with late arrival and early departure"
        actions={
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => navigate('/attendance-intelligence')}>Hub</Button>
            <Button onClick={() => navigate('/attendance/daily')}>Daily Attendance</Button>
          </div>
        }
      />

      <Card>
        <div className="flex flex-wrap gap-4 mb-4">
          <Input placeholder="Section ID..." value={sectionFilter} onChange={(e) => { setSectionFilter(e.target.value); setPage(1) }} className="w-40" />
          <Input type="date" value={dateFilter} onChange={(e) => { setDateFilter(e.target.value); setPage(1) }} className="w-44" />
        </div>

        {error && <ErrorState message={error} />}
        {loading ? <Loading /> : (
          <>
            <Table data={data} columns={columns} keyExtractor={(r) => r.id} onRowClick={(r) => navigate(`/attendance-intelligence/period/${r.id}`)} />
            <Pagination page={page} size={size} total={total} pages={Math.ceil(total / size)} onPageChange={setPage} onSizeChange={setSize} />
          </>
        )}
      </Card>
    </div>
  )
}

export default PeriodAttendancePage
