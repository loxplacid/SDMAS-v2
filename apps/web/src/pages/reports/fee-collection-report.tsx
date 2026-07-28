import { useState, useEffect, useCallback, useRef } from 'react'
import { academicYearApi } from '../../api/academic/academic-year-api'
import { feeReportApi } from '../../api/reports/fee-reports'
import type { CollectionReportItem } from '../../api/reports/types'
import { Card, Select, Button, Loading, ErrorState, Table, Badge } from '../../components/ui'
import { formatCurrency } from '../../lib/utils'

export function FeeCollectionReportPage() {
  const [academicYears, setAcademicYears] = useState<{ id: number; name: string }[]>([])
  const [selectedYearId, setSelectedYearId] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [report, setReport] = useState<CollectionReportItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  useEffect(() => {
    academicYearApi.list({ size: 100 }).then((r) => {
      setAcademicYears(r.items.map((y) => ({ id: y.id, name: y.name })))
    }).catch(() => {})
  }, [])

  const fetchReport = useCallback(async () => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string | number | boolean | undefined | null> = {
        academic_year_id: Number(selectedYearId),
      }
      if (startDate) params.start_date = startDate
      if (endDate) params.end_date = endDate

      const result = await feeReportApi.getCollectionReport(params as any)
      if (fetchId === fetchIdRef.current) setReport(result)
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load report')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [selectedYearId, startDate, endDate])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Fee Collection Report</h1>
        <p className="text-gray-500 mt-1">Fee collection summary grouped by class</p>
      </div>

      <Card>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Academic Year</label>
            <Select
              options={academicYears.map((y) => ({ value: String(y.id), label: y.name }))}
              value={selectedYearId}
              onChange={(e) => setSelectedYearId(e.target.value)}
              placeholder="Select year"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
        <div className="mt-4">
          <Button onClick={fetchReport} loading={loading} disabled={!selectedYearId}>Generate Report</Button>
        </div>
      </Card>

      {error && <ErrorState message={error} onRetry={fetchReport} />}
      {loading && <Loading text="Generating report..." />}

      {report.length > 0 && (
        <Card>
          <Table
            columns={[
              { key: 'class_name', header: 'Class' },
              { key: 'total_students', header: 'Students' },
              {
                key: 'total_fees_assigned', header: 'Total Fees',
                render: (r: CollectionReportItem) => formatCurrency(r.total_fees_assigned),
              },
              {
                key: 'total_collected', header: 'Collected',
                render: (r: CollectionReportItem) => (
                  <span className="text-green-600 font-medium">{formatCurrency(r.total_collected)}</span>
                ),
              },
              {
                key: 'total_outstanding', header: 'Outstanding',
                render: (r: CollectionReportItem) => (
                  <span className="text-red-600 font-medium">{formatCurrency(r.total_outstanding)}</span>
                ),
              },
              {
                key: 'collection_percentage', header: 'Collection %',
                render: (r: CollectionReportItem) => (
                  <Badge variant={r.collection_percentage >= 80 ? 'success' : r.collection_percentage >= 50 ? 'warning' : 'danger'}>
                    {r.collection_percentage}%
                  </Badge>
                ),
              },
            ]}
            data={report}
            keyExtractor={(r) => r.class_id}
            emptyMessage="No data found."
          />
        </Card>
      )}
    </div>
  )
}

export default FeeCollectionReportPage