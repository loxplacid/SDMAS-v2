import { useCallback, useEffect, useRef, useState } from 'react'
import { paymentApi, type PaymentListParams } from '../../api/fees/payment-api'
import { exportApi } from '../../api/reports/export-api'
import type { PaymentResponse, PaymentCreate, PaymentResult } from '../../api/generated/types'
import { Button, Modal, Form, Input, Select, Alert, Badge, useToast } from '../../components/ui'
import type { Column } from '../../components/ui/table'
import { useDelight } from '../../components/delight/delight-provider'
import { DataWorkspace, useWorkspace } from '../../components/data-workspace'
import { PAYMENT_METHODS, capitalize, formatCurrency, formatDateTime, plural } from '../../lib/utils'

const methodBadge: Record<string, 'info' | 'success' | 'warning' | 'neutral'> = {
  cash: 'success',
  bank_transfer: 'info',
  cheque: 'warning',
  card: 'info',
  mobile_money: 'info',
}

const PAYMENT_COLUMNS: Column<PaymentResponse>[] = [
  { key: 'id', header: 'ID', type: 'numeric', render: (p) => `#${p.id}` },
  { key: 'student_id', header: 'Student ID', type: 'numeric' },
  { key: 'fee_due_id', header: 'Fee Due', type: 'numeric' },
  {
    key: 'amount',
    header: 'Amount',
    type: 'amount',
    render: (p) => formatCurrency(p.amount),
    currency: 'NGN',
  },
  {
    key: 'payment_method',
    header: 'Method',
    render: (p) =>
      p.payment_method ? (
        <Badge variant={methodBadge[p.payment_method] || 'neutral'}>
          {capitalize(p.payment_method.replace('_', ' '))}
        </Badge>
      ) : (
        '-'
      ),
  },
  { key: 'receipt_number', header: 'Receipt', type: 'text', render: (p) => p.receipt_number || '-', hideOnMobile: true },
  { key: 'payment_date', header: 'Date', type: 'date', render: (p) => p.payment_date || '-' },
  { key: 'created_at', header: 'Recorded', type: 'date', render: (p) => formatDateTime(p.created_at), hideOnMobile: true },
]

export function PaymentListPage() {
  const { showToast } = useToast()
  const { celebrate } = useDelight()

  const workspace = useWorkspace<PaymentResponse>({
    viewKey: 'payments',
    columns: PAYMENT_COLUMNS,
    defaultPageSize: 20,
  })

  const [data, setData] = useState<PaymentResponse[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchIdRef = useRef(0)

  const fetch = useCallback(async (params: PaymentListParams, showLoading: boolean) => {
    const fetchId = ++fetchIdRef.current
    if (showLoading) setLoading(true)
    setError(null)
    try {
      const result = await paymentApi.list(params)
      if (fetchId === fetchIdRef.current) {
        setData(result.items); setTotal(result.total); setPages(result.pages)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load payments')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [])

  // Server round-trip: page/size, plus the numeric search → student_id.
  useEffect(() => {
    const params: PaymentListParams = { page: workspace.page, size: workspace.size }
    const q = workspace.filters.query.trim()
    const studentId = Number(q)
    if (q && Number.isFinite(studentId)) params.student_id = studentId
    fetch(params, true)
  }, [workspace.page, workspace.size, workspace.filters, fetch])

  const [modalOpen, setModalOpen] = useState(false)
  const [formData, setFormData] = useState<PaymentCreate>({ student_id: 0, fee_due_id: 0, amount: 0, payment_date: new Date().toISOString().split('T')[0], payment_method: 'cash', receipt_number: null })
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)

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
      // Glint §5.1 — first-of-kind milestone (registry-gated, once per campus).
      celebrate('first-payment')
      setModalOpen(false)
      fetch({ page: workspace.page, size: workspace.size }, true)
    } catch (err: any) {
      setApiError(err?.detail || 'Failed to record payment')
    } finally {
      setSaving(false)
    }
  }

  // ── export the current workspace state (P8 §22) ──
  const [exporting, setExporting] = useState(false)
  const handleExport = async () => {
    setExporting(true)
    try {
      const blob = await exportApi.payments({})
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'payments.csv'
      a.click()
      window.URL.revokeObjectURL(url)
      // The export endpoint has no student-id filter, so it exports the full
      // ledger — say so honestly rather than claiming the filtered count.
      showToast('Exporting all payments', 'success')
    } catch (err: any) {
      showToast(err?.detail || 'Export failed', 'error')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="space-y-4">
      <DataWorkspace
        workspace={workspace}
        title="Payments"
        description={plural(total, 'payment')}
        columns={PAYMENT_COLUMNS}
        keyExtractor={(p) => p.id}
        data={data}
        total={total}
        pages={pages}
        loading={loading}
        error={error}
        onRetry={() => fetch({ page: workspace.page, size: workspace.size }, true)}
        onRefresh={() => fetch({ page: workspace.page, size: workspace.size }, false)}
        mode="server"
        filterPlaceholder="Search by student ID…"
        primaryAction={
          <Button onClick={openCreateModal}>Record Payment</Button>
        }
        toolbarActions={
          <Button variant="secondary" onClick={handleExport} loading={exporting}>
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Export
          </Button>
        }
      />

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
