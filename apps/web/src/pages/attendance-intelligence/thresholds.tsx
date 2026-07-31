import { useState, useEffect, useCallback, useRef } from 'react'
import { attendanceIntelligenceApi, type AttendanceThresholdResponse } from '../../api/attendance-intelligence/attendance-intelligence-api'
import { Card, Table, PageHeader, Button, Badge, Pagination, Loading, ErrorState, useToast, Modal, Input, Select } from '../../components/ui'
import { capitalize } from '../../lib/utils'

const typeBadge: Record<string, 'warning' | 'danger' | 'info' | 'neutral' | 'primary' | 'success'> = {
  warning: 'warning', critical: 'danger', chronic: 'info',
}

const columns = [
  { key: 'name', header: 'Name' },
  { key: 'threshold_type', header: 'Type', render: (r: AttendanceThresholdResponse) => <Badge variant={typeBadge[r.threshold_type] || 'default'}>{capitalize(r.threshold_type)}</Badge> },
  { key: 'percentage', header: 'Threshold %', render: (r: AttendanceThresholdResponse) => <span className="font-semibold">{r.percentage}%</span> },
  { key: 'days_absent_threshold', header: 'Days Absent', render: (r: AttendanceThresholdResponse) => r.days_absent_threshold ?? '-' },
  { key: 'consecutive_absences', header: 'Consecutive', render: (r: AttendanceThresholdResponse) => r.consecutive_absences ?? '-' },
  { key: 'notification_enabled', header: 'Notifications', render: (r: AttendanceThresholdResponse) => r.notification_enabled ? <Badge variant="success">Enabled</Badge> : <Badge variant="neutral">Disabled</Badge> },
  { key: 'status', header: 'Status', render: (r: AttendanceThresholdResponse) => <Badge variant={r.status === 'active' ? 'success' : 'neutral'}>{capitalize(r.status)}</Badge> },
]

export function AttendanceThresholdsPage() {
  const { showToast } = useToast()
  const [data, setData] = useState<AttendanceThresholdResponse[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(20)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState({ name: '', threshold_type: 'warning', percentage: 75, days_absent_threshold: '', consecutive_absences: '', notification_enabled: true })
  const fetchIdRef = useRef(0)

  const fetch = useCallback(async () => {
    const fetchId = ++fetchIdRef.current
    setLoading(true); setError(null)
    try {
      const result = await attendanceIntelligenceApi.listThresholds({ page, size })
      if (fetchId === fetchIdRef.current) { setData(result.items); setTotal(result.total); setPage(result.page) }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load')
    } finally { if (fetchId === fetchIdRef.current) setLoading(false) }
  }, [page, size])

  useEffect(() => { fetch() }, [fetch])

  const handleCreate = async () => {
    try {
      await attendanceIntelligenceApi.createThreshold({
        ...form,
        days_absent_threshold: form.days_absent_threshold ? Number(form.days_absent_threshold) : null,
        consecutive_absences: form.consecutive_absences ? Number(form.consecutive_absences) : null,
      })
      showToast('Threshold created', 'success')
      setShowModal(false)
      setForm({ name: '', threshold_type: 'warning', percentage: 75, days_absent_threshold: '', consecutive_absences: '', notification_enabled: true })
      fetch()
    } catch (err: any) { showToast(err?.detail || 'Failed to create', 'error') }
  }

  const handleDelete = async (id: number) => {
    try {
      await attendanceIntelligenceApi.deleteThreshold(id)
      showToast('Threshold deleted', 'info')
      fetch()
    } catch (err: any) { showToast(err?.detail || 'Failed to delete', 'error') }
  }

  const actionCol = {
    key: 'actions' as const,
    header: 'Actions' as const,
    render: (r: AttendanceThresholdResponse) => (
      <Button size="sm" variant="ghost" className="text-red-500" onClick={(e: any) => { e.stopPropagation(); handleDelete(r.id) }}>Delete</Button>
    ),
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        title="Attendance Thresholds"
        subtitle="Configure attendance warning and critical thresholds"
        actions={
          <Button onClick={() => setShowModal(true)}>Add Threshold</Button>
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

      <Modal open={showModal} onClose={() => setShowModal(false)} title="New Attendance Threshold"
        footer={
          <div className="flex gap-2 justify-end">
            <Button variant="outline" onClick={() => setShowModal(false)}>Cancel</Button>
            <Button onClick={handleCreate}>Create</Button>
          </div>
        }
      >
        <div className="space-y-4">
          <Input label="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Warning Level 1" required />
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Type</label>
              <select className="w-full rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm bg-[var(--color-bg-primary)]" value={form.threshold_type} onChange={(e) => setForm({ ...form, threshold_type: e.target.value })}>
                <option value="warning">Warning</option>
                <option value="critical">Critical</option>
                <option value="chronic">Chronic</option>
              </select>
            </div>
            <Input label="Percentage (%)" type="number" value={String(form.percentage)} onChange={(e) => setForm({ ...form, percentage: Number(e.target.value) })} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Input label="Days Absent Threshold" type="number" value={form.days_absent_threshold} onChange={(e) => setForm({ ...form, days_absent_threshold: e.target.value })} placeholder="Optional" />
            <Input label="Consecutive Absences" type="number" value={form.consecutive_absences} onChange={(e) => setForm({ ...form, consecutive_absences: e.target.value })} placeholder="Optional" />
          </div>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={form.notification_enabled} onChange={(e) => setForm({ ...form, notification_enabled: e.target.checked })} className="rounded" />
            <span className="text-sm">Enable notifications</span>
          </label>
        </div>
      </Modal>
    </div>
  )
}

export default AttendanceThresholdsPage
