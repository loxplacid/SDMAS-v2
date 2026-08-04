import { useState, useEffect, useCallback } from 'react'
import {
  Card, TabGroup, Button, Select, Input, ErrorState, Badge, EmptyState,
} from '../../components/ui'
import { academicYearApi } from '../../api/academic/academic-year-api'
import { classApi } from '../../api/academic/class-api'
import { termApi } from '../../api/academic/term-api'
import { studentApi } from '../../api/student/student-api'
import { reportCardsApi, type StudentReportCard, type ClassMarksheet } from '../../api/report-cards/report-cards-api'
import { cn } from '../../lib/utils'

// ── Shared selectors ──────────────────────────────────────────────────

function useAcademicYears() {
  const [years, setYears] = useState<{ id: number; name: string }[]>([])
  useEffect(() => {
    academicYearApi.list({ size: 100 }).then((r) => setYears(r.items.map((y) => ({ id: y.id, name: y.name })))).catch(() => {})
  }, [])
  return years
}

// ── Student Report Card tab ───────────────────────────────────────────

function StudentCardTab() {
  const years = useAcademicYears()
  const [yearId, setYearId] = useState('')
  const [termId, setTermId] = useState('')
  const [terms, setTerms] = useState<{ id: number; name: string }[]>([])
  const [studentQuery, setStudentQuery] = useState('')
  const [students, setStudents] = useState<{ id: number; name: string; number: string }[]>([])
  const [studentId, setStudentId] = useState('')
  const [card, setCard] = useState<StudentReportCard | null>(null)
  const [loading, setLoading] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!yearId) { setTerms([]); return }
    termApi.listByYear(Number(yearId), { size: 100 })
      .then((r) => setTerms(r.items.map((t) => ({ id: t.id, name: t.name }))))
      .catch(() => {})
  }, [yearId])

  const searchStudents = useCallback(async (q: string) => {
    setStudentQuery(q)
    if (!q.trim()) { setStudents([]); return }
    try {
      const r = await studentApi.list({ search: q.trim(), size: 20 })
      setStudents(r.items.map((s) => ({
        id: s.id,
        name: `${s.first_name} ${s.last_name}`,
        number: s.student_number,
      })))
    } catch { setStudents([]) }
  }, [])

  const generate = async () => {
    if (!yearId || !studentId) { setError('Select an academic year and a student'); return }
    setLoading(true); setError(null); setCard(null)
    try {
      setCard(await reportCardsApi.getStudentCard(Number(studentId), {
        academic_year_id: Number(yearId),
        term_id: termId ? Number(termId) : null,
      }))
    } catch (err: any) {
      setError(err?.detail || 'Failed to load report card')
    } finally { setLoading(false) }
  }

  const download = async () => {
    if (!card) return
    setDownloading(true)
    try {
      await reportCardsApi.downloadStudentCardPdf(card.student_id, {
        academic_year_id: Number(yearId),
        term_id: termId ? Number(termId) : null,
      })
    } catch (err: any) {
      setError(err?.detail || err?.message || 'Download failed')
    } finally { setDownloading(false) }
  }

  return (
    <div className="space-y-6">
      <Card title="Select Student" subtitle="Generate a report card for one student">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <Select
              label="Academic Year"
              options={years.map((y) => ({ value: String(y.id), label: y.name }))}
              value={yearId}
              onChange={(e) => { setYearId(e.target.value); setStudentId(''); setCard(null) }}
              placeholder="Select year"
            />
          </div>
          <div>
            <Select
              label="Term (optional)"
              options={terms.map((t) => ({ value: String(t.id), label: t.name }))}
              value={termId}
              onChange={(e) => { setTermId(e.target.value); setCard(null) }}
              placeholder="All terms"
            />
          </div>
          <div className="lg:col-span-2">
            <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">Student</label>
            <div className="relative">
              <Input
                placeholder="Search by name or student #..."
                value={studentQuery}
                onChange={(e) => searchStudents(e.target.value)}
              />
              {students.length > 0 && (
                <div className="absolute z-20 mt-1 w-full max-h-56 overflow-y-auto rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-lg">
                  {students.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      onClick={() => { setStudentId(String(s.id)); setStudentQuery(`${s.name} (${s.number})`); setStudents([]); setCard(null) }}
                      className="w-full text-left px-3 py-2 text-sm hover:bg-[var(--color-surface-hover)] transition-colors"
                    >
                      <span className="font-medium">{s.name}</span>
                      <span className="ml-2 text-xs text-[var(--color-text-tertiary)]">#{s.number}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
        <div className="mt-4">
          <Button onClick={generate} loading={loading}>Generate Report Card</Button>
        </div>
      </Card>

      {error && <ErrorState message={error} onRetry={generate} />}

      {card && (
        <Card className="print:shadow-none">
          <div className="flex items-start justify-between gap-4 mb-4 print:hidden">
            <div>
              <h2 className="text-lg font-semibold">Report Card</h2>
              <p className="text-sm text-[var(--color-text-tertiary)]">Generated from grade records, attendance and teacher remarks</p>
            </div>
            <Button variant="outline" size="sm" loading={downloading} onClick={download}>Download PDF</Button>
          </div>

          {/* Student identity */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
            {[
              { label: 'Student', value: card.student_name },
              { label: 'Roll No.', value: card.student_number },
              { label: 'Class', value: card.class_name || '—' },
              { label: 'Section', value: card.section_name || '—' },
              { label: 'Academic Year', value: card.academic_year_name },
              { label: 'Term', value: card.term_filter || 'All Terms' },
            ].map((f) => (
              <div key={f.label}>
                <p className="text-xs text-[var(--color-text-tertiary)]">{f.label}</p>
                <p className="text-sm font-semibold text-[var(--color-text-primary)] mt-0.5">{f.value}</p>
              </div>
            ))}
          </div>

          {/* Terms / subjects */}
          {card.terms.length === 0 ? (
            <EmptyState title="No grades recorded" description="No grade records exist for this student and term." />
          ) : (
            card.terms.map((term) => (
              <div key={term.term_name} className="mb-6">
                <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
                  {term.term_name}
                  <Badge variant="info">{term.percentage != null ? `${term.percentage}%` : '—'}</Badge>
                  <Badge variant="success">{term.grade_point_average != null ? `GPA ${term.grade_point_average}` : '—'}</Badge>
                </h3>
                <div className="overflow-x-auto rounded-xl border border-[var(--color-border)]">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-[var(--color-surface-hover)] text-left text-xs uppercase tracking-wider text-[var(--color-text-muted)]">
                        <th className="px-3 py-2">Subject</th>
                        <th className="px-3 py-2">Marks</th>
                        <th className="px-3 py-2">Max</th>
                        <th className="px-3 py-2">Grade</th>
                        <th className="px-3 py-2">Grade Pt.</th>
                        <th className="px-3 py-2">Remarks</th>
                      </tr>
                    </thead>
                    <tbody>
                      {term.subjects.map((s) => (
                        <tr key={s.subject_id} className="border-t border-[var(--color-border)] hover:bg-[var(--color-surface-hover)]/50 transition-colors">
                          <td className="px-3 py-2 font-medium">{s.subject_name}</td>
                          <td className="px-3 py-2">{s.marks_obtained != null ? s.marks_obtained : '—'}</td>
                          <td className="px-3 py-2 text-[var(--color-text-muted)]">{s.max_marks}</td>
                          <td className="px-3 py-2"><Badge variant={s.grade === 'A' ? 'success' : 'info'}>{s.grade || '—'}</Badge></td>
                          <td className="px-3 py-2">{s.grade_point != null ? s.grade_point : '—'}</td>
                          <td className="px-3 py-2 text-[var(--color-text-muted)]">{s.remarks || '—'}</td>
                        </tr>
                      ))}
                      <tr className="border-t border-[var(--color-border)] bg-[var(--color-surface-hover)]/60 font-semibold">
                        <td className="px-3 py-2">Total</td>
                        <td className="px-3 py-2">{term.total_marks}</td>
                        <td className="px-3 py-2 text-[var(--color-text-muted)]">{term.total_max_marks}</td>
                        <td className="px-3 py-2" colSpan={3} />
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            ))
          )}

          {/* Overall + attendance */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
            <div className="rounded-xl border border-[var(--color-border)] p-4">
              <p className="text-xs text-[var(--color-text-tertiary)]">Overall Percentage</p>
              <p className="text-2xl font-bold text-[var(--color-brand-accent)] mt-1">
                {card.overall_percentage != null ? `${card.overall_percentage}%` : '—'}
              </p>
            </div>
            <div className="rounded-xl border border-[var(--color-border)] p-4">
              <p className="text-xs text-[var(--color-text-tertiary)]">Overall GPA</p>
              <p className="text-2xl font-bold text-[var(--color-success)] mt-1">
                {card.overall_grade_point_average != null ? card.overall_grade_point_average : '—'}
              </p>
            </div>
            <div className="rounded-xl border border-[var(--color-border)] p-4">
              <p className="text-xs text-[var(--color-text-tertiary)]">Attendance</p>
              <p className="text-2xl font-bold text-[var(--color-text-primary)] mt-1">
                {card.attendance.present}/{card.attendance.total}
                <span className="text-sm font-medium text-[var(--color-text-tertiary)] ml-1">
                  ({card.attendance.percentage}%)
                </span>
              </p>
              <p className="text-xs text-[var(--color-text-tertiary)] mt-1">
                {card.attendance.absent} absent · {card.attendance.late} late · {card.attendance.excused} excused
              </p>
            </div>
          </div>

          {/* Teacher remarks */}
          {card.teacher_remarks.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold mb-2">Teacher Remarks</h3>
              <ul className="space-y-1.5">
                {card.teacher_remarks.map((r, i) => (
                  <li key={i} className="text-sm text-[var(--color-text-muted)] flex gap-2">
                    <span className="text-[var(--color-brand-accent)]">•</span>{r}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      )}
    </div>
  )
}

// ── Class Marksheet tab ───────────────────────────────────────────────

function ClassMarksheetTab() {
  const years = useAcademicYears()
  const [yearId, setYearId] = useState('')
  const [termId, setTermId] = useState('')
  const [terms, setTerms] = useState<{ id: number; name: string }[]>([])
  const [classes, setClasses] = useState<{ id: number; name: string }[]>([])
  const [classId, setClassId] = useState('')
  const [marksheet, setMarksheet] = useState<ClassMarksheet | null>(null)
  const [loading, setLoading] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!yearId) { setTerms([]); setClasses([]); return }
    termApi.listByYear(Number(yearId), { size: 100 })
      .then((r) => setTerms(r.items.map((t) => ({ id: t.id, name: t.name }))))
      .catch(() => {})
    classApi.list({ academic_year_id: Number(yearId), size: 100 })
      .then((r) => setClasses(r.items.map((c) => ({ id: c.id, name: c.name }))))
      .catch(() => {})
  }, [yearId])

  const generate = async () => {
    if (!yearId || !classId) { setError('Select an academic year and a class'); return }
    setLoading(true); setError(null); setMarksheet(null)
    try {
      setMarksheet(await reportCardsApi.getClassMarksheet(Number(classId), {
        academic_year_id: Number(yearId),
        term_id: termId ? Number(termId) : null,
      }))
    } catch (err: any) {
      setError(err?.detail || 'Failed to load marksheet')
    } finally { setLoading(false) }
  }

  const download = async () => {
    if (!marksheet) return
    setDownloading(true)
    try {
      await reportCardsApi.downloadClassMarksheetPdf(marksheet.class_id, {
        academic_year_id: Number(yearId),
        term_id: termId ? Number(termId) : null,
      })
    } catch (err: any) {
      setError(err?.detail || err?.message || 'Download failed')
    } finally { setDownloading(false) }
  }

  return (
    <div className="space-y-6">
      <Card title="Select Class" subtitle="Generate a marksheet listing every enrolled student">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <Select
              label="Academic Year"
              options={years.map((y) => ({ value: String(y.id), label: y.name }))}
              value={yearId}
              onChange={(e) => { setYearId(e.target.value); setClassId(''); setMarksheet(null) }}
              placeholder="Select year"
            />
          </div>
          <div>
            <Select
              label="Class"
              options={classes.map((c) => ({ value: String(c.id), label: c.name }))}
              value={classId}
              onChange={(e) => { setClassId(e.target.value); setMarksheet(null) }}
              placeholder="Select class"
            />
          </div>
          <div>
            <Select
              label="Term (optional)"
              options={terms.map((t) => ({ value: String(t.id), label: t.name }))}
              value={termId}
              onChange={(e) => { setTermId(e.target.value); setMarksheet(null) }}
              placeholder="All terms"
            />
          </div>
        </div>
        <div className="mt-4">
          <Button onClick={generate} loading={loading}>Generate Marksheet</Button>
        </div>
      </Card>

      {error && <ErrorState message={error} onRetry={generate} />}

      {marksheet && (
        <Card className="print:shadow-none">
          <div className="flex items-start justify-between gap-4 mb-4 print:hidden">
            <div>
              <h2 className="text-lg font-semibold">{marksheet.class_name} — Marksheet</h2>
              <p className="text-sm text-[var(--color-text-tertiary)]">
                {marksheet.academic_year_name}{marksheet.term_filter ? ` · ${marksheet.term_filter}` : ''} · {marksheet.rows.length} students
              </p>
            </div>
            <Button variant="outline" size="sm" loading={downloading} onClick={download}>Download PDF</Button>
          </div>

          {marksheet.rows.length === 0 ? (
            <EmptyState title="No students enrolled" description="No students are enrolled in this class for the selected year." />
          ) : (
            <div className="overflow-x-auto rounded-xl border border-[var(--color-border)]">
              <table className="w-full text-sm whitespace-nowrap">
                <thead>
                  <tr className="bg-[var(--color-surface-hover)] text-left text-xs uppercase tracking-wider text-[var(--color-text-muted)]">
                    <th className="px-3 py-2 sticky left-0 bg-[var(--color-surface-hover)]">Roll No.</th>
                    <th className="px-3 py-2 sticky left-0 bg-[var(--color-surface-hover)]">Student</th>
                    {marksheet.subjects.map((s) => (
                      <th key={s.id} className="px-3 py-2 text-center">{s.code || s.name}</th>
                    ))}
                    <th className="px-3 py-2">Total</th>
                    <th className="px-3 py-2">%</th>
                    <th className="px-3 py-2">GPA</th>
                    <th className="px-3 py-2">Att.</th>
                  </tr>
                </thead>
                <tbody>
                  {marksheet.rows.map((row) => (
                    <tr key={row.student_id} className="border-t border-[var(--color-border)] hover:bg-[var(--color-surface-hover)]/50 transition-colors">
                      <td className="px-3 py-2 sticky left-0 bg-[var(--color-surface)] text-[var(--color-text-tertiary)]">{row.student_number}</td>
                      <td className="px-3 py-2 sticky left-0 bg-[var(--color-surface)] font-medium">{row.student_name}</td>
                      {marksheet.subjects.map((s) => {
                        const cell = row.subjects.find((c) => c.subject_id === s.id)
                        return (
                          <td key={s.id} className="px-3 py-2 text-center" title={cell?.subject_name}>
                            {cell?.marks_obtained != null ? (
                              <span className={cn('inline-flex items-center gap-1', (cell.grade === 'A' || cell.grade === 'A+') && 'text-[var(--color-success)] font-medium')}>
                                {cell.marks_obtained}
                                <span className="text-[10px] text-[var(--color-text-tertiary)]">{cell.grade || ''}</span>
                              </span>
                            ) : <span className="text-[var(--color-text-tertiary)]">—</span>}
                          </td>
                        )
                      })}
                      <td className="px-3 py-2 font-medium">{row.total_marks}<span className="text-[var(--color-text-tertiary)]">/{row.max_marks}</span></td>
                      <td className="px-3 py-2">{row.percentage != null ? `${row.percentage}%` : '—'}</td>
                      <td className="px-3 py-2">{row.grade_point_average != null ? row.grade_point_average : '—'}</td>
                      <td className="px-3 py-2">{row.attendance_percentage != null ? `${row.attendance_percentage}%` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────

export function ReportCardsPage() {
  const [activeTab, setActiveTab] = useState('student')

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <div className="text-[var(--color-brand-accent)] text-xs font-semibold uppercase tracking-wider">Reports</div>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)] mt-1">Report Cards & Marksheets</h1>
        <p className="text-sm text-[var(--color-text-tertiary)] mt-1">
          Generate printable report cards with grades, GPA, attendance and teacher remarks
        </p>
      </div>

      <TabGroup
        tabs={[
          { id: 'student', label: 'Student Report Card' },
          { id: 'class', label: 'Class Marksheet' },
        ]}
        activeTab={activeTab}
        onChange={setActiveTab}
      />

      {activeTab === 'student' ? <StudentCardTab /> : <ClassMarksheetTab />}
    </div>
  )
}

export default ReportCardsPage
