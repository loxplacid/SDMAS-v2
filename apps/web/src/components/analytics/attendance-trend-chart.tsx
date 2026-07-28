import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import type { AttendanceTrendPoint } from '../../api/analytics/types'
import { EmptyState } from '../ui'

interface AttendanceTrendChartProps {
  data: AttendanceTrendPoint[]
  granularity?: string
  loading?: boolean
}

const statusColors: Record<string, string> = {
  present: '#22c55e',
  absent: '#ef4444',
  late: '#eab308',
  excused: '#a855f7',
}

export function AttendanceTrendChart({ data, granularity, loading }: AttendanceTrendChartProps) {
  if (loading) {
    return (
      <div className="h-64 flex items-center justify-center">
        <p className="text-sm text-gray-400">Loading chart...</p>
      </div>
    )
  }

  if (!data || data.length === 0) {
    return <EmptyState title="No Attendance Data" description="No attendance records found for the selected filters." />
  }

  return (
    <div className="w-full">
      <p className="text-sm text-gray-500 mb-2">
        Attendance Trend ({granularity || 'daily'})
      </p>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => {
              if (granularity === 'monthly') return v.slice(5)
              if (granularity === 'weekly') return v.slice(-5)
              return v
            }}
          />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip
            contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5e7eb' }}
            labelStyle={{ fontWeight: 600 }}
            formatter={((value: any) => [Number(value).toLocaleString(), 'Records']) as any}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {Object.entries(statusColors).map(([status, color]) => (
            <Line
              key={status}
              type="monotone"
              dataKey={status}
              stroke={color}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
              name={status.charAt(0).toUpperCase() + status.slice(1)}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
