import { useState } from 'react'
import { academicYearApi } from '../../api/academic/academic-year-api'
import { batchApi } from '../../api/reports/batch-api'
import type { BatchEnrollItem, BatchEnrollResult, BatchEnrollResultItem } from '../../api/reports/types'
import { Card, Button, Input, Alert, Loading, Table, Badge, Select } from '../../components/ui'

export function BatchEnrollPage() {
  const [academicYears, setAcademicYears] = useState<{ id: number; name: string }[]>([])
  const [selectedYearId, setSelectedYearId] = useState('')
  const [entriesText, setEntriesText] = useState('')
  const [result, setResult] = useState<BatchEnrollResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useState(() => {
    academicYearApi.list({ size: 100 }).then((r) => {
      setAcademicYears(r.items.map((y) => ({ id: y.id, name: y.name })))
    }).catch(() => {})
  })

  const parseEntries = (): BatchEnrollItem[] => {
    return entriesText
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line)
      .map((line) => {
        const parts = line.split(',')
        const student_id = parseInt(parts[0], 10)
        const class_id = parseInt(parts[1], 10)
        const section_id = parts[2] ? parseInt(parts[2], 10) : null
        return { student_id, class_id, section_id }
      })
      .filter((e) => !isNaN(e.student_id) && !isNaN(e.class_id))
  }

  const handleSubmit = async () => {
    const enrollments = parseEntries()
    if (enrollments.length === 0 || !selectedYearId) return

    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const r = await batchApi.enroll({
        academic_year_id: Number(selectedYearId),
        enrollments,
      })
      setResult(r)
    } catch (err: any) {
      setError(err?.detail || 'Batch enrollment failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Batch Enroll Students</h1>
        <p className="text-gray-500 mt-1">Enroll multiple students in one operation</p>
      </div>

      <Card>
        <div className="space-y-4">
          <Select
            options={academicYears.map((y) => ({ value: String(y.id), label: y.name }))}
            value={selectedYearId}
            onChange={(e) => setSelectedYearId(e.target.value)}
            placeholder="Select academic year"
          />

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Student Entries</label>
            <p className="text-xs text-gray-500 mb-2">
              One per line: student_id, class_id, section_id (optional)
            </p>
            <textarea
              value={entriesText}
              onChange={(e) => setEntriesText(e.target.value)}
              rows={10}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder={`1, 5, 10\n2, 5, 10\n3, 6`}
            />
            <p className="text-xs text-gray-400 mt-1">{parseEntries().length} valid entries</p>
          </div>

          <Button onClick={handleSubmit} loading={loading} disabled={!selectedYearId || parseEntries().length === 0}>
            Enroll Students
          </Button>
        </div>

        {error && <Alert variant="error" onClose={() => setError(null)} className="mt-3">{error}</Alert>}
      </Card>

      {loading && <Loading text="Processing enrollment..." />}

      {result && (
        <Card>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div>
              <p className="text-sm text-gray-500">Total</p>
              <p className="text-2xl font-bold">{result.total}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Succeeded</p>
              <p className="text-2xl font-bold text-green-600">{result.succeeded}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Failed</p>
              <p className="text-2xl font-bold text-red-600">{result.failed}</p>
            </div>
          </div>

          {result.failed > 0 && (
            <Table
              columns={[
                { key: 'student_id', header: 'Student ID' },
                {
                  key: 'success', header: 'Status',
                  render: (r: BatchEnrollResultItem) => (
                    <Badge variant={r.success ? 'success' : 'danger'}>{r.success ? 'OK' : 'Failed'}</Badge>
                  ),
                },
                { key: 'error', header: 'Error' },
              ]}
              data={result.results.filter((r) => !r.success)}
              keyExtractor={(r) => r.student_id}
              emptyMessage="All succeeded."
            />
          )}
        </Card>
      )}
    </div>
  )
}

export default BatchEnrollPage