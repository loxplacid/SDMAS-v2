import { useState } from 'react'
import { exportApi } from '../../api/reports/export-api'
import { studentApi } from '../../api/student/student-api'
import { Card, Button, Select, Input, Alert } from '../../components/ui'
import { STUDENT_STATUSES, capitalize } from '../../lib/utils'

export function StudentExportPage() {
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')
  const [studentCount, setStudentCount] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const previewCount = async () => {
    try {
      const result = await studentApi.list({
        size: 1,
        status: status || undefined,
        search: search || undefined,
      })
      setStudentCount(result.total)
    } catch {
      setStudentCount(null)
    }
  }

  const handleExport = async () => {
    setLoading(true)
    setError(null)
    setSuccess(false)
    try {
      const blob = await exportApi.students({
        status: status || undefined,
        search: search || undefined,
      })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'students.csv'
      a.click()
      window.URL.revokeObjectURL(url)
      setSuccess(true)
    } catch (err: any) {
      setError(err?.detail || 'Export failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <div className="text-[var(--color-brand-accent)] text-xs font-semibold uppercase tracking-wider">Data Operations</div>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)] mt-1">Export Students</h1>
        <p className="text-sm text-[var(--color-text-tertiary)] mt-1">Download student records as CSV</p>
      </div>

      <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Select
            options={STUDENT_STATUSES.map((s) => ({ value: s, label: capitalize(s) }))}
            value={status}
            onChange={(e) => { setStatus(e.target.value); setStudentCount(null) }}
            placeholder="All statuses"
          />
          <Input
            placeholder="Search by name, number, or email"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setStudentCount(null) }}
          />
        </div>
        <div className="mt-4 flex gap-3">
          <Button variant="secondary" onClick={previewCount}>Preview Count</Button>
          <Button onClick={handleExport} loading={loading}>Export CSV</Button>
        </div>
        {studentCount !== null && (
          <p className="text-sm text-[var(--color-text-tertiary)] mt-3">{studentCount} student{studentCount !== 1 ? 's' : ''} will be exported</p>
        )}
        {error && <Alert variant="error" onClose={() => setError(null)} className="mt-3">{error}</Alert>}
        {success && <Alert variant="success" onClose={() => setSuccess(false)} className="mt-3">Export started successfully.</Alert>}
      </Card>
    </div>
  )
}

export default StudentExportPage