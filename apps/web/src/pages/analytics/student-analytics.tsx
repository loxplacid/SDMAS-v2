import { useState, useEffect, useCallback, useRef } from 'react'
import { academicYearApi } from '../../api/academic/academic-year-api'
import { studentAnalyticsApi } from '../../api/analytics/student-analytics-api'
import type { StudentOverview, StudentsByClass, StudentsBySection, EnrollmentTrend } from '../../api/analytics/types'
import { Card, Loading, ErrorState, Table } from '../../components/ui'
import { KpiCard } from '../../components/analytics/kpi-card'
import { AnalyticsFilterBar } from '../../components/analytics/analytics-filter-bar'
import { StudentDistributionChart } from '../../components/analytics/student-distribution-chart'

export function StudentAnalyticsPage() {
  const [academicYears, setAcademicYears] = useState<{ value: string; label: string }[]>([])
  const [classes, setClasses] = useState<{ value: string; label: string }[]>([])
  const [sections, setSections] = useState<{ value: string; label: string }[]>([])
  const [selectedYearId, setSelectedYearId] = useState('')
  const [selectedClassId, setSelectedClassId] = useState('')
  const [selectedSectionId, setSelectedSectionId] = useState('')

  const [overview, setOverview] = useState<StudentOverview | null>(null)
  const [byClass, setByClass] = useState<StudentsByClass[]>([])
  const [bySection, setBySection] = useState<StudentsBySection[]>([])
  const [enrollmentTrends, setEnrollmentTrends] = useState<EnrollmentTrend[]>([])

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
    import('../../api/academic/class-api').then(({ classApi }) => {
      classApi.list({ academic_year_id: Number(selectedYearId), size: 100 }).then(r => {
        setClasses(r.items.map(c => ({ value: String(c.id), label: c.name })))
      }).catch(() => {})
    })
  }, [selectedYearId])

  const fetchData = useCallback(async () => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)

    try {
      const params: Record<string, any> = {}
      if (selectedYearId) params.academic_year_id = Number(selectedYearId)
      if (selectedClassId) params.class_id = Number(selectedClassId)

      const [ov, bc, bs, et] = await Promise.all([
        studentAnalyticsApi.getOverview(),
        studentAnalyticsApi.getByClass(params),
        studentAnalyticsApi.getBySection(params),
        studentAnalyticsApi.getEnrollmentTrends().catch(() => [] as EnrollmentTrend[]),
      ])

      if (fetchId === fetchIdRef.current) {
        setOverview(ov)
        setByClass(bc)
        setBySection(bs)
        setEnrollmentTrends(et)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load analytics')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [selectedYearId, selectedClassId])

  useEffect(() => { fetchData() }, [fetchData])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">Student Analytics</h1>
        <p className="text-[var(--color-text-tertiary)] mt-1">Student population metrics and distribution</p>
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
          showGranularity={false}
        />
      </Card>

      {error && <ErrorState message={error} onRetry={fetchData} />}

      {loading ? (
        <Loading text="Loading analytics..." />
      ) : (
        <>
          {overview && (
            <div className="grid grid-cols-3 gap-3">
              <KpiCard title="Total Students" value={overview.total_students} color="blue" />
              <KpiCard title="Active" value={overview.active_students} color="green" />
              <KpiCard title="Inactive" value={overview.inactive_students} color="red" />
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card title="Students by Class">
              <StudentDistributionChart data={byClass} loading={false} />
            </Card>
            {enrollmentTrends.length > 0 && (
              <Card title="Enrollment Trends">
                <Table
                  columns={[
                    { key: 'academic_year_name', header: 'Academic Year' },
                    { key: 'enrollment_count', header: 'Enrolled Students' },
                  ]}
                  data={enrollmentTrends}
                  keyExtractor={(r) => r.academic_year_id}
                  emptyMessage="No enrollment data."
                />
              </Card>
            )}
          </div>

          {bySection.length > 0 && (
            <Card title="Students by Section">
              <Table
                columns={[
                  { key: 'section_name', header: 'Section' },
                  { key: 'class_name', header: 'Class' },
                  { key: 'student_count', header: 'Students' },
                ]}
                data={bySection}
                keyExtractor={(r) => r.section_id}
                emptyMessage="No section data."
              />
            </Card>
          )}
        </>
      )}
    </div>
  )
}

export default StudentAnalyticsPage
