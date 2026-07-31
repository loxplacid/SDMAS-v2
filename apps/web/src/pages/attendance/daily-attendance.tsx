import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { attendanceApi } from '../../api/attendance/attendance-api'
import type { AttendanceRecordResponse, DailyAttendanceItem } from '../../api/generated/types'
import { Card, Input, Select, Button, Badge, Alert, Form, ErrorState, useToast } from '../../components/ui'
import { ATTENDANCE_STATUSES, capitalize } from '../../lib/utils'

const statusBadge: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
  present: 'success',
  absent: 'danger',
  late: 'warning',
  excused: 'info',
}

export function DailyAttendancePage() {
  const navigate = useNavigate()
  const { showToast } = useToast()

  const [sectionId, setSectionId] = useState('')
  const [attendanceDate, setAttendanceDate] = useState(new Date().toISOString().split('T')[0])
  const [existingRecords, setExistingRecords] = useState<AttendanceRecordResponse[]>([])
  const [dailyRecords, setDailyRecords] = useState<DailyAttendanceItem[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [apiError, setApiError] = useState<string | null>(null)
  const [loaded, setLoaded] = useState(false)

  const fetchIdRef = useRef(0)

  const loadSectionRecords = useCallback(async () => {
    if (!sectionId || !attendanceDate) return
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)
    try {
      const records = await attendanceApi.getSectionAttendance(Number(sectionId), attendanceDate)
      if (fetchId === fetchIdRef.current) {
        setExistingRecords(records)
        setDailyRecords(records.map((r) => ({ student_id: r.student_id, status: r.status, notes: r.notes })))
        setLoaded(true)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) {
        if (err?.status === 404) {
          setExistingRecords([])
          setDailyRecords([])
          setLoaded(true)
        } else {
          setError(err?.detail || 'Failed to load records')
        }
      }
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [sectionId, attendanceDate])

  useEffect(() => {
    if (sectionId && attendanceDate) loadSectionRecords()
  }, [loadSectionRecords])

  const updateRecordStatus = (studentId: number, status: string) => {
    setDailyRecords((prev) => {
      const existing = prev.find((r) => r.student_id === studentId)
      if (existing) {
        return prev.map((r) => (r.student_id === studentId ? { ...r, status } : r))
      }
      return [...prev, { student_id: studentId, status, notes: null }]
    })
  }

  const updateRecordNotes = (studentId: number, notes: string) => {
    setDailyRecords((prev) => {
      const existing = prev.find((r) => r.student_id === studentId)
      if (existing) {
        return prev.map((r) => (r.student_id === studentId ? { ...r, notes: notes || null } : r))
      }
      return [...prev, { student_id: studentId, status: 'present', notes: notes || null }]
    })
  }

  const addStudent = () => {
    setDailyRecords((prev) => [...prev, { student_id: 0, status: 'present', notes: null }])
  }

  const removeStudent = (studentId: number) => {
    setDailyRecords((prev) => prev.filter((r) => r.student_id !== studentId))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!sectionId || !attendanceDate) return
    if (dailyRecords.length === 0) {
      setApiError('Add at least one student record')
      return
    }
    setSaving(true)
    setApiError(null)
    try {
      await attendanceApi.recordDaily({
        section_id: Number(sectionId),
        attendance_date: attendanceDate,
        records: dailyRecords.filter((r) => r.student_id > 0),
      })
      showToast('Daily attendance saved', 'success')
      await loadSectionRecords()
    } catch (err: any) {
      setApiError(err?.detail || 'Failed to save daily attendance')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <button onClick={() => navigate('/attendance/records')} className="text-sm text-[var(--color-brand-accent)] hover:text-[var(--color-brand-accent-hover)] transition-colors mb-1">
          &larr; Back to Records
        </button>
        <div className="text-[var(--color-brand-accent)] text-xs font-semibold uppercase tracking-wider mt-1">Attendance</div>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)] mt-1">Daily Attendance</h1>
      </div>

      <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
        <Form onSubmit={handleSubmit}>
          <div className="flex gap-4 items-end">
            <Input
              label="Section ID"
              type="number"
              value={sectionId}
              onChange={(e) => { setSectionId(e.target.value); setLoaded(false) }}
              required
            />
            <Input
              label="Date"
              type="date"
              value={attendanceDate}
              onChange={(e) => { setAttendanceDate(e.target.value); setLoaded(false) }}
              required
            />
            <Button variant="outline" onClick={loadSectionRecords} loading={loading}>
              Load
            </Button>
          </div>

          {apiError && <Alert variant="error" onClose={() => setApiError(null)}>{apiError}</Alert>}
          {error && <Alert variant="error">{error}</Alert>}

          {loaded && (
            <div className="space-y-4 mt-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium">
                  {existingRecords.length > 0 ? 'Update Existing Records' : 'New Records'}
                  <span className="text-sm text-[var(--color-text-tertiary)] ml-2">({dailyRecords.length} student{dailyRecords.length !== 1 ? 's' : ''})</span>
                </h3>
                <Button variant="outline" size="sm" onClick={addStudent}>Add Student</Button>
              </div>

              <div className="border border-[var(--color-border)] rounded-[var(--radius-lg)] overflow-hidden">
                <table className="min-w-full text-sm">
                  <thead className="bg-[var(--color-surface-hover)]">
                    <tr>
                      <th className="px-4 py-3 text-left font-medium text-[var(--color-text-tertiary)]">Student ID</th>
                      <th className="px-4 py-3 text-left font-medium text-[var(--color-text-tertiary)]">Status</th>
                      <th className="px-4 py-3 text-left font-medium text-[var(--color-text-tertiary)]">Notes</th>
                      <th className="px-4 py-3"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--color-divider)]">
                    {dailyRecords.map((record, idx) => (
                      <tr key={idx} className="hover:bg-[var(--color-surface-hover)]">
                        <td className="px-4 py-3">
                          <Input
                            type="number"
                            value={record.student_id || ''}
                            onChange={(e) => {
                              const newId = Number(e.target.value)
                              setDailyRecords((prev) => prev.map((r, i) => i === idx ? { ...r, student_id: newId } : r))
                            }}
                            className="w-24"
                          />
                        </td>
                        <td className="px-4 py-3">
                          <Select
                            value={record.status}
                            onChange={(e) => updateRecordStatus(record.student_id, e.target.value)}
                            options={ATTENDANCE_STATUSES.map((s) => ({ value: s, label: capitalize(s) }))}
                          />
                        </td>
                        <td className="px-4 py-3">
                          <Input
                            value={record.notes || ''}
                            onChange={(e) => updateRecordNotes(record.student_id, e.target.value)}
                            placeholder="Optional"
                          />
                        </td>
                        <td className="px-4 py-3">
                          <Button variant="danger" size="sm" onClick={() => removeStudent(record.student_id)}>Remove</Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="flex gap-3 pt-2">
                <Button type="submit" loading={saving}>Save Daily Attendance</Button>
              </div>
            </div>
          )}
        </Form>
      </Card>
    </div>
  )
}