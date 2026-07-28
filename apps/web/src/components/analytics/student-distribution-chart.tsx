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
import type { StudentsByClass } from '../../api/analytics/types'
import { EmptyState } from '../ui'

interface StudentDistributionChartProps {
  data: StudentsByClass[]
  loading?: boolean
  title?: string
}

const COLORS = ['#3b82f6', '#22c55e', '#a855f7', '#eab308', '#ef4444', '#06b6d4', '#f97316', '#8b5cf6']

export function StudentDistributionChart({ data, loading, title }: StudentDistributionChartProps) {
  if (loading) {
    return (
      <div className="h-64 flex items-center justify-center">
        <p className="text-sm text-gray-400">Loading chart...</p>
      </div>
    )
  }

  if (!data || data.length === 0) {
    return <EmptyState title="No Data" description="No student distribution data available." />
  }

  return (
    <div className="w-full">
      {title && (
        <p className="text-sm text-gray-500 mb-2">{title}</p>
      )}
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="class_name" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip
            formatter={((value: any) => [Number(value).toLocaleString(), 'Students']) as any}
            contentStyle={{ fontSize: 12, borderRadius: 8 }}
          />
          <Bar dataKey="student_count" name="Students" radius={[4, 4, 0, 0]}>
            {data.map((_, index) => (
              <Cell key={index} fill={COLORS[index % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
