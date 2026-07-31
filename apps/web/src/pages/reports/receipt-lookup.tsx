import { useState } from 'react'
import { feeReportApi } from '../../api/reports/fee-reports'
import type { DetailedReceipt } from '../../api/reports/types'
import { Card, Button, ErrorState, Input, Badge } from '../../components/ui'
import { formatCurrency, formatDateTime } from '../../lib/utils'
import { useExport } from '../../hooks/use-export'

export function ReceiptLookupPage() {
  const [paymentId, setPaymentId] = useState('')
  const [receipt, setReceipt] = useState<DetailedReceipt | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { exportPDF, exporting } = useExport()

  const handleSearch = async () => {
    if (!paymentId.trim()) return
    setLoading(true)
    setError(null)
    setReceipt(null)
    try {
      const result = await feeReportApi.getReceipt(Number(paymentId))
      setReceipt(result)
    } catch (err: any) {
      setError(err?.detail || 'Receipt not found')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <div className="text-[var(--color-brand-accent)] text-xs font-semibold uppercase tracking-wider">Reports</div>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)] mt-1">Receipt Lookup</h1>
        <p className="text-sm text-[var(--color-text-tertiary)] mt-1">View payment receipt details</p>
      </div>

      <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
        <div className="flex gap-4 items-end">
          <div className="flex-1">
            <Input
              label="Payment ID"
              type="number"
              value={paymentId}
              onChange={(e) => setPaymentId(e.target.value)}
              placeholder="Enter payment ID"
            />
          </div>
          <Button onClick={handleSearch} loading={loading}>Search</Button>
        </div>
      </Card>

      {error && <ErrorState message={error} onRetry={handleSearch} />}
      {loading && <div className="h-48 bg-[var(--color-surface)] rounded-xl animate-pulse" />}

      {receipt && (
        <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">            <div className="border-b border-[var(--color-divider)] pb-4 mb-4">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-semibold">Payment Receipt</h2>
              <div className="flex items-center gap-2">
                {receipt.receipt_number && <Badge variant="success">#{receipt.receipt_number}</Badge>}
                <Button
                  variant="outline"
                  size="sm"
                  loading={exporting === 'pdf'}
                  onClick={() => exportPDF('Payment Receipt', [
                    { key: 'field', header: 'Field' },
                    { key: 'value', header: 'Value' },
                  ], [
                    { field: 'Receipt #', value: receipt.receipt_number || '-' },
                    { field: 'Student', value: receipt.student_name },
                    { field: 'Student #', value: receipt.student_number },
                    { field: 'Academic Year', value: receipt.academic_year_name },
                    { field: 'Fee Type', value: receipt.fee_type_name },
                    { field: 'Payment Method', value: receipt.payment_method || '-' },
                    { field: 'Amount', value: formatCurrency(receipt.amount) },
                    { field: 'Payment Date', value: receipt.payment_date || '-' },
                    { field: 'Recorded At', value: formatDateTime(receipt.created_at) },
                  ], `receipt-${receipt.receipt_number || receipt.payment_id}`)}
                >
                  Export PDF
                </Button>
              </div>
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-[var(--color-text-tertiary)]">Student</p>
              <p className="font-medium">{receipt.student_name}</p>
              <p className="text-sm text-[var(--color-text-muted)]">{receipt.student_number}</p>
            </div>
            <div>
              <p className="text-sm text-[var(--color-text-tertiary)]">Academic Year</p>
              <p className="font-medium">{receipt.academic_year_name}</p>
            </div>
            <div>
              <p className="text-sm text-[var(--color-text-tertiary)]">Fee Type</p>
              <p className="font-medium">{receipt.fee_type_name}</p>
            </div>
            <div>
              <p className="text-sm text-[var(--color-text-tertiary)]">Payment Method</p>
              <p className="font-medium capitalize">{receipt.payment_method || '-'}</p>
            </div>
            <div>
              <p className="text-sm text-[var(--color-text-tertiary)]">Amount</p>
              <p className="text-xl font-bold text-green-600">{formatCurrency(receipt.amount)}</p>
            </div>
            <div>
              <p className="text-sm text-[var(--color-text-tertiary)]">Payment Date</p>
              <p className="font-medium">{receipt.payment_date || '-'}</p>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-[var(--color-divider)]">
            <p className="text-sm text-[var(--color-text-tertiary)]">Recorded At</p>
            <p className="font-medium">{formatDateTime(receipt.created_at)}</p>
          </div>
        </Card>
      )}
    </div>
  )
}

export default ReceiptLookupPage