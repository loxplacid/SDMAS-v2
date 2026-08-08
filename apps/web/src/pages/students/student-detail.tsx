import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { studentApi } from '../../api/student/student-api'
import type { StudentResponse } from '../../api/generated/types'
import { Card, Button, ErrorState, BreadcrumbBar, PageHeader, StatusBadge } from '../../components/ui'
import { formatDate, formatDateTime } from '../../lib/utils'

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

  if (loading) return (
    <div className="space-y-6 animate-fade-in-up">
      <div className="h-4 bg-[var(--color-border)] rounded w-64 animate-pulse" />
      <div className="h-8 bg-[var(--color-border)] rounded w-48 animate-pulse" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="h-64 bg-[var(--color-surface)] rounded-xl animate-pulse" />
        <div className="h-64 bg-[var(--color-surface)] rounded-xl animate-pulse" />
      </div>
    </div>
  )
  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />
  if (!student) return <ErrorState message="Student not found" />

  return (
    <div className="space-y-6 animate-fade-in-up">
      <BreadcrumbBar pageLabel={`${student.first_name} ${student.last_name}`} />

      <PageHeader
        title={`${student.first_name} ${student.last_name}`}
        subtitle={`Student #${student.student_number}`}
        actions={<StatusBadge status={student.status} />}
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card title="Personal Information" className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
          <dl className="space-y-4 text-sm">
            {[
              ['First Name', student.first_name],
              ['Last Name', student.last_name],
              ['Student Number', student.student_number],
              ['Email', student.email || '-'],
              ['Date of Birth', formatDate(student.date_of_birth)],
            ].map(([label, value]) => (
              <div key={label as string} className="flex justify-between items-center">
                <dt className="text-[var(--color-text-muted)]">{label as string}</dt>
                <dd className="font-medium text-[var(--color-text-primary)] text-right">{value as string}</dd>
              </div>
            ))}
          </dl>
        </Card>

        <Card title="System Information" className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
          <dl className="space-y-4 text-sm">
            <div className="flex justify-between items-center">
              <dt className="text-[var(--color-text-muted)]">Status</dt>
              <dd><StatusBadge status={student.status} /></dd>
            </div>
            {[
              ['Created', formatDateTime(student.created_at)],
              ['Updated', formatDateTime(student.updated_at)],
            ].map(([label, value]) => (
              <div key={label as string} className="flex justify-between items-center">
                <dt className="text-[var(--color-text-muted)]">{label as string}</dt>
                <dd className="font-medium text-[var(--color-text-primary)]">{value as string}</dd>
              </div>
            ))}
          </dl>
        </Card>
      </div>

      <div className="flex gap-3 flex-wrap">
        <Button onClick={() => navigate(`/students/${id}/edit`)}>Edit Student</Button>
        <Button onClick={() => navigate(`/students/${id}/360`)}>360° View</Button>
        <Button variant="outline" onClick={() => navigate('/students')}>Back to List</Button>
      </div>
    </div>
  )
}
