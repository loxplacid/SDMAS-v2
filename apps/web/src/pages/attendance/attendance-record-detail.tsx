import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { attendanceApi } from '../../api/attendance/attendance-api'
import type { AttendanceRecordResponse } from '../../api/generated/types'
import { Card, Badge, Button, Loading, ErrorState } from '../../components/ui'
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

  if (loading) return <Loading text="Loading record..." />
  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />
  if (!record) return <ErrorState message="Record not found" />

  return (
    <div className="space-y-6">
      <div>
        <button onClick={() => navigate('/attendance/records')} className="text-sm text-blue-600 hover:text-blue-800 mb-1">
          &larr; Back to Records
        </button>
        <h1 className="text-2xl font-bold text-gray-900">Attendance Record #{record.id}</h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card title="Attendance Details">
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Student ID</dt>
              <dd className="font-medium">{record.student_id}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Date</dt>
              <dd className="font-medium">{record.attendance_date}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Status</dt>
              <dd><Badge variant={statusBadge[record.status]}>{capitalize(record.status)}</Badge></dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Notes</dt>
              <dd className="font-medium">{record.notes || '-'}</dd>
            </div>
          </dl>
        </Card>

        <Card title="Context">
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Academic Year</dt>
              <dd className="font-medium">{record.academic_year_id}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Class</dt>
              <dd className="font-medium">{record.class_id}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Section</dt>
              <dd className="font-medium">{record.section_id}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Recorded</dt>
              <dd className="font-medium">{formatDateTime(record.recorded_at)}</dd>
            </div>
          </dl>
        </Card>
      </div>

      <div className="flex gap-3">
        <Button onClick={() => navigate(`/attendance/records/${id}/edit`)}>Edit Record</Button>
        <Button variant="secondary" onClick={() => navigate('/attendance/records')}>Back to List</Button>
      </div>
    </div>
  )
}