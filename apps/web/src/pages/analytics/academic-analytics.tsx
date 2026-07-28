import { useState, useEffect, useCallback, useRef } from 'react'
import { academicAnalyticsApi } from '../../api/analytics/academic-analytics-api'
import type { AcademicOverview, TeacherWorkload, SubjectDistribution } from '../../api/analytics/types'
import { Card, Loading, ErrorState, Table } from '../../components/ui'
import { KpiCard } from '../../components/analytics/kpi-card'

export function AcademicAnalyticsPage() {
  const [overview, setOverview] = useState<AcademicOverview | null>(null)
  const [teacherWorkload, setTeacherWorkload] = useState<TeacherWorkload[]>([])
  const [subjects, setSubjects] = useState<SubjectDistribution[]>([])

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  const fetchData = useCallback(async () => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)

    try {
      const [ov, tw, sd] = await Promise.all([
        academicAnalyticsApi.getOverview(),
        academicAnalyticsApi.getTeacherWorkload().catch(() => [] as TeacherWorkload[]),
        academicAnalyticsApi.getSubjectDistribution().catch(() => [] as SubjectDistribution[]),
      ])

      if (fetchId === fetchIdRef.current) {
        setOverview(ov)
        setTeacherWorkload(tw)
        setSubjects(sd)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load analytics')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Academic Analytics</h1>
        <p className="text-gray-500 mt-1">Academic structure and teacher metrics</p>
      </div>

      {error && <ErrorState message={error} onRetry={fetchData} />}

      {loading ? (
        <Loading text="Loading analytics..." />
      ) : (
        <>
          {overview && (
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
              <KpiCard title="Active Year" value={overview.active_academic_year || 'N/A'} color="blue" />
              <KpiCard title="Classes" value={overview.total_classes} color="green" />
              <KpiCard title="Sections" value={overview.total_sections} color="purple" />
              <KpiCard title="Teachers" value={overview.total_teachers} color="indigo" />
              <KpiCard title="Subjects" value={overview.total_subjects} color="yellow" />
            </div>
          )}

          {teacherWorkload.length > 0 && (
            <Card title="Teacher Workload">
              <Table
                columns={[
                  { key: 'teacher_name', header: 'Teacher' },
                  { key: 'employee_number', header: 'Employee #' },
                  { key: 'assignment_count', header: 'Assignments' },
                  { key: 'subjects', header: 'Subjects', render: (r: TeacherWorkload) => r.subjects.join(', ') || '-' },
                  { key: 'classes', header: 'Classes', render: (r: TeacherWorkload) => r.classes.join(', ') || '-' },
                ]}
                data={teacherWorkload}
                keyExtractor={(r) => r.teacher_id}
                emptyMessage="No teachers found."
              />
            </Card>
          )}

          {subjects.length > 0 && (
            <Card title="Subject Distribution">
              <Table
                columns={[
                  { key: 'subject_name', header: 'Subject' },
                  { key: 'subject_code', header: 'Code' },
                  { key: 'assignment_count', header: 'Assignments' },
                ]}
                data={subjects}
                keyExtractor={(r) => r.subject_id}
                emptyMessage="No subjects found."
              />
            </Card>
          )}
        </>
      )}
    </div>
  )
}

export default AcademicAnalyticsPage
