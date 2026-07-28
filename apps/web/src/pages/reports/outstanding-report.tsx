import { useState, useEffect, useCallback, useRef } from 'react'
import { academicYearApi } from '../../api/academic/academic-year-api'
import { classApi } from '../../api/academic/class-api'
import { feeReportApi } from '../../api/reports/fee-reports'
import type { OutstandingReportItem } from '../../api/reports/types'
import { Card, Select, Button, Loading, ErrorState, Table, Badge, Pagination } from '../../components/ui'
import { formatCurrency, capitalize } from '../../lib/utils'

const PAGE_SIZE = 20

export function OutstandingReportPage() {
  const [academicYears, setAcademicYears] = useState<{ id: number; name: string }[]>([])
  const [classes, setClasses] = useState<{ id: number; name: string }[]>([])
  const [selectedYearId, setSelectedYearId] = useState('')
  const [selectedClassId, setSelectedClassId] = useState('')
  const [report, setReport] = useState<OutstandingReportItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const fetchIdRef = useRef(0)

  useEffect(() => {
    academicYearApi.list({ size: 100 }).then((r) => {
      setAcademicYears(r.items.map((y) => ({ id: y.id, name: y.name })))
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!selectedYearId) { setClasses([]); return }
    classApi.list({ academic_year_id: Number(selectedYearId), size: 100 }).then((r) => {
      setClasses(r.items.map((c) => ({ id: c.id, name: c.name })))
    }).catch(() => {})
  }, [selectedYearId])

  const fetchReport = useCallback(async () => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string | number | boolean | undefined | null> = {
        academic_year_id: Number(selectedYearId),
      }
      if (selectedClassId) params.class_id = Number(selectedClassId)

      const result = await feeReportApi.getOutstandingReport(params as any)
      if (fetchId === fetchIdRef.current) setReport(result)
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load report')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [selectedYearId, selectedClassId])

  const paginated = report.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const totalPages = Math.ceil(report.length / PAGE_SIZE)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Outstanding Fees Report</h1>
        <p className="text-gray-500 mt-1">Students with outstanding fee balances</p>
      </div>

      <Card>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Academic Year</label>
            <Select
              options={academicYears.map((y) => ({ value: String(y.id), label: y.name }))}
              value={selectedYearId}
              onChange={(e) => { setSelectedYearId(e.target.value); setPage(1) }}
              placeholder="Select year"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Class (optional)</label>
            <Select
              options={classes.map((c) => ({ value: String(c.id), label: c.name }))}
              value={selectedClassId}
              onChange={(e) => { setSelectedClassId(e.target.value); setPage(1) }}
              placeholder="All classes"
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
          <p className="text-sm text-gray-500 mb-4">{report.length} student{report.length !== 1 ? 's' : ''} with outstanding fees</p>
          <Table
            columns={[
              { key: 'student_number', header: 'Student #' },
              { key: 'student_name', header: 'Name' },
              { key: 'class_name', header: 'Class' },
              {
                key: 'total_fees', header: 'Total Fees',
                render: (r: OutstandingReportItem) => formatCurrency(r.total_fees),
              },
              {
                key: 'total_paid', header: 'Paid',
                render: (r: OutstandingReportItem) => (
                  <span className="text-green-600">{formatCurrency(r.total_paid)}</span>
                ),
              },
              {
                key: 'outstanding', header: 'Outstanding',
                render: (r: OutstandingReportItem) => (
                  <span className="text-red-600 font-semibold">{formatCurrency(r.outstanding)}</span>
                ),
              },
              {
                key: 'status', header: 'Status',
                render: (r: OutstandingReportItem) => (
                  <div className="space-x-1">
                    {r.unpaid_count > 0 && <Badge variant="danger">{r.unpaid_count} unpaid</Badge>}
                    {r.partially_paid_count > 0 && <Badge variant="warning">{r.partially_paid_count} partial</Badge>}
                  </div>
                ),
              },
            ]}
            data={paginated}
            keyExtractor={(r) => r.student_id}
            emptyMessage="No outstanding fees found."
          />
          <Pagination
            page={page}
            size={PAGE_SIZE}
            total={report.length}
            pages={totalPages}
            onPageChange={setPage}
            onSizeChange={() => {}}
          />
        </Card>
      )}

      {!loading && !error && report.length === 0 && selectedYearId && (
        <Card>
          <p className="text-gray-500 text-center py-4">No outstanding fees found. All students are up to date.</p>
        </Card>
      )}
    </div>
  )
}

export default OutstandingReportPage