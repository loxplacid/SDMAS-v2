import { api } from '../client/http-client'

// ── Types ─────────────────────────────────────────────────────────────

export interface ReportCardSubject {
  subject_id: number
  subject_name: string
  subject_code: string
  marks_obtained: number | null
  max_marks: number
  grade: string | null
  grade_point: number | null
  remarks: string | null
}

export interface ReportCardTerm {
  term_id: number | null
  term_name: string
  subjects: ReportCardSubject[]
  total_marks: number
  total_max_marks: number
  percentage: number | null
  grade_point_average: number | null
}

export interface AttendanceSummaryOut {
  total: number
  present: number
  absent: number
  late: number
  excused: number
  percentage: number
}

export interface StudentReportCard {
  student_id: number
  student_name: string
  student_number: string
  class_name: string | null
  section_name: string | null
  academic_year_name: string
  term_filter: string | null
  terms: ReportCardTerm[]
  overall_percentage: number | null
  overall_grade_point_average: number | null
  attendance: AttendanceSummaryOut
  teacher_remarks: string[]
}

export interface MarksheetCell {
  subject_id: number
  subject_name: string
  subject_code: string
  marks_obtained: number | null
  max_marks: number
  grade: string | null
  grade_point: number | null
}

export interface ClassMarksheetRow {
  student_id: number
  student_name: string
  student_number: string
  subjects: MarksheetCell[]
  total_marks: number
  max_marks: number
  percentage: number | null
  grade_point_average: number | null
  attendance_percentage: number | null
}

export interface ClassMarksheet {
  class_id: number
  class_name: string
  academic_year_name: string
  term_filter: string | null
  subjects: { id: number; name: string; code: string }[]
  rows: ClassMarksheetRow[]
}

export interface ReportCardQuery {
  academic_year_id: number
  term_id?: number | null
}

// ── API client ────────────────────────────────────────────────────────

const BASE = '/api/report-cards'

export const reportCardsApi = {
  getStudentCard: (studentId: number, params: ReportCardQuery) =>
    api.get<StudentReportCard>(
      `${BASE}/students/${studentId}`,
      { academic_year_id: params.academic_year_id, term_id: params.term_id ?? null },
    ),

  getClassMarksheet: (classId: number, params: ReportCardQuery) =>
    api.get<ClassMarksheet>(
      `${BASE}/classes/${classId}`,
      { academic_year_id: params.academic_year_id, term_id: params.term_id ?? null },
    ),

  /** Download the student report card as a PDF file. */
  downloadStudentCardPdf: async (studentId: number, params: ReportCardQuery) => {
    await downloadPdf(`${BASE}/students/${studentId}/pdf`, params, `report-card-${studentId}.pdf`)
  },

  /** Download the class marksheet as a PDF file. */
  downloadClassMarksheetPdf: async (classId: number, params: ReportCardQuery) => {
    await downloadPdf(`${BASE}/classes/${classId}/pdf`, params, `marksheet-class-${classId}.pdf`)
  },
}

async function downloadPdf(
  path: string,
  params: ReportCardQuery,
  filename: string,
): Promise<void> {
  const query = new URLSearchParams()
  query.set('academic_year_id', String(params.academic_year_id))
  if (params.term_id) query.set('term_id', String(params.term_id))

  // Same auth/token flow as the shared http-client.
  const { getAccessToken } = await import('../client/http-client')
  const token = getAccessToken()
  const res = await fetch(`${path}?${query.toString()}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) {
    let detail = `Download failed (${res.status})`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : detail
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
