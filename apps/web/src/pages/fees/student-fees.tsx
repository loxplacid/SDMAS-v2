import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { feeDueApi } from '../../api/fees/fee-due-api'
import type { FeeDueResponse } from '../../api/generated/types'
import { Card, Input, Button, Badge, ErrorState } from '../../components/ui'
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
        <p className="text-sm font-medium text-[var(--color-brand-accent)] tracking-wide mt-2 mb-1">Fees</p>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)] tracking-tight">Student Fees</h1>
        <p className="text-sm text-[var(--color-text-tertiary)] mt-1">View fee structures and dues for individual students.</p>
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
            <p className="text-gray-500 text-sm">No fee structures assigned for this student and academic year.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium text-gray-500">Fee Type</th>
                    <th className="px-4 py-2 text-left font-medium text-gray-500">Amount</th>
                    <th className="px-4 py-2 text-left font-medium text-gray-500">Frequency</th>
                    <th className="px-4 py-2 text-left font-medium text-gray-500">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {(fees as any[]).map((fee: any) => (
                    <tr key={fee.id} className="hover:bg-gray-50">
                      <td className="px-4 py-2">{fee.fee_type_name || fee.fee_type_id}</td>
                      <td className="px-4 py-2 font-medium">{formatCurrency(fee.amount)}</td>
                      <td className="px-4 py-2">{capitalize(fee.frequency)}</td>
                      <td className="px-4 py-2"><Badge variant={fee.status === 'active' ? 'success' : 'danger'}>{capitalize(fee.status)}</Badge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {dues.length > 0 && (
        <Card title="Fee Dues">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left font-medium text-gray-500">ID</th>
                  <th className="px-4 py-2 text-left font-medium text-gray-500">Amount</th>
                  <th className="px-4 py-2 text-left font-medium text-gray-500">Paid</th>
                  <th className="px-4 py-2 text-left font-medium text-gray-500">Balance</th>
                  <th className="px-4 py-2 text-left font-medium text-gray-500">Status</th>
                  <th className="px-4 py-2 text-left font-medium text-gray-500">Due Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {dues.map((due) => (
                  <tr key={due.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => navigate(`/fees/dues/${due.id}`)}>
                    <td className="px-4 py-2">#{due.id}</td>
                    <td className="px-4 py-2 font-medium">{formatCurrency(due.original_amount)}</td>
                    <td className="px-4 py-2">{formatCurrency(due.amount_paid)}</td>
                    <td className="px-4 py-2 font-semibold">{formatCurrency(due.original_amount - due.amount_paid)}</td>
                    <td className="px-4 py-2"><Badge variant={statusBadge[due.status]}>{capitalize(due.status.replace('_', ' '))}</Badge></td>
                    <td className="px-4 py-2">{due.due_date || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}