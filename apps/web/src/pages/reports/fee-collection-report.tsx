import { useState, useEffect, useCallback, useRef } from 'react'
import { academicYearApi } from '../../api/academic/academic-year-api'
import { feeReportApi } from '../../api/reports/fee-reports'
import type { CollectionReportItem } from '../../api/reports/types'
import { Card, Select, Button, ErrorState, Table, Badge, Input, PageHeader } from '../../components/ui'
import { formatCurrency } from '../../lib/utils'
import { useExport } from '../../hooks/use-export'

export function FeeCollectionReportPage() {
  const [academicYears, setAcademicYears] = useState<{ id: number; name: string }[]>([])
  const [selectedYearId, setSelectedYearId] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [report, setReport] = useState<CollectionReportItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)
  const { exportPDF, exportExcel, exporting } = useExport()

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
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        eyebrow="Reports"
        title="Fee Collection Report"
        subtitle="Fee collection summary grouped by class"
        compact
      />

      <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">Academic Year</label>
            <Select
              options={academicYears.map((y) => ({ value: String(y.id), label: y.name }))}
              value={selectedYearId}
              onChange={(e) => setSelectedYearId(e.target.value)}
              placeholder="Select year"
            />
          </div>
          <Input label="Start Date" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          <Input label="End Date" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
        </div>
        <div className="mt-4">
          <Button onClick={fetchReport} loading={loading} disabled={!selectedYearId}>Generate Report</Button>
        </div>
      </Card>

      {error && <ErrorState message={error} onRetry={fetchReport} />}
      {loading && <div className="h-48 bg-[var(--color-surface)] rounded-xl animate-pulse" />}

      {report.length > 0 && (
        <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Collection Summary</h2>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" loading={exporting === 'pdf'}
                onClick={() => exportPDF('Fee Collection Report', [
                  { key: 'class_name', header: 'Class' },
                  { key: 'total_students', header: 'Students' },
                  { key: 'total_fees_assigned', header: 'Total Fees', render: (r: any) => formatCurrency(r.total_fees_assigned) },
                  { key: 'total_collected', header: 'Collected', render: (r: any) => formatCurrency(r.total_collected) },
                  { key: 'total_outstanding', header: 'Outstanding', render: (r: any) => formatCurrency(r.total_outstanding) },
                  { key: 'collection_percentage', header: 'Collection %', render: (r: any) => `${r.collection_percentage}%` },
                ], report, 'fee-collection-report')}
              >Export PDF</Button>
              <Button variant="outline" size="sm" loading={exporting === 'excel'}
                onClick={() => exportExcel('Fee Collection Report', [
                  { key: 'class_name', header: 'Class' },
                  { key: 'total_students', header: 'Students' },
                  { key: 'total_fees_assigned', header: 'Total Fees', render: (r: any) => formatCurrency(r.total_fees_assigned) },
                  { key: 'total_collected', header: 'Collected', render: (r: any) => formatCurrency(r.total_collected) },
                  { key: 'total_outstanding', header: 'Outstanding', render: (r: any) => formatCurrency(r.total_outstanding) },
                  { key: 'collection_percentage', header: 'Collection %', render: (r: any) => `${r.collection_percentage}%` },
                ], report, 'fee-collection-report')}
              >Export Excel</Button>
            </div>
          </div>
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