import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import type { AttendanceOverview } from '../../api/analytics/types'
import { EmptyState } from '../ui'

interface AttendanceStatusChartProps {
  data: AttendanceOverview | null
  loading?: boolean
}

const COLORS = {
  present: '#22c55e',
  absent: '#ef4444',
  late: '#eab308',
  excused: '#a855f7',
}

const LABELS: Record<string, string> = {
  present: 'Present',
  absent: 'Absent',
  late: 'Late',
  excused: 'Excused',
}

export function AttendanceStatusChart({ data, loading }: AttendanceStatusChartProps) {
  if (loading) {
    return (
      <div className="h-64 flex items-center justify-center">
        <p className="text-sm text-gray-400">Loading chart...</p>
      </div>
    )
  }

  if (!data || data.total_records === 0) {
    return <EmptyState title="No Data" description="No attendance records available." />
  }

  const chartData = [
    { name: 'Present', value: data.present, color: COLORS.present },
    { name: 'Absent', value: data.absent, color: COLORS.absent },
    { name: 'Late', value: data.late, color: COLORS.late },
    { name: 'Excused', value: data.excused, color: COLORS.excused },
  ].filter(d => d.value > 0)

  const formatPieLabel = ({ name, percent }: { name: string; percent?: number }) => {
    return `${name} ${((percent ?? 0) * 100).toFixed(0)}%`
  }

  const formatTooltip = (value: number | string) => {
    return [Number(value).toLocaleString(), 'Records'] as [string, string]
  }

  return (
    <div className="w-full">
      <ResponsiveContainer width="100%" height={260}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={100}
            paddingAngle={2}
            dataKey="value"
            label={formatPieLabel as any}
            labelLine={false}
          >
            {chartData.map((entry) => (
              <Cell key={entry.name} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip formatter={formatTooltip as any} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}
