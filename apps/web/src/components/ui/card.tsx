import type { CSSProperties, ReactNode } from 'react'
import { cn } from '../../lib/utils'

interface CardProps {
  title?: string
  subtitle?: string
  children: ReactNode
  className?: string
  style?: CSSProperties
  actions?: ReactNode
  onClick?: () => void
  padding?: 'none' | 'sm' | 'md' | 'lg'
  variant?: 'default' | 'elevated' | 'bordered' | 'flat'
}

const paddings = {
  none: '',
  sm: 'p-3',
  md: 'p-5',
  lg: 'p-7',
}

const variants = {
  default: 'bg-[var(--color-surface)] border border-[var(--color-border)] shadow-sm',
  elevated: 'bg-[var(--color-surface-elevated)] border border-[var(--color-border)] shadow-md',
  bordered: 'bg-[var(--color-surface)] border-2 border-[var(--color-border)]',
  flat: 'bg-[var(--color-bg)] border border-[var(--color-border)] rounded-xl',
}

export function Card({
  title,
  subtitle,
  children,
  className,
  style,
  actions,
  onClick,
  padding = 'md',
  variant = 'default',
}: CardProps) {
  return (
    <div
      style={style}
      className={cn(
        'rounded-2xl overflow-hidden',
        'motion-safe:transition-all motion-safe:duration-[var(--motion-base)] motion-safe:ease-[var(--ease-standard)]',
        variants[variant],
        onClick
          ? 'cursor-pointer motion-safe:hover:-translate-y-0.5 motion-safe:hover:shadow-lg hover:border-[var(--color-brand-accent)]/30'
          : '',
        className
      )}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onClick()
              }
            }
          : undefined
      }
    >
      {(title || subtitle || actions) && (
        <div className={cn(
          'flex items-start justify-between gap-4',
          paddings[padding],
          'pb-0'
        )}>
          <div className="min-w-0 flex-1">
            {title && (
              <h3 className="text-base font-semibold text-[var(--color-text-primary)] truncate">
                {title}
              </h3>
            )}
            {subtitle && (
              <p className="text-sm text-[var(--color-text-tertiary)] mt-0.5">{subtitle}</p>
            )}
          </div>
          {actions && <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>}
        </div>
      )}
      <div className={cn(paddings[padding])}>{children}</div>
    </div>
  )
}
