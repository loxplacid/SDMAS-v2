import { useState, useEffect, useCallback, useRef } from 'react'
import { teacherAssignmentApi, type TeacherAssignmentListParams } from '../../api/academic/teacher-assignment-api'
import { teacherApi } from '../../api/academic/teacher-api'
import { classApi } from '../../api/academic/class-api'
import { subjectApi } from '../../api/academic/subject-api'
import type { TeacherAssignmentResponse, TeacherAssignmentCreate, TeacherResponse, ClassResponse, SubjectResponse } from '../../api/generated/types'
import { Card, Table, Pagination, Input, Select, Button, Badge, Modal, Form, Alert, EmptyState, ErrorState, useToast, PageHeader, ShortcutKey} from '../../components/ui'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'
import { capitalize, plural } from '../../lib/utils'

const columns = [
  { key: 'teacher_id', header: 'Teacher ID', render: (a: TeacherAssignmentResponse) => `Teacher #${a.teacher_id}` },
  { key: 'class_id', header: 'Class ID', render: (a: TeacherAssignmentResponse) => `Class #${a.class_id}` },
  { key: 'subject_id', header: 'Subject ID', render: (a: TeacherAssignmentResponse) => a.subject_id ? `Subject #${a.subject_id}` : '-' },
  { key: 'status', header: 'Status', render: (a: TeacherAssignmentResponse) => <Badge variant="success">{capitalize(a.status)}</Badge> },
]

export function TeacherAssignmentListPage() {
  const { showToast } = useToast()

  useKeyboardShortcut({ 'n': () => openCreateModal() }, [])
  const [data, setData] = useState<TeacherAssignmentResponse[]>([])
  const [total, setTotal] = useState(0); const [pages, setPages] = useState(0)
  const [page, setPage] = useState(1); const [size, setSize] = useState(20)
  const [classFilter, setClassFilter] = useState(''); const [teacherFilter, setTeacherFilter] = useState('')
  const [loading, setLoading] = useState(true); const [error, setError] = useState<string | null>(null)
  const [teachers, setTeachers] = useState<TeacherResponse[]>([])
  const [classes, setClasses] = useState<ClassResponse[]>([])
  const [subjects, setSubjects] = useState<SubjectResponse[]>([])

  const [modalOpen, setModalOpen] = useState(false)
  const [formData, setFormData] = useState<{ teacher_id: number | null; class_id: number | null; subject_id: number | null }>({ teacher_id: null, class_id: null, subject_id: null })
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false); const [apiError, setApiError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  useEffect(() => {
    Promise.all([
      teacherApi.list({ size: 200 }).then((r) => setTeachers(r.items)).catch(() => {}),
      classApi.list({ size: 200 }).then((r) => setClasses(r.items)).catch(() => {}),
      subjectApi.list({ size: 200 }).then((r) => setSubjects(r.items)).catch(() => {}),
    ])
  }, [])

  const fetch = useCallback(async (params: TeacherAssignmentListParams) => {
    const fetchId = ++fetchIdRef.current; setLoading(true); setError(null)
    try {
      const result = await teacherAssignmentApi.list(params)
      if (fetchId === fetchIdRef.current) { setData(result.items); setTotal(result.total); setPages(result.pages); setPage(result.page) }
    } catch (err: any) { if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load assignments')
    } finally { if (fetchId === fetchIdRef.current) setLoading(false) }
  }, [])

  useEffect(() => { fetch({ page, size, class_id: classFilter ? Number(classFilter) : undefined, teacher_id: teacherFilter ? Number(teacherFilter) : undefined }) }, [page, size, classFilter, teacherFilter, fetch])

  const openCreateModal = () => { setFormData({ teacher_id: null, class_id: null, subject_id: null }); setFormErrors({}); setApiError(null); setModalOpen(true) }

  const validate = (): boolean => {
    const e: Record<string, string> = {}
    if (!formData.teacher_id) e.teacher_id = 'Teacher is required'
    if (!formData.class_id) e.class_id = 'Class is required'
    setFormErrors(e); return Object.keys(e).length === 0
  }

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault(); if (!validate()) return; setSaving(true); setApiError(null)
    try {
      const created = await teacherAssignmentApi.create({ teacher_id: formData.teacher_id!, class_id: formData.class_id!, subject_id: formData.subject_id })
      setData((prev) => [created, ...prev]); setTotal((t) => t + 1); showToast('Assignment created', 'success'); setModalOpen(false)
    } catch (err: any) { setApiError(err?.detail || 'Failed to save')
    } finally { setSaving(false) }
  }

  const handleDelete = async (a: TeacherAssignmentResponse) => {
    if (!confirm(`Delete assignment #${a.id}?`)) return
    try { await teacherAssignmentApi.delete(a.id); setData((prev) => prev.filter((item) => item.id !== a.id)); setTotal((t) => t - 1); showToast('Assignment deleted', 'success')
    } catch (err: any) { showToast(err?.detail || 'Failed to delete', 'error') }
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        eyebrow="Academics"
        title="Teacher Assignments"
        subtitle={plural(total, 'assignment')}
        compact
        actions={
          <Button onClick={openCreateModal}>
            Add Assignment
            <ShortcutKey>N</ShortcutKey>
          </Button>
        }
      />
      <div className="flex items-center gap-4">
        <Select options={classes.map((c) => ({ value: String(c.id), label: c.name }))} placeholder="All classes" value={classFilter}
          onChange={(e) => { setClassFilter(e.target.value); setPage(1) }} />
        <Select options={teachers.map((t) => ({ value: String(t.id), label: `${t.first_name} ${t.last_name}` }))} placeholder="All teachers" value={teacherFilter}
          onChange={(e) => { setTeacherFilter(e.target.value); setPage(1) }} />
      </div>
      <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
        {loading ? <Table columns={[]} data={[]} loading={true} keyExtractor={() => ''} emptyMessage="" /> : error ? <ErrorState message={error} onRetry={() => fetch({ page, size, class_id: classFilter ? Number(classFilter) : undefined, teacher_id: teacherFilter ? Number(teacherFilter) : undefined })} /> : (
          <>
            <Table columns={[...columns, { key: 'actions', header: 'Actions', render: (a: TeacherAssignmentResponse) => (<div className="flex gap-2" onClick={(e) => e.stopPropagation()}><Button variant="danger" size="sm" onClick={() => handleDelete(a)}>Delete</Button></div>) }]} data={data} keyExtractor={(a) => a.id} emptyMessage="No assignments found." />
            <Pagination page={page} size={size} total={total} pages={pages} onPageChange={setPage} onSizeChange={(s) => { setSize(s); setPage(1) }} />
          </>
        )}
      </Card>
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="Add Teacher Assignment"
        footer={<><Button variant="outline" onClick={() => setModalOpen(false)}>Cancel</Button><Button onClick={handleSubmit} loading={saving}>Create</Button></>}
      >
        {apiError && <Alert variant="error" onClose={() => setApiError(null)}>{apiError}</Alert>}
        <Form onSubmit={handleSubmit}>
          <Select label="Teacher" value={String(formData.teacher_id ?? '')} onChange={(e) => setFormData({ ...formData, teacher_id: e.target.value ? Number(e.target.value) : null })} error={formErrors.teacher_id}
            options={teachers.map((t) => ({ value: String(t.id), label: `${t.first_name} ${t.last_name}` }))} placeholder="Select teacher" />
          <Select label="Class" value={String(formData.class_id ?? '')} onChange={(e) => setFormData({ ...formData, class_id: e.target.value ? Number(e.target.value) : null })} error={formErrors.class_id}
            options={classes.map((c) => ({ value: String(c.id), label: c.name }))} placeholder="Select class" />
          <Select label="Subject" value={String(formData.subject_id ?? '')} onChange={(e) => setFormData({ ...formData, subject_id: e.target.value ? Number(e.target.value) : null })}
            options={subjects.map((s) => ({ value: String(s.id), label: `${s.name} (${s.code})` }))} placeholder="Select subject (optional)" />
        </Form>
      </Modal>
    </div>
  )
}