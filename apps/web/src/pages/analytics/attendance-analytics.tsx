import { useState, useEffect, useCallback, useRef } from 'react'
import { academicYearApi } from '../../api/academic/academic-year-api'
import { classApi } from '../../api/academic/class-api'
import { sectionApi } from '../../api/academic/section-api'
import { attendanceAnalyticsApi } from '../../api/analytics/attendance-analytics-api'
import type { AttendanceOverview, AttendanceTrend, ClassAttendanceComparison, LowAttendanceStudent, TermAttendanceAnalytics } from '../../api/analytics/types'
import { Card, Loading, ErrorState, Table } from '../../components/ui'
import { KpiCard } from '../../components/analytics/kpi-card'
import { AnalyticsFilterBar } from '../../components/analytics/analytics-filter-bar'
import { AttendanceTrendChart } from '../../components/analytics/attendance-trend-chart'
import { AttendanceStatusChart } from '../../components/analytics/attendance-status-chart'
import { ClassComparisonChart } from '../../components/analytics/class-comparison-chart'

export function AttendanceAnalyticsPage() {
  const [academicYears, setAcademicYears] = useState<{ value: string; label: string }[]>([])
  const [classes, setClasses] = useState<{ value: string; label: string }[]>([])
  const [sections, setSections] = useState<{ value: string; label: string }[]>([])
  const [selectedYearId, setSelectedYearId] = useState('')
  const [selectedClassId, setSelectedClassId] = useState('')
  const [selectedSectionId, setSelectedSectionId] = useState('')
  const [granularity, setGranularity] = useState('daily')

  const [overview, setOverview] = useState<AttendanceOverview | null>(null)
  const [trends, setTrends] = useState<AttendanceTrend | null>(null)
  const [classComparison, setClassComparison] = useState<ClassAttendanceComparison[]>([])
  const [lowAttendance, setLowAttendance] = useState<LowAttendanceStudent[]>([])
  const [termAttendance, setTermAttendance] = useState<TermAttendanceAnalytics[]>([])

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  useEffect(() => {
    academicYearApi.list({ size: 100 }).then(r => {
      setAcademicYears(r.items.map(y => ({ value: String(y.id), label: y.name })))
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!selectedYearId) { setClasses([]); return }
    classApi.list({ academic_year_id: Number(selectedYearId), size: 100 }).then(r => {
      setClasses(r.items.map(c => ({ value: String(c.id), label: c.name })))
    }).catch(() => {})
  }, [selectedYearId])

  useEffect(() => {
    if (!selectedClassId) { setSections([]); return }
    sectionApi.list({ class_id: Number(selectedClassId), size: 100 }).then(r => {
      setSections(r.items.map(s => ({ value: String(s.id), label: s.name })))
    }).catch(() => {})
  }, [selectedClassId])

  const fetchData = useCallback(async () => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)

    try {
      const params: Record<string, any> = {}
      if (selectedYearId) params.academic_year_id = Number(selectedYearId)
      if (selectedClassId) params.class_id = Number(selectedClassId)
      if (selectedSectionId) params.section_id = Number(selectedSectionId)

      const [ov, tr, cc, la, ta] = await Promise.all([
        attendanceAnalyticsApi.getOverview(params),
        attendanceAnalyticsApi.getTrends({ ...params, granularity }),
        attendanceAnalyticsApi.getClassComparison(params).catch(() => [] as ClassAttendanceComparison[]),
        attendanceAnalyticsApi.getLowAttendance(params).catch(() => [] as LowAttendanceStudent[]),
        attendanceAnalyticsApi.getTermAttendance(params).catch(() => [] as TermAttendanceAnalytics[]),
      ])

      if (fetchId === fetchIdRef.current) {
        setOverview(ov)
        setTrends(tr)
        setClassComparison(cc)
        setLowAttendance(la)
        setTermAttendance(ta)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) {
        setError(err?.detail || 'Failed to load analytics')
      }
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [selectedYearId, selectedClassId, selectedSectionId, granularity])

  useEffect(() => { fetchData() }, [fetchData])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">Attendance Analytics</h1>
        <p className="text-[var(--color-text-tertiary)] mt-1">Comprehensive attendance metrics and trends</p>
      </div>

      <Card>
        <AnalyticsFilterBar
          academicYears={academicYears}
          selectedYearId={selectedYearId}
          onYearChange={setSelectedYearId}
          classes={classes}
          selectedClassId={selectedClassId}
          onClassChange={setSelectedClassId}
          sections={sections}
          selectedSectionId={selectedSectionId}
          onSectionChange={setSelectedSectionId}
          granularity={granularity}
          onGranularityChange={setGranularity}
          showGranularity
        />
      </Card>

      {error && <ErrorState message={error} onRetry={fetchData} />}

      {loading ? (
        <Loading text="Loading analytics..." />
      ) : (
        <>
          {/* KPI Cards */}
          {overview && (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              <KpiCard title="Total Records" value={overview.total_records} color="blue" />
              <KpiCard title="Present" value={overview.present} color="green" />
              <KpiCard title="Absent" value={overview.absent} color="red" />
              <KpiCard title="Late" value={overview.late} color="yellow" />
              <KpiCard title="Attendance %" value={`${overview.attendance_percentage}%`} color="purple" />
            </div>
          )}

          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card title="Attendance Trend">
              <AttendanceTrendChart data={trends?.trend || []} granularity={trends?.granularity} loading={false} />
            </Card>
            <Card title="Attendance Status Distribution">
              <AttendanceStatusChart data={overview} loading={false} />
            </Card>
          </div>

          {/* Class Comparison */}
          {classComparison.length > 0 && (
            <Card title="Class Attendance Comparison">
              <ClassComparisonChart data={classComparison} loading={false} />
            </Card>
          )}

          {/* Term Attendance */}
          {termAttendance.length > 0 && (
            <Card title="Term Attendance">
              <Table
                columns={[
                  { key: 'term_name', header: 'Term' },
                  { key: 'total_records', header: 'Records' },
                  { key: 'present', header: 'Present' },
                  { key: 'absent', header: 'Absent' },
                  { key: 'late', header: 'Late' },
                  { key: 'excused', header: 'Excused' },
                  { key: 'attendance_percentage', header: '%', render: (r: any) => `${r.attendance_percentage}%` },
                ]}
                data={termAttendance}
                keyExtractor={(r) => r.term_id}
                emptyMessage="No term data."
              />
            </Card>
          )}

          {/* Low Attendance Alerts */}
          {lowAttendance.length > 0 && (
            <Card title={`Attendance Threshold Alert (${lowAttendance.length} students below 90%)`}>
              <Table
                columns={[
                  { key: 'student_name', header: 'Student' },
                  { key: 'student_number', header: 'Student #' },
                  { key: 'total_records', header: 'Records' },
                  { key: 'present_count', header: 'Present' },
                  { key: 'attendance_percentage', header: 'Attendance %', render: (r: any) => (
                    <span className={`font-semibold ${r.attendance_percentage < 75 ? 'text-red-600' : 'text-yellow-600'}`}>
                      {r.attendance_percentage}%
                    </span>
                  )},
                ]}
                data={lowAttendance}
                keyExtractor={(r) => r.student_id}
                emptyMessage="All students have good attendance."
              />
            </Card>
          )}

          {!overview && !error && (
            <Card>
              <p className="text-[var(--color-text-tertiary)] text-center py-8">Select filters and click "Generate Report" to view attendance analytics.</p>
            </Card>
          )}
        </>
      )}
    </div>
  )
}

export default AttendanceAnalyticsPage
