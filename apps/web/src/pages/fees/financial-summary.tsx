import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { summaryApi } from '../../api/fees/summary-api'
import { paymentApi } from '../../api/fees/payment-api'
import { feeDueApi } from '../../api/fees/fee-due-api'
import type { StudentFinancialSummary, ClassFinancialSummary } from '../../api/generated/types'
import { Card, Input, Button, Select, Table, ErrorState, Badge, TabGroup, PageHeader } from '../../components/ui'
import { formatCurrency, capitalize, FEE_DUE_STATUSES } from '../../lib/utils'

const statusLabel: Record<string, string> = { paid: 'Paid', partially_paid: 'Partial', unpaid: 'Unpaid' }
const statusBadge: Record<string, 'success' | 'warning' | 'danger'> = { paid: 'success', partially_paid: 'warning', unpaid: 'danger' }

export function FinancialSummaryPage() {
  const navigate = useNavigate()

  const [tab, setTab] = useState<'student' | 'class'>('student')

  const [studentId, setStudentId] = useState('')
  const [classId, setClassId] = useState('')
  const [ayId, setAyId] = useState('')
  const [studentSummary, setStudentSummary] = useState<StudentFinancialSummary | null>(null)
  const [classSummary, setClassSummary] = useState<ClassFinancialSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [studentDues, setStudentDues] = useState<any[]>([])
  const [studentPayments, setStudentPayments] = useState<any[]>([])

  const fetchStudentSummary = async () => {
    if (!studentId || !ayId) return
    setLoading(true); setError(null)
    try {
      const [summary, dues, payments] = await Promise.all([
        summaryApi.getStudentSummary(Number(studentId), Number(ayId)),
        feeDueApi.getStudentDues(Number(studentId), { academic_year_id: Number(ayId) }),
        paymentApi.getStudentPayments(Number(studentId)),
      ])
      setStudentSummary(summary)
      setStudentDues(dues)
      setStudentPayments(payments)
    } catch (err: any) { setError(err?.detail || 'Failed to load summary') }
    finally { setLoading(false) }
  }

  const fetchClassSummary = async () => {
    if (!classId || !ayId) return
    setLoading(true); setError(null)
    try {
      const summary = await summaryApi.getClassSummary(Number(classId), Number(ayId))
      setClassSummary(summary)
    } catch (err: any) { setError(err?.detail || 'Failed to load summary') }
    finally { setLoading(false) }
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        eyebrow="Fees"
        title="Financial Summary"
        compact
        actions={
          <TabGroup
            tabs={[
              { id: 'student', label: 'Student' },
              { id: 'class', label: 'Class' },
            ]}
            activeTab={tab}
            onChange={(id) => setTab(id as 'student' | 'class')}
            variant="pills"
            size="sm"
          />
        }
      />

      {tab === 'student' ? (
        <div className="space-y-4">
          <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
            <div className="flex gap-4 items-end">
              <Input label="Student ID" type="number" value={studentId} onChange={(e) => setStudentId(e.target.value)} required />
              <Input label="Academic Year ID" type="number" value={ayId} onChange={(e) => setAyId(e.target.value)} required />
              <Button onClick={fetchStudentSummary} loading={loading}>Load</Button>
            </div>
          </Card>

          {error && <ErrorState message={error} />}

          {studentSummary && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none"><div className="text-center"><p className="text-2xl font-bold text-[var(--color-text-primary)]">{formatCurrency(studentSummary.total_fees_assigned)}</p><p className="text-xs text-[var(--color-text-tertiary)]">Total Assigned</p></div></Card>
                <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none"><div className="text-center"><p className="text-2xl font-bold text-green-600">{formatCurrency(studentSummary.total_paid)}</p><p className="text-xs text-[var(--color-text-tertiary)]">Paid</p></div></Card>
                <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none"><div className="text-center"><p className="text-2xl font-bold text-red-600">{formatCurrency(studentSummary.total_outstanding)}</p><p className="text-xs text-[var(--color-text-tertiary)]">Outstanding</p></div></Card>
                <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none"><div className="text-center"><p className="text-2xl font-bold text-blue-600">{studentSummary.paid_count}</p><p className="text-xs text-[var(--color-text-tertiary)]">Paid Dues</p></div></Card>
                <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none"><div className="text-center"><p className="text-2xl font-bold text-yellow-600">{studentSummary.partially_paid_count + studentSummary.unpaid_count}</p><p className="text-xs text-[var(--color-text-tertiary)]">Pending Dues</p></div></Card>
              </div>

              {studentDues.length > 0 && (
                <Card title="Fee Dues" className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
                  <Table
                    columns={[
                      { key: 'id', header: 'ID', render: (d: any) => `#${d.id}` },
                      { key: 'original_amount', header: 'Amount', render: (d: any) => formatCurrency(d.original_amount) },
                      { key: 'amount_paid', header: 'Paid', render: (d: any) => formatCurrency(d.amount_paid) },
                      { key: 'status', header: 'Status', render: (d: any) => <Badge variant={statusBadge[d.status]}>{statusLabel[d.status] || capitalize(d.status)}</Badge> },
                      { key: 'due_date', header: 'Due', render: (d: any) => d.due_date || '-' },
                    ]}
                    data={studentDues}
                    keyExtractor={(d: any) => d.id}
                    emptyMessage="No dues found."
                  />
                </Card>
              )}

              {studentPayments.length > 0 && (
                <Card title="Payment History" className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
                  <Table
                    columns={[
                      { key: 'id', header: 'ID', render: (p: any) => `#${p.id}` },
                      { key: 'fee_due_id', header: 'Fee Due' },
                      { key: 'amount', header: 'Amount', render: (p: any) => formatCurrency(p.amount) },
                      { key: 'payment_method', header: 'Method', render: (p: any) => p.payment_method ? capitalize(p.payment_method.replace('_', ' ')) : '-' },
                      { key: 'receipt_number', header: 'Receipt', render: (p: any) => p.receipt_number || '-' },
                      { key: 'payment_date', header: 'Date', render: (p: any) => p.payment_date || '-' },
                    ]}
                    data={studentPayments}
                    keyExtractor={(p: any) => p.id}
                    emptyMessage="No payments found."
                  />
                </Card>
              )}
            </>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
            <div className="flex gap-4 items-end">
              <Input label="Class ID" type="number" value={classId} onChange={(e) => setClassId(e.target.value)} required />
              <Input label="Academic Year ID" type="number" value={ayId} onChange={(e) => setAyId(e.target.value)} required />
              <Button onClick={fetchClassSummary} loading={loading}>Load</Button>
            </div>
          </Card>

          {error && <ErrorState message={error} />}

          {classSummary && (
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none"><div className="text-center"><p className="text-2xl font-bold text-[var(--color-text-primary)]">{classSummary.total_students}</p><p className="text-xs text-[var(--color-text-tertiary)]">Students</p></div></Card>
              <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none"><div className="text-center"><p className="text-2xl font-bold text-[var(--color-text-primary)]">{formatCurrency(classSummary.total_fees_assigned)}</p><p className="text-xs text-[var(--color-text-tertiary)]">Total Fees</p></div></Card>
              <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none"><div className="text-center"><p className="text-2xl font-bold text-green-600">{formatCurrency(classSummary.total_collected)}</p><p className="text-xs text-[var(--color-text-tertiary)]">Collected</p></div></Card>
              <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none"><div className="text-center"><p className="text-2xl font-bold text-red-600">{formatCurrency(classSummary.total_outstanding)}</p><p className="text-xs text-[var(--color-text-tertiary)]">Outstanding</p></div></Card>
              <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none"><div className="text-center"><p className="text-2xl font-bold text-yellow-600">{classSummary.students_with_outstanding}</p><p className="text-xs text-[var(--color-text-tertiary)]">Students w/ Outstanding</p></div></Card>
            </div>
          )}
        </div>
      )}
    </div>
  )
}