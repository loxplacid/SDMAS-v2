import type { ReactNode } from 'react'
import { Card, AnimatedCount } from '../ui'

interface KpiCardProps {
  title: string
  value: string | number | ReactNode
  subtitle?: string
  trend?: 'up' | 'down' | 'neutral'
  icon?: ReactNode
  color?: 'blue' | 'green' | 'red' | 'yellow' | 'purple' | 'indigo' | 'orange'
}

const colorMap = {
  blue: 'text-blue-600 bg-blue-50',
  green: 'text-green-600 bg-green-50',
  red: 'text-red-600 bg-red-50',
  yellow: 'text-yellow-600 bg-yellow-50',
  purple: 'text-purple-600 bg-purple-50',
  indigo: 'text-indigo-600 bg-indigo-50',
  orange: 'text-orange-600 bg-orange-50',
}

const trendIcons = {
  up: '↑',
  down: '↓',
  neutral: '→',
}

const trendColors = {
  up: 'text-green-500',
  down: 'text-red-500',
  neutral: 'text-gray-500',
}

export function KpiCard({ title, value, subtitle, trend, icon, color = 'blue' }: KpiCardProps) {
  const renderValue = typeof value === 'number' ? (
    <AnimatedCount value={value} duration={800} />
  ) : (
    value
  )

  return (
    <Card className="relative overflow-hidden transition-shadow hover:shadow-md">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-500 truncate">{title}</p>
          <p className="mt-1 text-2xl font-bold text-gray-900 tabular-nums">{renderValue}</p>
          {subtitle && (
            <p className="mt-1 text-xs text-gray-400">{subtitle}</p>
          )}
          {trend && (
            <p className={`mt-1 text-sm font-medium ${trendColors[trend]}`}>
              {trendIcons[trend]} {trend === 'up' ? 'Improving' : trend === 'down' ? 'Needs attention' : 'Stable'}
            </p>
          )}
        </div>
        {icon && (
          <div className={`flex-shrink-0 p-2 rounded-lg ${colorMap[color]}`}>
            {icon}
          </div>
        )}
      </div>
    </Card>
  )
}
