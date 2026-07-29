import { Badge, type BadgeVariant } from './badge'
import { capitalize } from '../../lib/utils'

interface StatusBadgeProps {
  status: string
  variant?: BadgeVariant
  dot?: boolean
}

const statusVariantMap: Record<string, BadgeVariant> = {
  active: 'success',
  inactive: 'neutral',
  present: 'success',
  absent: 'danger',
  late: 'warning',
  excused: 'info',
  paid: 'success',
  unpaid: 'danger',
  partially_paid: 'warning',
  graduated: 'info',
  transferred: 'warning',
}

export function StatusBadge({ status, variant, dot = true }: StatusBadgeProps) {
  const resolvedVariant = variant || statusVariantMap[status] || 'neutral'
  const label = capitalize(status.replace(/_/g, ' '))

  return (
    <Badge variant={resolvedVariant} dot={dot}>
      {label}
    </Badge>
  )
}
