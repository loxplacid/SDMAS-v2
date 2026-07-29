import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { academicYearApi } from '../../api/academic/academic-year-api'
import type { AcademicYearResponse } from '../../api/generated/types'
import { Card, Badge, Button, Loading, ErrorState } from '../../components/ui'
import { formatDateTime, capitalize } from '../../lib/utils'

export function AcademicYearDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [year, setYear] = useState<AcademicYearResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    setLoading(true); setError(null)
    academicYearApi.getById(Number(id))
      .then(setYear)
      .catch((err) => setError(err?.detail || 'Failed to load'))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <Loading text="Loading..." />
  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />
  if (!year) return <ErrorState message="Academic year not found" />

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <button onClick={() => navigate('/academic')} className="text-sm text-[var(--color-brand-accent)] hover:text-[var(--color-brand-accent-hover)] transition-colors mb-1">&larr; Back to Academics</button>
          <h1 className="text-2xl font-bold text-[var(--color-text-primary)] tracking-tight">{year.name}</h1>
          <p className="text-sm text-[var(--color-text-tertiary)] mt-1">Academic year details</p>
        </div>
        <Badge variant={year.status === 'active' ? 'success' : 'danger'}>{capitalize(year.status)}</Badge>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card title="Details" className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between"><dt className="text-[var(--color-text-tertiary)]">Name</dt><dd className="font-medium text-[var(--color-text-primary)]">{year.name}</dd></div>
            <div className="flex justify-between"><dt className="text-[var(--color-text-tertiary)]">Start Date</dt><dd className="font-medium text-[var(--color-text-primary)]">{year.start_date}</dd></div>
            <div className="flex justify-between"><dt className="text-[var(--color-text-tertiary)]">End Date</dt><dd className="font-medium text-[var(--color-text-primary)]">{year.end_date}</dd></div>
          </dl>
        </Card>
        <Card title="System Information" className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between"><dt className="text-[var(--color-text-tertiary)]">Status</dt><dd><Badge variant={year.status === 'active' ? 'success' : 'danger'}>{capitalize(year.status)}</Badge></dd></div>
            <div className="flex justify-between"><dt className="text-[var(--color-text-tertiary)]">Created</dt><dd className="font-medium text-[var(--color-text-primary)]">{formatDateTime(year.created_at)}</dd></div>
            <div className="flex justify-between"><dt className="text-[var(--color-text-tertiary)]">Updated</dt><dd className="font-medium text-[var(--color-text-primary)]">{formatDateTime(year.updated_at)}</dd></div>
          </dl>
        </Card>
      </div>
      <div className="flex gap-3">
        <Button variant="outline" onClick={() => navigate('/academic')}>Back to List</Button>
      </div>
    </div>
  )
}