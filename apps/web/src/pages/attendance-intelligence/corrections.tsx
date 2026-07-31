import { useState, useEffect, useCallback, useRef } from 'react'
import { attendanceIntelligenceApi, type AttendanceCorrectionResponse } from '../../api/attendance-intelligence/attendance-intelligence-api'
import { Card, Table, PageHeader, Button, Badge, Pagination, Loading, ErrorState, useToast } from '../../components/ui'
import { capitalize, formatDateTime } from '../../lib/utils'

const statusBadge: Record<string, 'warning' | 'success' | 'danger' | 'info' | 'neutral'> = {
  pending: 'warning', approved: 'success', declined: 'danger',
}

const columns = [
  { key: 'id', header: 'ID', render: (r: AttendanceCorrectionResponse) => `#${r.id}` },
  { key: 'record_type', header: 'Type', render: (r: AttendanceCorrectionResponse) => capitalize(r.record_type) },
  { key: 'record_id', header: 'Record' },
  { key: 'requested_status', header: 'Requested', render: (r: AttendanceCorrectionResponse) => <Badge variant={r.requested_status === 'present' ? 'success' : 'danger'}>{capitalize(r.requested_status)}</Badge> },
  { key: 'previous_status', header: 'Previous', render: (r: AttendanceCorrectionResponse) => r.previous_status ? <Badge variant="neutral">{capitalize(r.previous_status)}</Badge> : '-' },
  { key: 'reason', header: 'Reason', render: (r: AttendanceCorrectionResponse) => r.reason ? <span className="text-sm truncate max-w-[200px] block">{r.reason}</span> : '-' },
  { key: 'status', header: 'Status', render: (r: AttendanceCorrectionResponse) => <Badge variant={statusBadge[r.status] || 'neutral'}>{capitalize(r.status)}</Badge> },
  { key: 'created_at', header: 'Submitted', render: (r: AttendanceCorrectionResponse) => formatDateTime(r.created_at) },
]

export function AttendanceCorrectionsPage() {
  const { showToast } = useToast()
  const [data, setData] = useState<AttendanceCorrectionResponse[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(20)
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  const fetch = useCallback(async () => {
    const fetchId = ++fetchIdRef.current
    setLoading(true); setError(null)
    try {
      const params: any = { page, size }
      if (statusFilter) params.status = statusFilter
      const result = await attendanceIntelligenceApi.listCorrections(params)
      if (fetchId === fetchIdRef.current) { setData(result.items); setTotal(result.total); setPage(result.page) }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load')
    } finally { if (fetchId === fetchIdRef.current) setLoading(false) }
  }, [page, size, statusFilter])

  useEffect(() => { fetch() }, [fetch])

  const handleApprove = async (id: number) => {
    try {
      await attendanceIntelligenceApi.approveCorrection(id)
      showToast('Correction approved', 'success')
      fetch()
    } catch (err: any) { showToast(err?.detail || 'Failed to approve', 'error') }
  }

  const handleDecline = async (id: number) => {
    try {
      await attendanceIntelligenceApi.declineCorrection(id)
      showToast('Correction declined', 'info')
      fetch()
    } catch (err: any) { showToast(err?.detail || 'Failed to decline', 'error') }
  }

  const actionCol = {
    key: 'actions' as const,
    header: 'Actions' as const,
    render: (r: AttendanceCorrectionResponse) => r.status === 'pending' ? (
      <div className="flex gap-2">
        <Button size="sm" variant="primary" onClick={(e: any) => { e.stopPropagation(); handleApprove(r.id) }}>Approve</Button>
        <Button size="sm" variant="outline" onClick={(e: any) => { e.stopPropagation(); handleDecline(r.id) }}>Decline</Button>
      </div>
    ) : null,
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        title="Attendance Corrections"
        subtitle="Review and manage attendance correction requests"
        actions={
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => { setStatusFilter(''); setPage(1) }}>All</Button>
            <Button variant="outline" onClick={() => { setStatusFilter('pending'); setPage(1) }}>Pending</Button>
            <Button variant="outline" onClick={() => { setStatusFilter('approved'); setPage(1) }}>Approved</Button>
            <Button variant="outline" onClick={() => { setStatusFilter('declined'); setPage(1) }}>Declined</Button>
          </div>
        }
      />

      <Card>
        {error && <ErrorState message={error} />}
        {loading ? <Loading /> : (
          <>
            <Table data={data} columns={[...columns, actionCol as any]} keyExtractor={(r) => r.id} />
            <Pagination page={page} size={size} total={total} pages={Math.ceil(total / size)} onPageChange={setPage} onSizeChange={setSize} />
          </>
        )}
      </Card>
    </div>
  )
}

export default AttendanceCorrectionsPage
