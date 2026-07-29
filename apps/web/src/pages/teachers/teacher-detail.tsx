import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { teacherApi } from '../../api/academic/teacher-api'
import type { TeacherResponse } from '../../api/generated/types'
import { Card, Badge, Button, ErrorState } from '../../components/ui'
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
  if (!teacher) return <ErrorState message="Teacher not found" />

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="text-[var(--color-brand-accent)] text-xs font-semibold uppercase tracking-wider">People</div>
          <h1 className="text-2xl font-bold text-[var(--color-text-primary)] mt-1 tracking-tight">{teacher.first_name} {teacher.last_name}</h1>
          <p className="text-sm text-[var(--color-text-tertiary)] mt-1">Employee #{teacher.employee_number}</p>
        </div>
        <Badge variant={teacher.status === 'active' ? 'success' : 'danger'}>{capitalize(teacher.status)}</Badge>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card title="Personal Information" className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between"><dt className="text-[var(--color-text-tertiary)]">First Name</dt><dd className="font-medium text-[var(--color-text-primary)]">{teacher.first_name}</dd></div>
            <div className="flex justify-between"><dt className="text-[var(--color-text-tertiary)]">Last Name</dt><dd className="font-medium text-[var(--color-text-primary)]">{teacher.last_name}</dd></div>
            <div className="flex justify-between"><dt className="text-[var(--color-text-tertiary)]">Employee #</dt><dd className="font-medium text-[var(--color-text-primary)]">{teacher.employee_number}</dd></div>
            <div className="flex justify-between"><dt className="text-[var(--color-text-tertiary)]">Email</dt><dd className="font-medium text-[var(--color-text-primary)]">{teacher.email || '-'}</dd></div>
          </dl>
        </Card>
        <Card title="System Information" className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between"><dt className="text-[var(--color-text-tertiary)]">Status</dt><dd><Badge variant={teacher.status === 'active' ? 'success' : 'danger'}>{capitalize(teacher.status)}</Badge></dd></div>
            <div className="flex justify-between"><dt className="text-[var(--color-text-tertiary)]">Created</dt><dd className="font-medium text-[var(--color-text-primary)]">{formatDateTime(teacher.created_at)}</dd></div>
            <div className="flex justify-between"><dt className="text-[var(--color-text-tertiary)]">Updated</dt><dd className="font-medium text-[var(--color-text-primary)]">{formatDateTime(teacher.updated_at)}</dd></div>
          </dl>
        </Card>
      </div>
      <div className="flex gap-3">
        <Button variant="outline" onClick={() => navigate('/teachers')}>Back to List</Button>
      </div>
    </div>
  )
}