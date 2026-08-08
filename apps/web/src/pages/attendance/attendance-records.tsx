import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { attendanceApi, type AttendanceListParams } from '../../api/attendance/attendance-api'
import { exportApi } from '../../api/reports/export-api'
import type { AttendanceRecordResponse } from '../../api/generated/types'
import { Button, Badge, useToast } from '../../components/ui'
import type { Column } from '../../components/ui/table'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'
import { DataWorkspace, useWorkspace } from '../../components/data-workspace'
import { capitalize } from '../../lib/utils'

const statusBadge: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
  present: 'success',
  absent: 'danger',
  late: 'warning',
  excused: 'info',
}

export function AttendanceRecordsPage() {
  const navigate = useNavigate()
  const { showToast } = useToast()
  const searchInputRef = useRef<HTMLInputElement>(null)

  // ── keyboard: `/` focuses the rail search, `n` records attendance ──
  useKeyboardShortcut({
    '/': (e) => {
      e.preventDefault()
      searchInputRef.current?.focus()
    },
    n: () => navigate('/attendance/record'),
  }, [navigate])

  // Columns live inside the component: the actions column binds `navigate`.
  const columns = useMemo<Column<AttendanceRecordResponse>[]>(
    () => [
      { key: 'id', header: 'ID', type: 'numeric', render: (r) => `#${r.id}` },
      { key: 'student_id', header: 'Student ID', type: 'numeric' },
      { key: 'attendance_date', header: 'Date', type: 'date', render: (r) => r.attendance_date },
      {
        key: 'status',
        header: 'Status',
        type: 'status',
        render: (r) => <Badge variant={statusBadge[r.status] || 'neutral'}>{capitalize(r.status)}</Badge>,
      },
      { key: 'section_id', header: 'Section', type: 'numeric', render: (r) => r.section_id ?? '-' },
      {
        key: 'actions',
        header: '',
        type: 'actions',
        render: (r) => (
          <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
            <Button variant="ghost" size="sm" onClick={() => navigate(`/attendance/records/${r.id}`)}>
              View
            </Button>
          </div>
        ),
      },
    ],
    [navigate]
  )

  const workspace = useWorkspace<AttendanceRecordResponse>({
    viewKey: 'attendance-records',
    columns,
    defaultPageSize: 20,
  })

  const [data, setData] = useState<AttendanceRecordResponse[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchIdRef = useRef(0)

  const fetch = useCallback(async (params: AttendanceListParams, showLoading: boolean) => {
    const fetchId = ++fetchIdRef.current
    if (showLoading) setLoading(true)
    setError(null)
    try {
      const result = await attendanceApi.list(params)
      if (fetchId === fetchIdRef.current) {
        setData(result.items); setTotal(result.total); setPages(result.pages)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load attendance records')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [])

  // The workspace's filters are mapped to the exact server params the
  // attendance API supports — nothing is invented client-side.
  useEffect(() => {
    const params: AttendanceListParams = { page: workspace.page, size: workspace.size }
    const facet = workspace.filters.facets.status?.[0]
    if (facet) params.status = facet
    const dateRange = workspace.filters.ranges.attendance_date
    if (dateRange?.min !== undefined) params.attendance_date = String(dateRange.min)
    else if (dateRange?.max !== undefined) params.attendance_date = String(dateRange.max)
    const studentRange = workspace.filters.ranges.student_id
    if (studentRange?.min !== undefined) params.student_id = Number(studentRange.min)
    else if (studentRange?.max !== undefined) params.student_id = Number(studentRange.max)
    const sectionRange = workspace.filters.ranges.section_id
    if (sectionRange?.min !== undefined) params.section_id = Number(sectionRange.min)
    else if (sectionRange?.max !== undefined) params.section_id = Number(sectionRange.max)
    // bare numeric search → student id lookup
    const q = workspace.filters.query.trim()
    const sid = Number(q)
    if (q && Number.isFinite(sid)) params.student_id = sid
    fetch(params, true)
  }, [workspace.page, workspace.size, workspace.filters, fetch])

  // ── export the current workspace state (P8 §22) ──
  const [exporting, setExporting] = useState(false)
  const handleExport = async () => {
    setExporting(true)
    try {
      const sectionRange = workspace.filters.ranges.section_id
      const dateRange = workspace.filters.ranges.attendance_date
      const blob = await exportApi.attendance({
        status: workspace.filters.facets.status?.[0],
        section_id:
          sectionRange?.min !== undefined
            ? Number(sectionRange.min)
            : sectionRange?.max !== undefined
              ? Number(sectionRange.max)
              : undefined,
        start_date: dateRange?.min !== undefined ? String(dateRange.min) : undefined,
        end_date: dateRange?.max !== undefined ? String(dateRange.max) : undefined,
      })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'attendance.csv'
      a.click()
      window.URL.revokeObjectURL(url)
      showToast(`Exporting ${total} record${total === 1 ? '' : 's'}`, 'success')
    } catch (err: any) {
      showToast(err?.detail || 'Export failed', 'error')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="space-y-4">
      <DataWorkspace
        workspace={workspace}
        title="Attendance Records"
        description={`${total} record${total !== 1 ? 's' : ''}`}
        columns={columns}
        keyExtractor={(r) => r.id}
        data={data}
        total={total}
        pages={pages}
        loading={loading}
        error={error}
        onRetry={() => fetch({ page: workspace.page, size: workspace.size }, true)}
        onRefresh={() => fetch({ page: workspace.page, size: workspace.size }, false)}
        mode="server"
        filterPlaceholder="Search by student ID…"
        onRowClick={(r) => navigate(`/attendance/records/${r.id}`)}
        searchInputRef={searchInputRef}
        primaryAction={
          <Button onClick={() => navigate('/attendance/record')}>
            Record Attendance
            <kbd className="ml-2 hidden sm:inline-flex items-center px-1.5 py-0.5 rounded bg-white/20 text-[10px] font-medium text-white/80">N</kbd>
          </Button>
        }
        toolbarActions={
          <>
            <Button variant="outline" onClick={() => navigate('/attendance/daily')}>
              Daily Attendance
            </Button>
            <Button variant="secondary" onClick={handleExport} loading={exporting}>
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Export
            </Button>
          </>
        }
      />
    </div>
  )
}
