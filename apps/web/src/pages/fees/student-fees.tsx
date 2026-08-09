import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { feeDueApi } from '../../api/fees/fee-due-api'
import type { FeeDueResponse } from '../../api/generated/types'
import { Card, Input, Button, Badge, ErrorState, Table, PageHeader } from '../../components/ui'
import { formatCurrency, capitalize } from '../../lib/utils'

const statusBadge: Record<string, 'success' | 'warning' | 'danger'> = {
  paid: 'success', partially_paid: 'warning', unpaid: 'danger',
}

export function StudentFeesPage() {
  const navigate = useNavigate()
  const [studentId, setStudentId] = useState('')
  const [ayId, setAyId] = useState('')
  const [fees, setFees] = useState<any[] | null>(null)
  const [dues, setDues] = useState<FeeDueResponse[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleLoad = async () => {
    if (!studentId || !ayId) return
    setLoading(true); setError(null)
    try {
      const [applicableFees, studentDues] = await Promise.all([
        feeDueApi.getStudentFees(Number(studentId), Number(ayId)),
        feeDueApi.getStudentDues(Number(studentId), { academic_year_id: Number(ayId) }),
      ])
      setFees(applicableFees as any[])
      setDues(studentDues)
    } catch (err: any) { setError(err?.detail || 'Failed to load student fees') }
    finally { setLoading(false) }
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <button onClick={() => navigate('/fees')} className="text-sm text-[var(--color-brand-accent)] hover:text-[var(--color-brand-accent-hover)] transition-colors mb-1">
          &larr; Back to Fees
        </button>
        <PageHeader eyebrow="Fees" title="Student Fees" subtitle="View fee structures and dues for individual students." compact />
      </div>

      <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
        <div className="flex gap-4 items-end">
          <Input label="Student ID" type="number" value={studentId} onChange={(e) => setStudentId(e.target.value)} required />
          <Input label="Academic Year ID" type="number" value={ayId} onChange={(e) => setAyId(e.target.value)} required />
          <Button onClick={handleLoad} loading={loading}>Load</Button>
        </div>
      </Card>

      {error && <ErrorState message={error} />}

      {fees && (
        <Card title="Applicable Fee Structures">
          {fees.length === 0 ? (
            <p className="text-[var(--color-text-tertiary)] text-sm">No fee structures assigned for this student and academic year.</p>
          ) : (
            <Table
              columns={[
                { key: 'fee_type_name', header: 'Fee Type', render: (f: any) => f.fee_type_name || f.fee_type_id },
                { key: 'amount', header: 'Amount', render: (f: any) => <span className="font-medium">{formatCurrency(f.amount)}</span> },
                { key: 'frequency', header: 'Frequency', render: (f: any) => capitalize(f.frequency) },
                { key: 'status', header: 'Status', render: (f: any) => <Badge variant={f.status === 'active' ? 'success' : 'danger'}>{capitalize(f.status)}</Badge> },
              ]}
              data={fees as any[]}
              keyExtractor={(f: any) => f.id}
            />
          )}
        </Card>
      )}

      {dues.length > 0 && (
        <Card title="Fee Dues">
          <Table
            columns={[
              { key: 'id', header: 'ID', render: (d: FeeDueResponse) => `#${d.id}` },
              { key: 'original_amount', header: 'Amount', render: (d: FeeDueResponse) => <span className="font-medium">{formatCurrency(d.original_amount)}</span> },
              { key: 'amount_paid', header: 'Paid', render: (d: FeeDueResponse) => formatCurrency(d.amount_paid) },
              { key: 'balance', header: 'Balance', render: (d: FeeDueResponse) => <span className="font-semibold">{formatCurrency(d.original_amount - d.amount_paid)}</span> },
              { key: 'status', header: 'Status', render: (d: FeeDueResponse) => <Badge variant={statusBadge[d.status]}>{capitalize(d.status.replace('_', ' '))}</Badge> },
              { key: 'due_date', header: 'Due Date' },
            ]}
            data={dues}
            keyExtractor={(d: FeeDueResponse) => d.id}
            onRowClick={(d: FeeDueResponse) => navigate(`/fees/dues/${d.id}`)}
          />
        </Card>
      )}
    </div>
  )
}