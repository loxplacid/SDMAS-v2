import { useState, useEffect } from 'react'
import { academicYearApi } from '../../api/academic/academic-year-api'
import { rolloverApi } from '../../api/reports/rollover-api'
import type { RolloverPreview, RolloverResult } from '../../api/reports/types'
import { Card, Button, Alert, Loading, Table, Input } from '../../components/ui'

export function RolloverPage() {
  const [academicYears, setAcademicYears] = useState<{ id: number; name: string }[]>([])
  const [selectedYearId, setSelectedYearId] = useState('')
  const [newYearName, setNewYearName] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  const [preview, setPreview] = useState<RolloverPreview | null>(null)
  const [result, setResult] = useState<RolloverResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [executing, setExecuting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    academicYearApi.list({ size: 100 }).then((r) => {
      setAcademicYears(r.items.map((y) => ({ id: y.id, name: y.name })))
    }).catch(() => {})
  }, [])

  const handlePreview = async () => {
    if (!selectedYearId || !newYearName || !startDate || !endDate) return
    setLoading(true)
    setError(null)
    setPreview(null)
    setResult(null)
    try {
      const p = await rolloverApi.preview({
        from_year_id: Number(selectedYearId),
        to_year_name: newYearName,
        to_start_date: startDate,
        to_end_date: endDate,
      })
      setPreview(p)
    } catch (err: any) {
      setError(err?.detail || 'Preview failed')
    } finally {
      setLoading(false)
    }
  }

  const handleExecute = async () => {
    if (!preview) return
    setExecuting(true)
    setError(null)
    try {
      const r = await rolloverApi.execute({
        from_year_id: Number(selectedYearId),
        to_year_name: newYearName,
        to_start_date: startDate,
        to_end_date: endDate,
      })
      setResult(r)
      setPreview(null)
    } catch (err: any) {
      setError(err?.detail || 'Rollover failed')
    } finally {
      setExecuting(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Academic Year Rollover</h1>
        <p className="text-gray-500 mt-1">Roll over to a new academic year with classes, sections, and enrollments</p>
      </div>

      <Card>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Source Academic Year</label>
            <select
              value={selectedYearId}
              onChange={(e) => setSelectedYearId(e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select year</option>
              {academicYears.map((y) => (
                <option key={y.id} value={y.id}>{y.name}</option>
              ))}
            </select>
          </div>
          <Input
            label="New Academic Year Name"
            value={newYearName}
            onChange={(e) => setNewYearName(e.target.value)}
            placeholder="e.g. 2026-2027"
          />
          <Input
            label="Start Date"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
          <Input
            label="End Date"
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
        </div>
        <div className="mt-4">
          <Button onClick={handlePreview} loading={loading} disabled={!selectedYearId || !newYearName || !startDate || !endDate}>
            Preview Rollover
          </Button>
        </div>
        {error && <Alert variant="error" onClose={() => setError(null)} className="mt-3">{error}</Alert>}
      </Card>

      {loading && <Loading text="Generating preview..." />}

      {preview && (
        <Card title="Rollover Preview">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
            <div>
              <p className="text-sm text-gray-500">From</p>
              <p className="font-semibold">{preview.from_year_name}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">To</p>
              <p className="font-semibold">{preview.to_year_name}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Classes</p>
              <p className="font-semibold">{preview.classes.length}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Sections</p>
              <p className="font-semibold">{preview.sections.length}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Enrolled Students</p>
              <p className="font-semibold">{preview.enrolled_students}</p>
            </div>
          </div>
          <Button onClick={handleExecute} loading={executing} variant="primary" className="bg-green-600 hover:bg-green-700">
            Execute Rollover
          </Button>
        </Card>
      )}

      {result && (
        <Card title="Rollover Result">
          <div className="space-y-2">
            <p className="text-green-600 font-semibold">{result.message}</p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-4">
              <div>
                <p className="text-sm text-gray-500">New Year ID</p>
                <p className="font-semibold">{result.academic_year_id}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Classes Created</p>
                <p className="font-semibold">{result.classes_created}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Sections Created</p>
                <p className="font-semibold">{result.sections_created}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Enrollments Created</p>
                <p className="font-semibold">{result.enrollments_created}</p>
              </div>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}

export default RolloverPage