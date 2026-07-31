import { useState } from 'react'
import { exportApi } from '../../api/reports/export-api'
import { academicYearApi } from '../../api/academic/academic-year-api'
import { Card, Button, Select, Alert, Input } from '../../components/ui'

export function PaymentExportPage() {
  const [academicYears, setAcademicYears] = useState<{ id: number; name: string }[]>([])
  const [selectedYearId, setSelectedYearId] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  useState(() => {
    academicYearApi.list({ size: 100 }).then((r) => {
      setAcademicYears(r.items.map((y) => ({ id: y.id, name: y.name })))
    }).catch(() => {})
  })

  const handleExport = async () => {
    setLoading(true)
    setError(null)
    setSuccess(false)
    try {
      const blob = await exportApi.payments({
        academic_year_id: selectedYearId ? Number(selectedYearId) : undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'payments.csv'
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
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)] mt-1">Export Payments</h1>
        <p className="text-sm text-[var(--color-text-tertiary)] mt-1">Download payment records as CSV</p>
      </div>

      <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">Academic Year (optional)</label>
            <Select
              options={academicYears.map((y) => ({ value: String(y.id), label: y.name }))}
              value={selectedYearId}
              onChange={(e) => setSelectedYearId(e.target.value)}
              placeholder="All years"
            />
          </div>
          <Input label="Start Date" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          <Input label="End Date" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
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

export default PaymentExportPage