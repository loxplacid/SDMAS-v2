import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { studentApi } from '../../api/student/student-api'
import type { StudentResponse } from '../../api/generated/types'
import { Card, Badge, Button, Loading, ErrorState } from '../../components/ui'
import { formatDate, formatDateTime, capitalize } from '../../lib/utils'

export function StudentDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [student, setStudent] = useState<StudentResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    setError(null)
    studentApi.getById(Number(id))
      .then(setStudent)
      .catch((err) => setError(err?.detail || 'Failed to load student'))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <Loading text="Loading student details..." />
  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />
  if (!student) return <ErrorState message="Student not found" />

  const statusBadge: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
    active: 'success',
    inactive: 'danger',
    graduated: 'info',
    transferred: 'warning',
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <button
            onClick={() => navigate('/students')}
            className="text-sm text-blue-600 hover:text-blue-800 mb-1"
          >
            &larr; Back to Students
          </button>
          <h1 className="text-2xl font-bold text-gray-900">
            {student.first_name} {student.last_name}
          </h1>
          <p className="text-gray-500">Student #{student.student_number}</p>
        </div>
        <Badge variant={statusBadge[student.status] || 'default'}>
          {capitalize(student.status)}
        </Badge>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card title="Personal Information">
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">First Name</dt>
              <dd className="font-medium">{student.first_name}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Last Name</dt>
              <dd className="font-medium">{student.last_name}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Student Number</dt>
              <dd className="font-medium">{student.student_number}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Email</dt>
              <dd className="font-medium">{student.email || '-'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Date of Birth</dt>
              <dd className="font-medium">{formatDate(student.date_of_birth)}</dd>
            </div>
          </dl>
        </Card>

        <Card title="System Information">
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Status</dt>
              <dd>
                <Badge variant={statusBadge[student.status] || 'default'}>
                  {capitalize(student.status)}
                </Badge>
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Created</dt>
              <dd className="font-medium">{formatDateTime(student.created_at)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Updated</dt>
              <dd className="font-medium">{formatDateTime(student.updated_at)}</dd>
            </div>
          </dl>
        </Card>
      </div>

      <div className="flex gap-3">
        <Button onClick={() => navigate(`/students/${id}/edit`)}>Edit Student</Button>
        <Button variant="secondary" onClick={() => navigate('/students')}>Back to List</Button>
      </div>
    </div>
  )
}