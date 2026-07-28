import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import type { ClassAttendanceComparison } from '../../api/analytics/types'
import { EmptyState } from '../ui'

interface ClassComparisonChartProps {
  data: ClassAttendanceComparison[]
  loading?: boolean
}

export function ClassComparisonChart({ data, loading }: ClassComparisonChartProps) {
  if (loading) {
    return (
      <div className="h-64 flex items-center justify-center">
        <p className="text-sm text-gray-400">Loading chart...</p>
      </div>
    )
  }

  if (!data || data.length === 0) {
    return <EmptyState title="No Data" description="No class attendance data available." />
  }

  const chartData = data.map(d => ({
    name: d.class_name,
    percentage: Math.round(d.attendance_percentage * 10) / 10,
    present: d.present,
    total: d.total_records,
  }))

  const getBarColor = (pct: number) => {
    if (pct >= 90) return '#22c55e'
    if (pct >= 75) return '#eab308'
    return '#ef4444'
  }

  return (
    <div className="w-full">
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="name" tick={{ fontSize: 11 }} />
          <YAxis
            domain={[0, 100]}
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => `${v}%`}
          />
          <Tooltip
            formatter={((value: any) => [`${Number(value).toFixed(1)}%`, 'Attendance %']) as any}
            contentStyle={{ fontSize: 12, borderRadius: 8 }}
          />
          <Bar dataKey="percentage" name="Attendance %" radius={[4, 4, 0, 0]}>
            {chartData.map((entry) => (
              <Cell key={entry.name} fill={getBarColor(entry.percentage)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
