import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { attendanceApi } from '../../api/attendance/attendance-api'
import type { AttendanceRecordResponse } from '../../api/generated/types'
import { Card, Badge, Button, ErrorState } from '../../components/ui'
import { formatDateTime, capitalize } from '../../lib/utils'

const statusBadge: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
  present: 'success',
  absent: 'danger',
  late: 'warning',
  excused: 'info',
}

export function AttendanceRecordDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [record, setRecord] = useState<AttendanceRecordResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    attendanceApi.getById(Number(id))
      .then(setRecord)
      .catch((err) => setError(err?.detail || 'Failed to load record'))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return (
    <div className="space-y-6 animate-fade-in-up">
      <div className="h-8 bg-gray-200 rounded w-48 animate-pulse" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="h-48 bg-[var(--color-surface)] rounded-xl animate-pulse" />
        <div className="h-48 bg-[var(--color-surface)] rounded-xl animate-pulse" />
      </div>
    </div>
  )
  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />
  if (!record) return <ErrorState message="Record not found" />

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <div className="text-[var(--color-brand-accent)] text-xs font-semibold uppercase tracking-wider">Attendance</div>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)] mt-1">Attendance Record #{record.id}</h1>
        <button onClick={() => navigate('/attendance/records')} className="text-sm text-[var(--color-brand-accent)] hover:text-[var(--color-brand-accent-hover)] transition-colors mt-1">
          &larr; Back to Records
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card title="Attendance Details" className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-[var(--color-text-tertiary)]">Student ID</dt>
              <dd className="font-medium text-[var(--color-text-primary)]">{record.student_id}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-[var(--color-text-tertiary)]">Date</dt>
              <dd className="font-medium text-[var(--color-text-primary)]">{record.attendance_date}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-[var(--color-text-tertiary)]">Status</dt>
              <dd><Badge variant={statusBadge[record.status]}>{capitalize(record.status)}</Badge></dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-[var(--color-text-tertiary)]">Notes</dt>
              <dd className="font-medium text-[var(--color-text-primary)]">{record.notes || '-'}</dd>
            </div>
          </dl>
        </Card>

        <Card title="Context" className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-[var(--color-text-tertiary)]">Academic Year</dt>
              <dd className="font-medium text-[var(--color-text-primary)]">{record.academic_year_id}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-[var(--color-text-tertiary)]">Class</dt>
              <dd className="font-medium text-[var(--color-text-primary)]">{record.class_id}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-[var(--color-text-tertiary)]">Section</dt>
              <dd className="font-medium text-[var(--color-text-primary)]">{record.section_id}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-[var(--color-text-tertiary)]">Recorded</dt>
              <dd className="font-medium text-[var(--color-text-primary)]">{formatDateTime(record.recorded_at)}</dd>
            </div>
          </dl>
        </Card>
      </div>

      <div className="flex gap-3">
        <Button onClick={() => navigate(`/attendance/records/${id}/edit`)}>Edit Record</Button>
        <Button variant="outline" onClick={() => navigate('/attendance/records')}>Back to List</Button>
      </div>
    </div>
  )
}