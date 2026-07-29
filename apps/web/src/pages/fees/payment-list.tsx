import { useState, useEffect, useCallback, useRef } from 'react'
import { paymentApi, type PaymentListParams } from '../../api/fees/payment-api'
import type { PaymentResponse, PaymentCreate, PaymentResult } from '../../api/generated/types'
import { Card, Table, Pagination, Input, Select, Button, Badge, Modal, Form, Alert, ErrorState, useToast } from '../../components/ui'
import { PAYMENT_METHODS, capitalize, formatCurrency, formatDateTime } from '../../lib/utils'

const methodBadge: Record<string, 'info' | 'success' | 'warning' | 'neutral'> = {
  cash: 'success',
  bank_transfer: 'info',
  cheque: 'warning',
  card: 'info',
  mobile_money: 'info',
}

export function PaymentListPage() {
  const { showToast } = useToast()

  const [data, setData] = useState<PaymentResponse[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(0)
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(20)
  const [studentFilter, setStudentFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [modalOpen, setModalOpen] = useState(false)
  const [formData, setFormData] = useState<PaymentCreate>({ student_id: 0, fee_due_id: 0, amount: 0, payment_date: new Date().toISOString().split('T')[0], payment_method: 'cash', receipt_number: null })
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)

  const fetchIdRef = useRef(0)

  const fetch = useCallback(async (params: PaymentListParams) => {
    const fetchId = ++fetchIdRef.current
    setLoading(true); setError(null)
    try {
      const result = await paymentApi.list(params)
      if (fetchId === fetchIdRef.current) {
        setData(result.items); setTotal(result.total); setPages(result.pages); setPage(result.page)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load payments')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const params: PaymentListParams = { page, size }
    if (studentFilter) params.student_id = Number(studentFilter)
    fetch(params)
  }, [page, size, studentFilter, fetch])

  const openCreateModal = () => {
    setFormData({ student_id: 0, fee_due_id: 0, amount: 0, payment_date: new Date().toISOString().split('T')[0], payment_method: 'cash', receipt_number: null })
    setFormErrors({}); setApiError(null); setModalOpen(true)
  }

  const validate = () => {
    const e: Record<string, string> = {}
    if (!formData.student_id) e.student_id = 'Required'
    if (!formData.fee_due_id) e.fee_due_id = 'Required'
    if (formData.amount <= 0) e.amount = 'Must be positive'
    setFormErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault()
    if (!validate()) return
    setSaving(true); setApiError(null)
    try {
      const result: PaymentResult = await paymentApi.record(formData)
      showToast(`Payment recorded. Receipt: ${result.payment.receipt_number || 'N/A'}`, 'success')
      setModalOpen(false)
      fetch({ page, size })
    } catch (err: any) { setApiError(err?.detail || 'Failed to record payment') }
    finally { setSaving(false) }
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[var(--color-brand-accent)] text-xs font-semibold uppercase tracking-wider">Fees</div>
          <h1 className="text-2xl font-bold text-[var(--color-text-primary)] mt-1">Payments</h1>
          <p className="text-[var(--color-text-tertiary)] text-sm mt-1">{total} payment{total !== 1 ? 's' : ''}</p>
        </div>
        <Button onClick={openCreateModal}>Record Payment</Button>
      </div>

      <div className="flex items-center gap-4">
        <Input type="number" placeholder="Student ID" value={studentFilter} onChange={(e) => { setStudentFilter(e.target.value); setPage(1) }} className="w-32" />
      </div>

      <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
        {loading ? <Table columns={[]} data={[]} loading={true} keyExtractor={() => ''} emptyMessage="" /> : error ? <ErrorState message={error} onRetry={() => fetch({ page, size })} /> : (
          <>
            <Table
              columns={[
                { key: 'id', header: 'ID', render: (p: PaymentResponse) => `#${p.id}` },
                { key: 'student_id', header: 'Student' },
                { key: 'fee_due_id', header: 'Fee Due' },
                { key: 'amount', header: 'Amount', render: (p: PaymentResponse) => formatCurrency(p.amount) },
                { key: 'payment_method', header: 'Method', render: (p: PaymentResponse) => p.payment_method ? <Badge variant={methodBadge[p.payment_method] || 'neutral'}>{capitalize(p.payment_method.replace('_', ' '))}</Badge> : '-' },
                { key: 'receipt_number', header: 'Receipt', render: (p: PaymentResponse) => p.receipt_number || '-' },
                { key: 'payment_date', header: 'Date', render: (p: PaymentResponse) => p.payment_date || '-' },
                { key: 'created_at', header: 'Recorded', render: (p: PaymentResponse) => formatDateTime(p.created_at) },
              ]}
              data={data}
              keyExtractor={(p) => p.id}
              emptyMessage="No payments found."
            />
            <Pagination page={page} size={size} total={total} pages={pages} onPageChange={setPage} onSizeChange={(s) => { setSize(s); setPage(1) }} />
          </>
        )}
      </Card>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)}
        title="Record Payment"
        footer={
          <>
            <Button variant="outline" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button onClick={handleSubmit} loading={saving}>Record Payment</Button>
          </>
        }
      >
        {apiError && <Alert variant="error" onClose={() => setApiError(null)}>{apiError}</Alert>}
        <Form onSubmit={handleSubmit}>
          <Input label="Student ID" type="number" value={formData.student_id || ''} onChange={(e) => setFormData({ ...formData, student_id: Number(e.target.value) })} error={formErrors.student_id} required />
          <Input label="Fee Due ID" type="number" value={formData.fee_due_id || ''} onChange={(e) => setFormData({ ...formData, fee_due_id: Number(e.target.value) })} error={formErrors.fee_due_id} required />
          <Input label="Amount (cents)" type="number" value={formData.amount || ''} onChange={(e) => setFormData({ ...formData, amount: Number(e.target.value) })} error={formErrors.amount} required />
          <Input label="Payment Date" type="date" value={formData.payment_date || ''} onChange={(e) => setFormData({ ...formData, payment_date: e.target.value || null })} />
          <Select label="Payment Method" value={formData.payment_method || 'cash'} onChange={(e) => setFormData({ ...formData, payment_method: e.target.value })} options={PAYMENT_METHODS.map((m) => ({ value: m, label: capitalize(m.replace('_', ' ')) }))} />
          <Input label="Receipt Number" value={formData.receipt_number || ''} onChange={(e) => setFormData({ ...formData, receipt_number: e.target.value || null })} />
        </Form>
      </Modal>
    </div>
  )
}