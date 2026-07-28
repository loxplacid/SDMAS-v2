import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import type { CollectionTrendPoint } from '../../api/analytics/types'
import { EmptyState } from '../ui'
import { formatCurrency } from '../../lib/utils'

interface CollectionTrendChartProps {
  data: CollectionTrendPoint[]
  granularity?: string
  loading?: boolean
}

export function CollectionTrendChart({ data, granularity, loading }: CollectionTrendChartProps) {
  if (loading) {
    return (
      <div className="h-64 flex items-center justify-center">
        <p className="text-sm text-gray-400">Loading chart...</p>
      </div>
    )
  }

  if (!data || data.length === 0) {
    return <EmptyState title="No Data" description="No collection data available for the selected filters." />
  }

  const chartData = data.map(d => ({
    ...d,
    displayDate: granularity === 'monthly' ? d.date.slice(5) : d.date,
  }))

  return (
    <div className="w-full">
      <p className="text-sm text-gray-500 mb-2">
        Collection Trend ({granularity || 'daily'})
      </p>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="displayDate" tick={{ fontSize: 11 }} />
          <YAxis
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => formatCurrency(v)}
          />
          <Tooltip
            formatter={((value: any) => [formatCurrency(Number(value)), 'Amount']) as any}
            contentStyle={{ fontSize: 12, borderRadius: 8 }}
          />
          <Line
            type="monotone"
            dataKey="amount"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={{ r: 3, fill: '#3b82f6' }}
            activeDot={{ r: 5 }}
            name="Amount"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
