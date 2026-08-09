import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { attendanceApi } from '../../api/attendance/attendance-api'
import type { AttendanceRecordCreate } from '../../api/generated/types'
import { Card, Input, Select, Button, Modal, Form, Alert, useToast, PageHeader } from '../../components/ui'
import { ATTENDANCE_STATUSES, capitalize } from '../../lib/utils'

export function RecordAttendancePage() {
  const navigate = useNavigate()
  const { showToast } = useToast()

  const [formData, setFormData] = useState<AttendanceRecordCreate>({
    student_id: 0,
    academic_year_id: 0,
    class_id: 0,
    section_id: 0,
    attendance_date: '',
    status: 'present',
    notes: null,
  })
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)

  const validate = (): boolean => {
    const errors: Record<string, string> = {}
    if (!formData.student_id) errors.student_id = 'Student ID is required'
    if (!formData.academic_year_id) errors.academic_year_id = 'Academic year ID is required'
    if (!formData.class_id) errors.class_id = 'Class ID is required'
    if (!formData.section_id) errors.section_id = 'Section ID is required'
    if (!formData.attendance_date) errors.attendance_date = 'Date is required'
    setFormErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!validate()) return
    setSaving(true)
    setApiError(null)
    try {
      await attendanceApi.record(formData)
      showToast('Attendance recorded', 'success')
      navigate('/attendance/records')
    } catch (err: any) {
      setApiError(err?.detail || 'Failed to record attendance')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6 max-w-2xl animate-fade-in-up">
      <div>
        <button onClick={() => navigate('/attendance/records')} className="text-sm text-[var(--color-brand-accent)] hover:text-[var(--color-brand-accent-hover)] transition-colors mb-1">
          &larr; Back to Records
        </button>
        <PageHeader eyebrow="Attendance" title="Record Attendance" compact />
      </div>

      <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
        {apiError && <Alert variant="error" onClose={() => setApiError(null)}>{apiError}</Alert>}
        <Form onSubmit={handleSubmit}>
          <Input
            label="Student ID"
            type="number"
            value={formData.student_id || ''}
            onChange={(e) => setFormData({ ...formData, student_id: Number(e.target.value) })}
            error={formErrors.student_id}
            required
          />
          <Input
            label="Academic Year ID"
            type="number"
            value={formData.academic_year_id || ''}
            onChange={(e) => setFormData({ ...formData, academic_year_id: Number(e.target.value) })}
            error={formErrors.academic_year_id}
            required
          />
          <Input
            label="Class ID"
            type="number"
            value={formData.class_id || ''}
            onChange={(e) => setFormData({ ...formData, class_id: Number(e.target.value) })}
            error={formErrors.class_id}
            required
          />
          <Input
            label="Section ID"
            type="number"
            value={formData.section_id || ''}
            onChange={(e) => setFormData({ ...formData, section_id: Number(e.target.value) })}
            error={formErrors.section_id}
            required
          />
          <Input
            label="Date"
            type="date"
            value={formData.attendance_date}
            onChange={(e) => setFormData({ ...formData, attendance_date: e.target.value })}
            error={formErrors.attendance_date}
            required
          />
          <Select
            label="Status"
            value={formData.status}
            onChange={(e) => setFormData({ ...formData, status: e.target.value })}
            options={ATTENDANCE_STATUSES.map((s) => ({ value: s, label: capitalize(s) }))}
          />
          <Input
            label="Notes"
            value={formData.notes || ''}
            onChange={(e) => setFormData({ ...formData, notes: e.target.value || null })}
          />
          <div className="flex gap-3 pt-2">
            <Button type="submit" loading={saving}>Record Attendance</Button>
            <Button variant="outline" onClick={() => navigate('/attendance/records')}>Cancel</Button>
          </div>
        </Form>
      </Card>
    </div>
  )
}