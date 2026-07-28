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
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <button onClick={() => navigate('/academic')} className="text-sm text-blue-600 hover:text-blue-800 mb-1">&larr; Back to Academic</button>
          <h1 className="text-2xl font-bold text-gray-900">{year.name}</h1>
        </div>
        <Badge variant={year.status === 'active' ? 'success' : 'danger'}>{capitalize(year.status)}</Badge>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card title="Details">
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between"><dt className="text-gray-500">Name</dt><dd className="font-medium">{year.name}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Start Date</dt><dd className="font-medium">{year.start_date}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">End Date</dt><dd className="font-medium">{year.end_date}</dd></div>
          </dl>
        </Card>
        <Card title="System Information">
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between"><dt className="text-gray-500">Status</dt><dd><Badge variant={year.status === 'active' ? 'success' : 'danger'}>{capitalize(year.status)}</Badge></dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Created</dt><dd className="font-medium">{formatDateTime(year.created_at)}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Updated</dt><dd className="font-medium">{formatDateTime(year.updated_at)}</dd></div>
          </dl>
        </Card>
      </div>
      <div className="flex gap-3">
        <Button variant="secondary" onClick={() => navigate('/academic')}>Back to List</Button>
      </div>
    </div>
  )
}