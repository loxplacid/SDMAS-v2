import { useState } from 'react'
import { feeReportApi } from '../../api/reports/fee-reports'
import type { DetailedReceipt } from '../../api/reports/types'
import { Card, Button, Loading, ErrorState, Input, Badge } from '../../components/ui'
import { formatCurrency, formatDateTime } from '../../lib/utils'

export function ReceiptLookupPage() {
  const [paymentId, setPaymentId] = useState('')
  const [receipt, setReceipt] = useState<DetailedReceipt | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Receipt Lookup</h1>
        <p className="text-gray-500 mt-1">View payment receipt details</p>
      </div>

      <Card>
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
      {loading && <Loading text="Looking up receipt..." />}

      {receipt && (
        <Card>
          <div className="border-b border-gray-200 pb-4 mb-4">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-semibold">Payment Receipt</h2>
              {receipt.receipt_number && (
                <Badge variant="success">#{receipt.receipt_number}</Badge>
              )}
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-gray-500">Student</p>
              <p className="font-medium">{receipt.student_name}</p>
              <p className="text-sm text-gray-400">{receipt.student_number}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Academic Year</p>
              <p className="font-medium">{receipt.academic_year_name}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Fee Type</p>
              <p className="font-medium">{receipt.fee_type_name}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Payment Method</p>
              <p className="font-medium capitalize">{receipt.payment_method || '-'}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Amount</p>
              <p className="text-xl font-bold text-green-600">{formatCurrency(receipt.amount)}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Payment Date</p>
              <p className="font-medium">{receipt.payment_date || '-'}</p>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-gray-200">
            <p className="text-sm text-gray-500">Recorded At</p>
            <p className="font-medium">{formatDateTime(receipt.created_at)}</p>
          </div>
        </Card>
      )}
    </div>
  )
}

export default ReceiptLookupPage