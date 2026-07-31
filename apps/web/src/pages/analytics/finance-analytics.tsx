import { useState, useEffect, useCallback, useRef } from 'react'
import { academicYearApi } from '../../api/academic/academic-year-api'
import { financeAnalyticsApi } from '../../api/analytics/finance-analytics-api'
import type { FinanceOverview, CollectionTrend, FeeTypeCollection, ClassFeeCollection, PaymentMethodDistribution, FeeStatusDistribution } from '../../api/analytics/types'
import { Card, Loading, ErrorState, Table, Select } from '../../components/ui'
import { KpiCard } from '../../components/analytics/kpi-card'
import { CollectionTrendChart } from '../../components/analytics/collection-trend-chart'
import { formatCurrency } from '../../lib/utils'

export function FinanceAnalyticsPage() {
  const [academicYears, setAcademicYears] = useState<{ value: string; label: string }[]>([])
  const [selectedYearId, setSelectedYearId] = useState('')
  const [granularity, setGranularity] = useState('monthly')

  const [overview, setOverview] = useState<FinanceOverview | null>(null)
  const [trends, setTrends] = useState<CollectionTrend | null>(null)
  const [feeTypeData, setFeeTypeData] = useState<FeeTypeCollection[]>([])
  const [classData, setClassData] = useState<ClassFeeCollection[]>([])
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethodDistribution[]>([])
  const [statusDist, setStatusDist] = useState<FeeStatusDistribution[]>([])

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  useEffect(() => {
    academicYearApi.list({ size: 100 }).then(r => {
      setAcademicYears([{ value: '', label: 'All Years' }, ...r.items.map(y => ({ value: String(y.id), label: y.name }))])
    }).catch(() => {})
  }, [])

  const fetchData = useCallback(async () => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)

    try {
      const params: Record<string, any> = {}
      if (selectedYearId) params.academic_year_id = Number(selectedYearId)

      const [ov, tr, ft, cd, pm, sd] = await Promise.all([
        financeAnalyticsApi.getOverview(params),
        financeAnalyticsApi.getTrends({ ...params, granularity }),
        financeAnalyticsApi.getFeeTypeCollection(params).catch(() => [] as FeeTypeCollection[]),
        financeAnalyticsApi.getClassCollection(params).catch(() => [] as ClassFeeCollection[]),
        financeAnalyticsApi.getPaymentMethods(params).catch(() => [] as PaymentMethodDistribution[]),
        financeAnalyticsApi.getStatusDistribution(params).catch(() => [] as FeeStatusDistribution[]),
      ])

      if (fetchId === fetchIdRef.current) {
        setOverview(ov)
        setTrends(tr)
        setFeeTypeData(ft)
        setClassData(cd)
        setPaymentMethods(pm)
        setStatusDist(sd)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load analytics')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [selectedYearId, granularity])

  useEffect(() => { fetchData() }, [fetchData])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">Financial Analytics</h1>
        <p className="text-[var(--color-text-tertiary)] mt-1">Fee collection metrics and financial insights</p>
      </div>

      <Card>
        <div className="flex flex-wrap gap-3">
          <div className="min-w-[200px]">
            <label className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1">Academic Year</label>
            <Select
              options={academicYears}
              value={selectedYearId}
              onChange={(e) => setSelectedYearId(e.target.value)}
              placeholder="All Years"
            />
          </div>
          <div className="min-w-[160px]">
            <label className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1">Granularity</label>
            <Select
              options={[{ value: 'daily', label: 'Daily' }, { value: 'weekly', label: 'Weekly' }, { value: 'monthly', label: 'Monthly' }]}
              value={granularity}
              onChange={(e) => setGranularity(e.target.value)}
            />
          </div>
        </div>
      </Card>

      {error && <ErrorState message={error} onRetry={fetchData} />}

      {loading ? (
        <Loading text="Loading analytics..." />
      ) : (
        <>
          {overview && (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <KpiCard title="Total Fees" value={formatCurrency(overview.total_fees_amount)} color="blue" />
                <KpiCard title="Collected" value={formatCurrency(overview.total_collected)} color="green" />
                <KpiCard title="Outstanding" value={formatCurrency(overview.total_outstanding)} color="red" />
                <KpiCard title="Collection %" value={`${overview.collection_percentage}%`} color="purple" />
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <KpiCard title="Fully Paid" value={overview.fully_paid_students} color="green" subtitle="students" />
                <KpiCard title="Partially Paid" value={overview.partially_paid_students} color="yellow" subtitle="students" />
                <KpiCard title="Unpaid" value={overview.unpaid_students} color="red" subtitle="students" />
                <KpiCard title="With Outstanding" value={overview.students_with_outstanding} color="orange" subtitle="students" />
              </div>
            </>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card title="Collection Trend">
              <CollectionTrendChart data={trends?.trend || []} granularity={trends?.granularity} loading={false} />
            </Card>
            <Card title="Payment Status">
              {statusDist.length > 0 ? (
                <Table
                  columns={[
                    { key: 'status', header: 'Status', render: (r: FeeStatusDistribution) => (
                      <span className="capitalize">{r.status.replace('_', ' ')}</span>
                    )},
                    { key: 'count', header: 'Count' },
                    { key: 'total_amount', header: 'Amount', render: (r: FeeStatusDistribution) => formatCurrency(r.total_amount) },
                  ]}
                  data={statusDist}
                  keyExtractor={(r) => r.status}
                  emptyMessage="No data."
                />
              ) : (
                <p className="text-[var(--color-text-muted)] text-sm text-center py-8">No fee due data available.</p>
              )}
            </Card>
          </div>

          {feeTypeData.length > 0 && (
            <Card title="Collection by Fee Type">
              <Table
                columns={[
                  { key: 'fee_type_name', header: 'Fee Type' },
                  { key: 'total_expected', header: 'Expected', render: (r: FeeTypeCollection) => formatCurrency(r.total_expected) },
                  { key: 'total_collected', header: 'Collected', render: (r: FeeTypeCollection) => (
                    <span className="text-green-600">{formatCurrency(r.total_collected)}</span>
                  )},
                  { key: 'outstanding', header: 'Outstanding', render: (r: FeeTypeCollection) => (
                    <span className="text-red-600">{formatCurrency(r.outstanding)}</span>
                  )},
                  { key: 'collection_percentage', header: '%', render: (r: FeeTypeCollection) => `${r.collection_percentage}%` },
                ]}
                data={feeTypeData}
                keyExtractor={(r) => r.fee_type_id}
                emptyMessage="No data."
              />
            </Card>
          )}

          {classData.length > 0 && (
            <Card title="Collection by Class">
              <Table
                columns={[
                  { key: 'class_name', header: 'Class' },
                  { key: 'total_expected', header: 'Expected', render: (r: ClassFeeCollection) => formatCurrency(r.total_expected) },
                  { key: 'total_collected', header: 'Collected', render: (r: ClassFeeCollection) => (
                    <span className="text-green-600">{formatCurrency(r.total_collected)}</span>
                  )},
                  { key: 'outstanding', header: 'Outstanding', render: (r: ClassFeeCollection) => (
                    <span className="text-red-600">{formatCurrency(r.outstanding)}</span>
                  )},
                  { key: 'collection_percentage', header: '%', render: (r: ClassFeeCollection) => `${r.collection_percentage}%` },
                ]}
                data={classData}
                keyExtractor={(r) => r.class_id}
                emptyMessage="No data."
              />
            </Card>
          )}

          {paymentMethods.length > 0 && (
            <Card title="Payment Method Distribution">
              <Table
                columns={[
                  { key: 'payment_method', header: 'Method', render: (r: PaymentMethodDistribution) => (
                    <span className="capitalize">{r.payment_method.replace('_', ' ')}</span>
                  )},
                  { key: 'transaction_count', header: 'Transactions' },
                  { key: 'total_amount', header: 'Amount', render: (r: PaymentMethodDistribution) => formatCurrency(r.total_amount) },
                ]}
                data={paymentMethods}
                keyExtractor={(r) => r.payment_method}
                emptyMessage="No payment data."
              />
            </Card>
          )}
        </>
      )}
    </div>
  )
}

export default FinanceAnalyticsPage
