import { useState, useEffect, useCallback, useRef } from 'react'
import { academicYearApi } from '../../api/academic/academic-year-api'
import { classApi } from '../../api/academic/class-api'
import { sectionApi } from '../../api/academic/section-api'
import { attendanceReportApi } from '../../api/reports/attendance-reports'
import type { ClassAttendanceSummaryReport, SectionAttendanceSummaryReport } from '../../api/reports/types'
import { Card, Select, Button, ErrorState, Badge, Table, AnimatedCount } from '../../components/ui'
import { useExport } from '../../hooks/use-export'

export function AttendanceReportPage() {
  const [academicYears, setAcademicYears] = useState<{ id: number; name: string }[]>([])
  const [classes, setClasses] = useState<{ id: number; name: string }[]>([])
  const [sections, setSections] = useState<{ id: number; name: string }[]>([])

  const [selectedYearId, setSelectedYearId] = useState('')
  const [selectedClassId, setSelectedClassId] = useState('')
  const [selectedSectionId, setSelectedSectionId] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [reportType, setReportType] = useState('class')

  const [report, setReport] = useState<ClassAttendanceSummaryReport | SectionAttendanceSummaryReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)
  const { exportPDF, exportExcel, exporting } = useExport()

  useEffect(() => {
    academicYearApi.list({ size: 100 }).then((r) => {
      setAcademicYears(r.items.map((y) => ({ id: y.id, name: y.name })))
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!selectedYearId) { setClasses([]); setSections([]); return }
    classApi.list({ academic_year_id: Number(selectedYearId), size: 100 }).then((r) => {
      setClasses(r.items.map((c) => ({ id: c.id, name: c.name })))
    }).catch(() => {})
  }, [selectedYearId])

  useEffect(() => {
    if (!selectedClassId) { setSections([]); return }
    sectionApi.list({ class_id: Number(selectedClassId), size: 100 }).then((r) => {
      setSections(r.items.map((s) => ({ id: s.id, name: s.name })))
    }).catch(() => {})
  }, [selectedClassId])

  const fetchReport = useCallback(async () => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)
    setReport(null)

    try {
      const params: Record<string, string | number | boolean | undefined | null> = {}
      if (selectedYearId) params.academic_year_id = Number(selectedYearId)
      if (startDate) params.start_date = startDate
      if (endDate) params.end_date = endDate

      let result: ClassAttendanceSummaryReport | SectionAttendanceSummaryReport
      if (reportType === 'class' && selectedClassId) {
        result = await attendanceReportApi.getClassReport(Number(selectedClassId), params)
      } else if (reportType === 'section' && selectedSectionId) {
        result = await attendanceReportApi.getSectionReport(Number(selectedSectionId), params)
      } else {
        setError('Please select a class or section');
        setLoading(false); return
      }

      if (fetchId === fetchIdRef.current) setReport(result)
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load report')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [reportType, selectedYearId, selectedClassId, selectedSectionId, startDate, endDate])

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <div className="text-[var(--color-brand-accent)] text-xs font-semibold uppercase tracking-wider">Reports</div>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)] mt-1">Attendance Report</h1>
        <p className="text-sm text-[var(--color-text-tertiary)] mt-1">View attendance summary for a class or section</p>
      </div>

      <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">Report Type</label>
            <Select
              options={[{ value: 'class', label: 'By Class' }, { value: 'section', label: 'By Section' }]}
              value={reportType}
              onChange={(e) => setReportType(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">Academic Year</label>
            <Select
              options={academicYears.map((y) => ({ value: String(y.id), label: y.name }))}
              value={selectedYearId}
              onChange={(e) => setSelectedYearId(e.target.value)}
              placeholder="Select year"
            />
          </div>
          {reportType === 'class' ? (
            <div>
              <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">Class</label>
              <Select
                options={classes.map((c) => ({ value: String(c.id), label: c.name }))}
                value={selectedClassId}
                onChange={(e) => setSelectedClassId(e.target.value)}
                placeholder="Select class"
              />
            </div>
          ) : (
            <div>
              <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">Section</label>
              <Select
                options={sections.map((s) => ({ value: String(s.id), label: s.name }))}
                value={selectedSectionId}
                onChange={(e) => setSelectedSectionId(e.target.value)}
                placeholder="Select section"
              />
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
        <div className="mt-4">
          <Button onClick={fetchReport} loading={loading}>Generate Report</Button>
        </div>
      </Card>

      {error && <ErrorState message={error} onRetry={fetchReport} />}

      {loading && <div className="h-48 bg-[var(--color-surface)] rounded-xl animate-pulse" />}

      {report && (
        <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Report Results</h2>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                loading={exporting === 'pdf'}
                onClick={() => {
                  const r = report as any
                  const summaryCols = [
                    { key: 'metric', header: 'Metric' },
                    { key: 'value', header: 'Value', render: (row: any) => String(row.value) },
                  ]
                  const summaryData = [
                    { metric: 'Total Students', value: r.total_students },
                    { metric: 'Total Records', value: r.total_records },
                    { metric: 'Present', value: r.present },
                    { metric: 'Absent', value: r.absent },
                    { metric: 'Late', value: r.late },
                    { metric: 'Excused', value: r.excused },
                    { metric: 'Present %', value: r.present_percentage },
                  ]
                  exportPDF('Attendance Report', summaryCols, summaryData, 'attendance-report')
                }}
              >
                Export PDF
              </Button>
              <Button
                variant="outline"
                size="sm"
                loading={exporting === 'excel'}
                onClick={() => {
                  const r = report as any
                  const summaryCols = [
                    { key: 'metric', header: 'Metric' },
                    { key: 'value', header: 'Value', render: (row: any) => String(row.value) },
                  ]
                  const summaryData = [
                    { metric: 'Total Students', value: r.total_students },
                    { metric: 'Total Records', value: r.total_records },
                    { metric: 'Present', value: r.present },
                    { metric: 'Absent', value: r.absent },
                    { metric: 'Late', value: r.late },
                    { metric: 'Excused', value: r.excused },
                    { metric: 'Present %', value: r.present_percentage },
                  ]
                  exportExcel('Attendance Report', summaryCols, summaryData, 'attendance-report')
                }}
              >
                Export Excel
              </Button>
            </div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
            <div>
              <p className="text-sm text-[var(--color-text-tertiary)]">Students</p>
              <p className="text-2xl font-bold"><AnimatedCount value={report.total_students} duration={800} /></p>
            </div>
            <div>
              <p className="text-sm text-[var(--color-text-tertiary)]">Total Records</p>
              <p className="text-2xl font-bold"><AnimatedCount value={report.total_records} duration={800} /></p>
            </div>
            <div>
              <p className="text-sm text-[var(--color-text-tertiary)]">Present</p>
              <p className="text-2xl font-bold text-green-600"><AnimatedCount value={report.present} duration={800} /></p>
            </div>
            <div>
              <p className="text-sm text-[var(--color-text-tertiary)]">Absent</p>
              <p className="text-2xl font-bold text-red-600"><AnimatedCount value={report.absent} duration={800} /></p>
            </div>
            <div>
              <p className="text-sm text-[var(--color-text-tertiary)]">Present %</p>
              <p className="text-2xl font-bold text-blue-600"><AnimatedCount value={report.present_percentage} duration={800} suffix="%" /></p>
            </div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            <div>
              <p className="text-sm text-[var(--color-text-tertiary)]">Late</p>
              <p className="text-xl font-semibold text-yellow-600"><AnimatedCount value={report.late} duration={800} /></p>
            </div>
            <div>
              <p className="text-sm text-[var(--color-text-tertiary)]">Excused</p>
              <p className="text-xl font-semibold text-purple-600"><AnimatedCount value={report.excused} duration={800} /></p>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}

export default AttendanceReportPage