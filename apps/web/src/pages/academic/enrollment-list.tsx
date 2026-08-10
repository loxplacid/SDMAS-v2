import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { enrollmentApi, type EnrollmentListParams } from '../../api/academic/enrollment-api'
import { studentApi } from '../../api/student/student-api'
import { academicYearApi } from '../../api/academic/academic-year-api'
import { classApi } from '../../api/academic/class-api'
import { sectionApi } from '../../api/academic/section-api'
import type { EnrollmentResponse, EnrollmentCreate, EnrollmentUpdate, StudentResponse, AcademicYearResponse, ClassResponse, SectionResponse } from '../../api/generated/types'
import { Card, Table, Pagination, Input, Select, Button, Badge, Modal, Form, Alert, EmptyState, ErrorState, useToast, PageHeader, ShortcutKey} from '../../components/ui'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'
import { ENROLLMENT_STATUSES, capitalize, plural } from '../../lib/utils'

const statusBadge: Record<string, 'success' | 'warning' | 'danger' | 'info'> = { active: 'success', inactive: 'danger' }

const columns = [
  { key: 'student_id', header: 'Student ID', render: (e: EnrollmentResponse) => `Student #${e.student_id}` },
  { key: 'academic_year_id', header: 'Year ID', render: (e: EnrollmentResponse) => `Year #${e.academic_year_id}` },
  { key: 'class_id', header: 'Class ID', render: (e: EnrollmentResponse) => e.class_id ? `Class #${e.class_id}` : '-' },
  { key: 'section_id', header: 'Section ID', render: (e: EnrollmentResponse) => e.section_id ? `Section #${e.section_id}` : '-' },
  { key: 'status', header: 'Status', render: (e: EnrollmentResponse) => <Badge variant={statusBadge[e.status] || 'default'}>{capitalize(e.status)}</Badge> },
]

export function EnrollmentListPage() {
  const navigate = useNavigate()
  const { showToast } = useToast()
  const [searchParams] = useSearchParams()
  const initialClassId = searchParams.get('classId')
  const initialSectionId = searchParams.get('sectionId')

  useKeyboardShortcut({ 'n': () => openCreateModal() }, [])
  const [data, setData] = useState<EnrollmentResponse[]>([])
  const [total, setTotal] = useState(0); const [pages, setPages] = useState(0)
  const [page, setPage] = useState(1); const [size, setSize] = useState(20)
  const [studentFilter, setStudentFilter] = useState(''); const [yearFilter, setYearFilter] = useState('')
  const [classFilter, setClassFilter] = useState(initialClassId ?? ''); const [sectionFilter, setSectionFilter] = useState(initialSectionId ?? '')
  const [loading, setLoading] = useState(true); const [error, setError] = useState<string | null>(null)
  const [students, setStudents] = useState<StudentResponse[]>([])
  const [years, setYears] = useState<AcademicYearResponse[]>([])
  const [classes, setClasses] = useState<ClassResponse[]>([])
  const [sections, setSections] = useState<SectionResponse[]>([])

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<EnrollmentResponse | null>(null)
  const [formData, setFormData] = useState<{ student_id: number | null; academic_year_id: number | null; class_id: number | null; section_id: number | null; status?: string | null }>({ student_id: null, academic_year_id: null, class_id: null, section_id: null })
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false); const [apiError, setApiError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  useEffect(() => {
    Promise.all([
      studentApi.list({ size: 200 }).then((r) => setStudents(r.items)).catch(() => {}),
      academicYearApi.list({ size: 100 }).then((r) => setYears(r.items)).catch(() => {}),
      classApi.list({ size: 200 }).then((r) => setClasses(r.items)).catch(() => {}),
      sectionApi.list({ size: 200 }).then((r) => setSections(r.items)).catch(() => {}),
    ])
  }, [])

  const fetch = useCallback(async (params: EnrollmentListParams) => {
    const fetchId = ++fetchIdRef.current; setLoading(true); setError(null)
    try {
      const result = await enrollmentApi.list(params)
      if (fetchId === fetchIdRef.current) { setData(result.items); setTotal(result.total); setPages(result.pages); setPage(result.page) }
    } catch (err: any) { if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load enrollments')
    } finally { if (fetchId === fetchIdRef.current) setLoading(false) }
  }, [])

  useEffect(() => { fetch({ page, size, student_id: studentFilter ? Number(studentFilter) : undefined, academic_year_id: yearFilter ? Number(yearFilter) : undefined, class_id: classFilter ? Number(classFilter) : undefined, section_id: sectionFilter ? Number(sectionFilter) : undefined }) }, [page, size, studentFilter, yearFilter, classFilter, sectionFilter, fetch])

  const openCreateModal = () => { setEditing(null); setFormData({ student_id: null, academic_year_id: null, class_id: null, section_id: null }); setFormErrors({}); setApiError(null); setModalOpen(true) }
  const openEditModal = (e: EnrollmentResponse) => { setEditing(e); setFormData({ student_id: e.student_id, academic_year_id: e.academic_year_id, class_id: e.class_id, section_id: e.section_id, status: e.status }); setFormErrors({}); setApiError(null); setModalOpen(true) }

  const validate = (): boolean => {
    const e: Record<string, string> = {}
    if (!formData.student_id) e.student_id = 'Student is required'
    if (!formData.academic_year_id) e.academic_year_id = 'Academic year is required'
    setFormErrors(e); return Object.keys(e).length === 0
  }

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault(); if (!validate()) return; setSaving(true); setApiError(null)
    try {
      if (editing) {
        const updated = await enrollmentApi.update(editing.id, { class_id: formData.class_id, section_id: formData.section_id, status: formData.status || null })
        setData((prev) => prev.map((e) => (e.id === updated.id ? updated : e))); showToast('Enrollment updated', 'success')
        setModalOpen(false)
      } else {
        const created = await enrollmentApi.create({ student_id: formData.student_id!, academic_year_id: formData.academic_year_id!, class_id: formData.class_id, section_id: formData.section_id })
        setData((prev) => [created, ...prev]); setTotal((t) => t + 1); showToast('Enrollment created', 'success')
        setModalOpen(false)
      }
    } catch (err: any) { setApiError(err?.detail || 'Failed to save')
    } finally { setSaving(false) }
  }

  const handleDelete = async (e: EnrollmentResponse) => {
    if (!confirm(`Delete enrollment #${e.id}?`)) return
    try { await enrollmentApi.delete(e.id); setData((prev) => prev.filter((en) => en.id !== e.id)); setTotal((t) => t - 1); showToast('Enrollment deleted', 'success')
    } catch (err: any) { showToast(err?.detail || 'Failed to delete', 'error') }
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        eyebrow="Academics"
        title="Enrollments"
        subtitle={plural(total, 'enrollment')}
        compact
        actions={
          <Button onClick={openCreateModal}>
            Add Enrollment
            <ShortcutKey>N</ShortcutKey>
          </Button>
        }
      />
      <div className="flex items-center gap-4">
        <Select options={students.slice(0, 100).map((s) => ({ value: String(s.id), label: `${s.first_name} ${s.last_name} (#${s.student_number})` }))} placeholder="All students" value={studentFilter}
          onChange={(e) => { setStudentFilter(e.target.value); setPage(1) }} />
        <Select options={years.map((y) => ({ value: String(y.id), label: y.name }))} placeholder="All years" value={yearFilter}
          onChange={(e) => { setYearFilter(e.target.value); setPage(1) }} />
        <Select options={classes.map((c) => ({ value: String(c.id), label: c.name }))} placeholder="All classes" value={classFilter}
          onChange={(e) => { setClassFilter(e.target.value); setPage(1) }} />
        <Select options={sections.map((s) => ({ value: String(s.id), label: s.name }))} placeholder="All sections" value={sectionFilter}
          onChange={(e) => { setSectionFilter(e.target.value); setPage(1) }} />
      </div>
      <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
        {error ? <ErrorState message={error} onRetry={() => fetch({ page, size, student_id: studentFilter ? Number(studentFilter) : undefined, academic_year_id: yearFilter ? Number(yearFilter) : undefined, class_id: classFilter ? Number(classFilter) : undefined, section_id: sectionFilter ? Number(sectionFilter) : undefined })} /> : (
          <>
            <Table columns={[...columns, { key: 'actions', header: 'Actions', render: (e: EnrollmentResponse) => (<div className="flex gap-2" onClick={(ev) => ev.stopPropagation()}><Button variant="ghost" size="sm" onClick={() => openEditModal(e)}>Edit</Button><Button variant="danger" size="sm" onClick={() => handleDelete(e)}>Delete</Button></div>) }]} data={data} keyExtractor={(e) => e.id} emptyMessage="No enrollments found." loading={loading} onRowClick={(e) => navigate(`/students/${e.student_id}`)} />
            <Pagination page={page} size={size} total={total} pages={pages} onPageChange={setPage} onSizeChange={(s) => { setSize(s); setPage(1) }} />
          </>
        )}
      </Card>
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Edit Enrollment' : 'Add Enrollment'}
        footer={<>            <Button variant="outline" onClick={() => setModalOpen(false)}>Cancel</Button><Button onClick={handleSubmit} loading={saving}>{editing ? 'Save Changes' : 'Create'}</Button></>}
      >
        {apiError && <Alert variant="error" onClose={() => setApiError(null)}>{apiError}</Alert>}
        <Form onSubmit={handleSubmit}>
          {!editing && (
            <>
              <Select label="Student" value={String(formData.student_id ?? '')} onChange={(e) => setFormData({ ...formData, student_id: e.target.value ? Number(e.target.value) : null })} error={formErrors.student_id}
                options={students.map((s) => ({ value: String(s.id), label: `${s.first_name} ${s.last_name} (#${s.student_number})` }))} placeholder="Select student" />
              <Select label="Academic Year" value={String(formData.academic_year_id ?? '')} onChange={(e) => setFormData({ ...formData, academic_year_id: e.target.value ? Number(e.target.value) : null })} error={formErrors.academic_year_id}
                options={years.map((y) => ({ value: String(y.id), label: y.name }))} placeholder="Select year" />
            </>
          )}
          <Select label="Class" value={String(formData.class_id ?? '')} onChange={(e) => setFormData({ ...formData, class_id: e.target.value ? Number(e.target.value) : null })}
            options={classes.map((c) => ({ value: String(c.id), label: c.name }))} placeholder="Select class (optional)" />
          <Select label="Section" value={String(formData.section_id ?? '')} onChange={(e) => setFormData({ ...formData, section_id: e.target.value ? Number(e.target.value) : null })}
            options={sections.map((s) => ({ value: String(s.id), label: s.name }))} placeholder="Select section (optional)" />
          {editing && <Select label="Status" value={formData.status ?? editing.status} onChange={(e) => setFormData({ ...formData, status: e.target.value })} options={ENROLLMENT_STATUSES.map((s) => ({ value: s, label: capitalize(s) }))} />}
        </Form>
      </Modal>
    </div>
  )
}