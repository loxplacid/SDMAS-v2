import { useState } from 'react'
import { exportApi } from '../../api/reports/export-api'
import { sectionApi } from '../../api/academic/section-api'
import { Card, Button, Select, Alert } from '../../components/ui'

export function AttendanceExportPage() {
  const [sections, setSections] = useState<{ id: number; name: string }[]>([])
  const [selectedSectionId, setSelectedSectionId] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const loadSections = async () => {
    if (sections.length === 0) {
      try {
        const result = await sectionApi.list({ size: 1000 })
        setSections(result.items.map((s) => ({ id: s.id, name: s.name })))
      } catch {}
    }
  }

  useState(() => { loadSections() })

  const handleExport = async () => {
    setLoading(true)
    setError(null)
    setSuccess(false)
    try {
      const blob = await exportApi.attendance({
        section_id: selectedSectionId ? Number(selectedSectionId) : undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'attendance.csv'
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
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Export Attendance</h1>
        <p className="text-gray-500 mt-1">Download attendance records as CSV</p>
      </div>

      <Card>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Section (optional)</label>
            <Select
              options={sections.map((s) => ({ value: String(s.id), label: s.name }))}
              value={selectedSectionId}
              onChange={(e) => setSelectedSectionId(e.target.value)}
              placeholder="All sections"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
        <div className="mt-4">
          <Button onClick={handleExport} loading={loading}>Export CSV</Button>
        </div>
        {error && <Alert variant="error" onClose={() => setError(null)} className="mt-3">{error}</Alert>}
        {success && <Alert variant="success" onClose={() => setSuccess(false)} className="mt-3">Export started successfully.</Alert>}
      </Card>
    </div>
  )
}

export default AttendanceExportPage