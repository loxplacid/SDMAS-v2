import { useState } from 'react'
import { academicYearApi } from '../../api/academic/academic-year-api'
import { batchApi } from '../../api/reports/batch-api'
import type { BatchFeeDueResult, BatchFeeDueResultItem } from '../../api/reports/types'
import { Card, Button, Input, Alert, Table, Badge, Select, AnimatedCount } from '../../components/ui'

export function BatchFeeDuesPage() {
  const [academicYears, setAcademicYears] = useState<{ id: number; name: string }[]>([])
  const [selectedYearId, setSelectedYearId] = useState('')
  const [studentIdsText, setStudentIdsText] = useState('')
  const [result, setResult] = useState<BatchFeeDueResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useState(() => {
    academicYearApi.list({ size: 100 }).then((r) => {
      setAcademicYears(r.items.map((y) => ({ id: y.id, name: y.name })))
    }).catch(() => {})
  })

  const parseIds = (): number[] => {
    return studentIdsText
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line)
      .map((id) => parseInt(id, 10))
      .filter((id) => !isNaN(id))
  }

  const handleSubmit = async () => {
    const ids = parseIds()
    if (ids.length === 0 || !selectedYearId) return

    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const r = await batchApi.createFeeDues({
        academic_year_id: Number(selectedYearId),
        student_ids: ids,
      })
      setResult(r)
    } catch (err: any) {
      setError(err?.detail || 'Batch fee due creation failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <div className="text-[var(--color-brand-accent)] text-xs font-semibold uppercase tracking-wider">Data Operations</div>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)] mt-1">Batch Fee Dues</h1>
        <p className="text-sm text-[var(--color-text-tertiary)] mt-1">Create fee dues for multiple students at once</p>
      </div>

      <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
        <div className="space-y-4">
          <Select
            options={academicYears.map((y) => ({ value: String(y.id), label: y.name }))}
            value={selectedYearId}
            onChange={(e) => setSelectedYearId(e.target.value)}
            placeholder="Select academic year"
          />

          <div>
            <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">Student IDs</label>
            <p className="text-xs text-gray-500 mb-2">One student ID per line</p>
            <textarea
              value={studentIdsText}
              onChange={(e) => setStudentIdsText(e.target.value)}
              rows={8}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder={`1\n2\n3\n4\n5`}
            />
            <p className="text-xs text-gray-400 mt-1">{parseIds().length} valid IDs</p>
          </div>

          <Button onClick={handleSubmit} loading={loading} disabled={!selectedYearId || parseIds().length === 0}>
            Create Fee Dues
          </Button>
        </div>

        {error && <Alert variant="error" onClose={() => setError(null)} className="mt-3">{error}</Alert>}
      </Card>

      {loading && <div className="h-24 bg-[var(--color-surface)] rounded-xl animate-pulse" />}

      {result && (
        <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div>
              <p className="text-sm text-[var(--color-text-tertiary)]">Total</p>
              <p className="text-2xl font-bold text-[var(--color-text-primary)]"><AnimatedCount value={result.total} duration={800} /></p>
            </div>
            <div>
              <p className="text-sm text-[var(--color-text-tertiary)]">Succeeded</p>
              <p className="text-2xl font-bold text-green-600"><AnimatedCount value={result.succeeded} duration={800} /></p>
            </div>
            <div>
              <p className="text-sm text-[var(--color-text-tertiary)]">Failed</p>
              <p className="text-2xl font-bold text-red-600"><AnimatedCount value={result.failed} duration={800} /></p>
            </div>
          </div>

          {result.failed > 0 && (
            <Table
              columns={[
                { key: 'student_id', header: 'Student ID' },
                {
                  key: 'success', header: 'Status',
                  render: (r: BatchFeeDueResultItem) => (
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

export default BatchFeeDuesPage