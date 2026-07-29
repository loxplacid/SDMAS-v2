import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

interface PageHeaderProps {
  title: string
  subtitle?: string
  actions?: ReactNode
  className?: string
  compact?: boolean
}

export function PageHeader({ title, subtitle, actions, className, compact = false }: PageHeaderProps) {
  return (
    <div
      className={cn(
        'flex flex-col sm:flex-row sm:items-center justify-between gap-3',
        compact ? 'mb-4' : 'mb-6',
        className
      )}
    >
      <div className="min-w-0 flex-1">
        <h1 className="text-xl sm:text-2xl font-bold text-[var(--color-text-primary)] tracking-tight">
          {title}
        </h1>
        {subtitle && (
          <p className="text-sm text-[var(--color-text-muted)] mt-1">{subtitle}</p>
        )}
      </div>
      {actions && <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>}
    </div>
  )
}
