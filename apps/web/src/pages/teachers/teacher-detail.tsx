import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { teacherApi } from '../../api/academic/teacher-api'
import type { TeacherResponse } from '../../api/generated/types'
import { Card, Badge, Button, Loading, ErrorState } from '../../components/ui'
import { formatDateTime, capitalize } from '../../lib/utils'

export function TeacherDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [teacher, setTeacher] = useState<TeacherResponse | null>(null)
  const [loading, setLoading] = useState(true); const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return; setLoading(true); setError(null)
    teacherApi.getById(Number(id)).then(setTeacher).catch((err) => setError(err?.detail || 'Failed to load')).finally(() => setLoading(false))
  }, [id])

  if (loading) return <Loading text="Loading teacher..." />
  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />
  if (!teacher) return <ErrorState message="Teacher not found" />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <button onClick={() => navigate('/teachers')} className="text-sm text-blue-600 hover:text-blue-800 mb-1">&larr; Back to Teachers</button>
          <h1 className="text-2xl font-bold text-gray-900">{teacher.first_name} {teacher.last_name}</h1>
          <p className="text-gray-500">Employee #{teacher.employee_number}</p>
        </div>
        <Badge variant={teacher.status === 'active' ? 'success' : 'danger'}>{capitalize(teacher.status)}</Badge>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card title="Personal Information">
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between"><dt className="text-gray-500">First Name</dt><dd className="font-medium">{teacher.first_name}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Last Name</dt><dd className="font-medium">{teacher.last_name}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Employee #</dt><dd className="font-medium">{teacher.employee_number}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Email</dt><dd className="font-medium">{teacher.email || '-'}</dd></div>
          </dl>
        </Card>
        <Card title="System Information">
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between"><dt className="text-gray-500">Status</dt><dd><Badge variant={teacher.status === 'active' ? 'success' : 'danger'}>{capitalize(teacher.status)}</Badge></dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Created</dt><dd className="font-medium">{formatDateTime(teacher.created_at)}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Updated</dt><dd className="font-medium">{formatDateTime(teacher.updated_at)}</dd></div>
          </dl>
        </Card>
      </div>
      <div className="flex gap-3"><Button variant="secondary" onClick={() => navigate('/teachers')}>Back to List</Button></div>
    </div>
  )
}