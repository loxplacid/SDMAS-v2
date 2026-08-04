import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { StudentReportCard, ClassMarksheet } from '../api/report-cards/report-cards-api'

// ── Shared hoisted mocks ─────────────────────────────────────────────
// These are re-armed in `beforeEach` because `vi.resetAllMocks()` wipes
// implementations, and the page fetches years/terms/classes/students on
// mount / selection.
const {
  academicYearListMock,
  termListMock,
  classListMock,
  studentListMock,
} = vi.hoisted(() => ({
  academicYearListMock: vi.fn(),
  termListMock: vi.fn(),
  classListMock: vi.fn(),
  studentListMock: vi.fn(),
}))

vi.mock('../api/academic/academic-year-api', () => ({
  academicYearApi: { list: (...args: unknown[]) => academicYearListMock(...args) },
}))

vi.mock('../api/academic/term-api', () => ({
  termApi: { listByYear: (...args: unknown[]) => termListMock(...args) },
}))

vi.mock('../api/academic/class-api', () => ({
  classApi: { list: (...args: unknown[]) => classListMock(...args) },
}))

vi.mock('../api/student/student-api', () => ({
  studentApi: { list: (...args: unknown[]) => studentListMock(...args) },
}))

// ── Report cards API mock ────────────────────────────────────────────

const getStudentCardMock = vi.fn()
const getClassMarksheetMock = vi.fn()
const downloadStudentPdfMock = vi.fn()
const downloadClassPdfMock = vi.fn()

vi.mock('../api/report-cards/report-cards-api', () => ({
  reportCardsApi: {
    getStudentCard: (...args: unknown[]) => getStudentCardMock(...args),
    getClassMarksheet: (...args: unknown[]) => getClassMarksheetMock(...args),
    downloadStudentCardPdf: (...args: unknown[]) => downloadStudentPdfMock(...args),
    downloadClassMarksheetPdf: (...args: unknown[]) => downloadClassPdfMock(...args),
  },
}))

// Import after mocking
const { ReportCardsPage } = await import('../pages/report-cards/report-cards')

function makeCard(overrides: Partial<StudentReportCard> = {}): StudentReportCard {
  return {
    student_id: 101,
    student_name: 'Rahul Sharma',
    student_number: 'A001',
    class_name: 'Grade 5',
    section_name: 'A',
    academic_year_name: '2026-27',
    term_filter: 'Term 1',
    terms: [
      {
        term_id: 10,
        term_name: 'Term 1',
        total_marks: 172,
        total_max_marks: 200,
        percentage: 86.0,
        grade_point_average: 8.6,
        subjects: [
          {
            subject_id: 1,
            subject_name: 'Mathematics',
            subject_code: 'MATH',
            marks_obtained: 88,
            max_marks: 100,
            grade: 'A',
            grade_point: 9.0,
            remarks: 'Excellent progress',
          },
        ],
      },
    ],
    overall_percentage: 86.0,
    overall_grade_point_average: 8.6,
    attendance: { total: 90, present: 85, absent: 3, late: 1, excused: 1, percentage: 94.4 },
    teacher_remarks: ['Good focus this term'],
    ...overrides,
  }
}

function makeMarksheet(overrides: Partial<ClassMarksheet> = {}): ClassMarksheet {
  return {
    class_id: 5,
    class_name: 'Grade 5',
    academic_year_name: '2026-27',
    term_filter: 'Term 1',
    subjects: [
      { id: 1, name: 'Mathematics', code: 'MATH' },
      { id: 2, name: 'English', code: 'ENG' },
    ],
    rows: [
      {
        student_id: 101,
        student_name: 'Rahul Sharma',
        student_number: 'A001',
        subjects: [
          { subject_id: 1, subject_name: 'Mathematics', subject_code: 'MATH', marks_obtained: 88, max_marks: 100, grade: 'A', grade_point: 9.0 },
          { subject_id: 2, subject_name: 'English', subject_code: 'ENG', marks_obtained: 84, max_marks: 100, grade: 'A', grade_point: 8.5 },
        ],
        total_marks: 172,
        max_marks: 200,
        percentage: 86.0,
        grade_point_average: 8.75,
        attendance_percentage: 94.4,
      },
    ],
    ...overrides,
  }
}

function renderPage() {
  return render(<ReportCardsPage />)
}

beforeEach(() => {
  vi.resetAllMocks()
  // Re-arm the shared list mocks after the reset.
  academicYearListMock.mockResolvedValue({
    items: [
      { id: 1, name: '2026-27' },
      { id: 2, name: '2027-28' },
    ],
  })
  termListMock.mockResolvedValue({
    items: [
      { id: 10, name: 'Term 1' },
      { id: 11, name: 'Term 2' },
    ],
  })
  classListMock.mockResolvedValue({
    items: [
      { id: 5, name: 'Grade 5' },
      { id: 6, name: 'Grade 6' },
    ],
  })
  studentListMock.mockResolvedValue({
    items: [
      { id: 101, first_name: 'Rahul', last_name: 'Sharma', student_number: 'A001' },
      { id: 102, first_name: 'Priya', last_name: 'Verma', student_number: 'A002' },
    ],
  })
})

// Pick a student via the search dropdown (shared by the student tests).
async function pickStudent() {
  const searchInput = screen.getByPlaceholderText(/Search by name or student/i)
  await userEvent.type(searchInput, 'Rahul')
  await waitFor(() => expect(screen.getByText(/Rahul Sharma/)).toBeInTheDocument())
  await userEvent.click(screen.getByText(/Rahul Sharma/))
}

describe('Report Cards page', () => {
  it('generates a student report card with grades, GPA, attendance and remarks', async () => {
    getStudentCardMock.mockResolvedValueOnce(makeCard())

    renderPage()

    await waitFor(() => expect(screen.getByText('2026-27')).toBeInTheDocument())
    await userEvent.selectOptions(screen.getByLabelText(/Academic Year/i), '1')
    // Terms load asynchronously after the year changes.
    await waitFor(() => expect(screen.getByText('Term 1')).toBeInTheDocument())
    await userEvent.selectOptions(screen.getByLabelText(/Term \(optional\)/i), '10')

    await pickStudent()
    await userEvent.click(screen.getByRole('button', { name: /Generate Report Card/i }))

    await waitFor(() => {
      expect(getStudentCardMock).toHaveBeenCalledWith(101, {
        academic_year_id: 1,
        term_id: 10,
      })
      expect(screen.getByText('Rahul Sharma')).toBeInTheDocument()
      expect(screen.getByText('88')).toBeInTheDocument()
      // "86%" appears on both the term badge and the overall stat.
      expect(screen.getAllByText('86%').length).toBeGreaterThanOrEqual(2)
      expect(screen.getByText('8.6')).toBeInTheDocument()
      expect(screen.getByText(/85\/90/)).toBeInTheDocument()
      expect(screen.getByText('Excellent progress')).toBeInTheDocument()
      expect(screen.getByText('Good focus this term')).toBeInTheDocument()
    })
  })

  it('shows an empty state when no grades are recorded', async () => {
    getStudentCardMock.mockResolvedValueOnce(makeCard({ terms: [], overall_percentage: null }))

    renderPage()

    await waitFor(() => expect(screen.getByText('2026-27')).toBeInTheDocument())
    await userEvent.selectOptions(screen.getByLabelText(/Academic Year/i), '1')
    await waitFor(() => expect(screen.getByText('Term 1')).toBeInTheDocument())
    await userEvent.selectOptions(screen.getByLabelText(/Term \(optional\)/i), '10')

    await pickStudent()
    await userEvent.click(screen.getByRole('button', { name: /Generate Report Card/i }))

    await waitFor(() => {
      expect(screen.getByText('No grades recorded')).toBeInTheDocument()
    })
  })

  it('downloads the student report card PDF', async () => {
    getStudentCardMock.mockResolvedValueOnce(makeCard())
    downloadStudentPdfMock.mockResolvedValueOnce(undefined)

    renderPage()

    await waitFor(() => expect(screen.getByText('2026-27')).toBeInTheDocument())
    await userEvent.selectOptions(screen.getByLabelText(/Academic Year/i), '1')
    await waitFor(() => expect(screen.getByText('Term 1')).toBeInTheDocument())
    await userEvent.selectOptions(screen.getByLabelText(/Term \(optional\)/i), '10')

    await pickStudent()
    await userEvent.click(screen.getByRole('button', { name: /Generate Report Card/i }))

    await waitFor(() => expect(screen.getByText('Report Card')).toBeInTheDocument())
    await userEvent.click(screen.getByRole('button', { name: /Download PDF/i }))

    await waitFor(() => {
      expect(downloadStudentPdfMock).toHaveBeenCalledWith(101, {
        academic_year_id: 1,
        term_id: 10,
      })
    })
  })

  it('generates a class marksheet listing every enrolled student', async () => {
    getClassMarksheetMock.mockResolvedValueOnce(makeMarksheet())

    renderPage()

    await userEvent.click(screen.getByRole('tab', { name: /Class Marksheet/i }))

    await waitFor(() => expect(screen.getByText('2026-27')).toBeInTheDocument())
    await userEvent.selectOptions(screen.getByLabelText(/Academic Year/i), '1')
    // Classes + terms load asynchronously after the year changes.
    await waitFor(() => expect(screen.getByText('Grade 5')).toBeInTheDocument())
    await userEvent.selectOptions(screen.getByLabelText(/Class/i), '5')
    await waitFor(() => expect(screen.getByText('Term 1')).toBeInTheDocument())
    await userEvent.selectOptions(screen.getByLabelText(/Term \(optional\)/i), '10')

    await userEvent.click(screen.getByRole('button', { name: /Generate Marksheet/i }))

    await waitFor(() => {
      expect(getClassMarksheetMock).toHaveBeenCalledWith(5, {
        academic_year_id: 1,
        term_id: 10,
      })
      expect(screen.getByText('Grade 5 — Marksheet')).toBeInTheDocument()
      expect(screen.getByText('Rahul Sharma')).toBeInTheDocument()
      // Total cell renders "172" + "/200" across two text nodes.
      expect(screen.getByText('172')).toBeInTheDocument()
      expect(screen.getByText('94.4%')).toBeInTheDocument()
    })
  })

  it('shows an empty state when no students are enrolled in the class', async () => {
    getClassMarksheetMock.mockResolvedValueOnce(makeMarksheet({ rows: [] }))

    renderPage()

    await userEvent.click(screen.getByRole('tab', { name: /Class Marksheet/i }))

    await waitFor(() => expect(screen.getByText('2026-27')).toBeInTheDocument())
    await userEvent.selectOptions(screen.getByLabelText(/Academic Year/i), '1')
    await waitFor(() => expect(screen.getByText('Grade 5')).toBeInTheDocument())
    await userEvent.selectOptions(screen.getByLabelText(/Class/i), '5')

    await userEvent.click(screen.getByRole('button', { name: /Generate Marksheet/i }))

    await waitFor(() => {
      expect(screen.getByText('No students enrolled')).toBeInTheDocument()
    })
  })

  it('downloads the class marksheet PDF', async () => {
    getClassMarksheetMock.mockResolvedValueOnce(makeMarksheet())
    downloadClassPdfMock.mockResolvedValueOnce(undefined)

    renderPage()

    await userEvent.click(screen.getByRole('tab', { name: /Class Marksheet/i }))

    await waitFor(() => expect(screen.getByText('2026-27')).toBeInTheDocument())
    await userEvent.selectOptions(screen.getByLabelText(/Academic Year/i), '1')
    await waitFor(() => expect(screen.getByText('Grade 5')).toBeInTheDocument())
    await userEvent.selectOptions(screen.getByLabelText(/Class/i), '5')

    await userEvent.click(screen.getByRole('button', { name: /Generate Marksheet/i }))

    await waitFor(() => expect(screen.getByText('Grade 5 — Marksheet')).toBeInTheDocument())
    await userEvent.click(screen.getByRole('button', { name: /Download PDF/i }))

    await waitFor(() => {
      expect(downloadClassPdfMock).toHaveBeenCalledWith(5, {
        academic_year_id: 1,
        term_id: null,
      })
    })
  })

  it('shows an error state when generation fails', async () => {
    getStudentCardMock.mockRejectedValueOnce({ detail: 'Student 101 not found' })

    renderPage()

    await waitFor(() => expect(screen.getByText('2026-27')).toBeInTheDocument())
    await userEvent.selectOptions(screen.getByLabelText(/Academic Year/i), '1')

    await pickStudent()
    await userEvent.click(screen.getByRole('button', { name: /Generate Report Card/i }))

    await waitFor(() => {
      expect(screen.getByText('Student 101 not found')).toBeInTheDocument()
    })
  })
})
